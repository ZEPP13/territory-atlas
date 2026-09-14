#!/usr/bin/env python3
"""Local server for the war table.

    python3 07-war-table/serve.py            # http://127.0.0.1:8777

Why a server at all: a static page cannot write a file, and one-tap logging has to land
somewhere durable. This is the smallest thing that does that — Python stdlib, no framework,
no database. The page still works read-only when opened as a plain file.

Security posture, for review:
  * binds to 127.0.0.1 only; refuses to start on any other interface without --unsafe-host
  * rejects requests whose Host header is not localhost (blocks DNS-rebinding)
  * POST requires the header `X-War-Table: 1` and `Content-Type: application/json`, which a
    cross-site form or image cannot send without a CORS preflight this server never grants
  * bodies over 16 KB are refused; unknown fields are refused; every record is schema-validated
    and checked for referential integrity before it is appended
  * serves exactly one HTML file and three JSON routes; no filesystem paths from the client
"""
import argparse
import json
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wartable import DATA, DIST, store                              # noqa: E402
from wartable.registry import LedgerError, apply_ledger, check_change, load_base  # noqa: E402
from wartable.state import compose                                  # noqa: E402

MAX_BODY = 16_000
TAPS = {"surveyed", "visited", "met", "quoted", "won"}
SIGNAL_ACTIONS = {"signal_reviewed", "signal_pinned", "signal_dismissed"}
LEDGER_FROM_UI = {"mark_defunct", "mark_not_a_fit", "mark_assigned_elsewhere", "mark_duplicate", "reinstate"}
LOG_FIELDS = {"action", "entity_id", "signal_id", "undo_of", "role"}
LEDGER_FIELDS = {"change", "entity_id", "reason", "duplicate_of", "evidence"}
WRITE_LOCK = threading.Lock()


class BadRequest(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


class App:
    def __init__(self, dist=DIST, data_dir=DATA):
        self.dist, self.data_dir = dist, data_dir
        self._base, self._mtime = None, None

    def base(self):
        p = os.path.join(self.dist, "registry_base.json")
        m = os.path.getmtime(p)
        if m != self._mtime:
            self._base, self._mtime = load_base(p), m
        return self._base

    def state(self):
        return compose(self.base(), self.data_dir)

    # ---------------------------------------------------------------- writes
    def log(self, body):
        extra = set(body) - LOG_FIELDS
        if extra:
            raise BadRequest(400, f"unexpected fields: {sorted(extra)}")
        action = body.get("action")
        rec = {"id": store.new_id("lb-"), "ts": store.now_iso(), "actor": "joe", "action": action}
        with WRITE_LOCK:
            ledger = store.read("ledger", self.data_dir)
            ents, _ = apply_ledger(self.base(), ledger)
            if action in TAPS:
                eid = body.get("entity_id")
                if eid not in ents:
                    raise BadRequest(400, f"unknown entity {eid!r}")
                if ents[eid]["status"]["value"] != "active":
                    raise BadRequest(409, f"{eid} is {ents[eid]['status']['value']}; reinstate it first")
                rec["entity_id"] = eid
                # record the opportunity rating as it stood when the tap was made, so later changes
                # to the scoring model never take earned points away
                band = (ents[eid].get("potential") or {}).get("band")
                if band:
                    rec["band"] = band
                if body.get("role"):
                    if action != "met":
                        raise BadRequest(400, "role is only recorded for 'met'")
                    rec["role"] = body["role"].strip()
            elif action in SIGNAL_ACTIONS:
                sid = body.get("signal_id")
                if sid not in {s["id"] for s in store.read("signals", self.data_dir)}:
                    raise BadRequest(400, f"unknown signal {sid!r}")
                rec["signal_id"] = sid
            elif action == "undo":
                target = body.get("undo_of")
                logbook = store.read("logbook", self.data_dir)
                done = {e["undo_of"] for e in logbook if e["action"] == "undo"}
                ev = next((e for e in logbook if e["id"] == target), None)
                if not ev or ev["action"] not in TAPS:
                    raise BadRequest(400, "undo_of must name an existing tap")
                if target in done:
                    raise BadRequest(409, "that tap is already undone")
                rec["undo_of"] = target
                rec["entity_id"] = ev["entity_id"]
            else:
                raise BadRequest(400, f"unsupported action {action!r}")
            try:
                store.append("logbook", rec, self.data_dir)
            except store.StoreError as e:
                raise BadRequest(400, str(e))
        return rec

    def ledger(self, body):
        extra = set(body) - LEDGER_FIELDS
        if extra:
            raise BadRequest(400, f"unexpected fields: {sorted(extra)}")
        if body.get("change") not in LEDGER_FROM_UI:
            raise BadRequest(400, f"change must be one of {sorted(LEDGER_FROM_UI)}")
        rec = {"id": store.new_id("lc-"), "ts": store.now_iso(), "actor": "joe", **body}
        rec["reason"] = (rec.get("reason") or "").strip()
        with WRITE_LOCK:
            ledger = store.read("ledger", self.data_dir)
            try:
                store.validate_record("ledger", rec)
                ents, _ = apply_ledger(self.base(), ledger)
                check_change(rec, ents.keys())
                apply_ledger(self.base(), ledger + [rec])      # proves no loop / conflict
                store.append("ledger", rec, self.data_dir)
            except (store.StoreError, LedgerError) as e:
                raise BadRequest(400, str(e))
        return rec


def make_handler(app, allowed_hosts=("127.0.0.1", "localhost"), quiet=False):
    class Handler(BaseHTTPRequestHandler):
        server_version = "WarTable/1.0"
        sys_version = ""

        def log_message(self, fmt, *args):
            if quiet:
                return
            sys.stderr.write("%s %s\n" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), fmt % args))

        def _send(self, code, payload=None, raw=None, ctype="application/json; charset=utf-8"):
            body = raw if raw is not None else json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            if ctype.startswith("text/html"):
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                                 "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                 "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; "
                                 "connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self):
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            return host in allowed_hosts

        def do_HEAD(self):
            if not self._host_ok():
                self.send_response(403); self.end_headers(); return
            path = urlsplit(self.path).path
            self.send_response(200 if path in ("/", "/index.html", "/api/health", "/api/state") else 404)
            self.end_headers()

        def handle(self):
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError):
                pass                      # the browser closed the connection early; nothing to do

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "host not allowed"})
            path = urlsplit(self.path).path
            try:
                if path in ("/", "/index.html"):
                    with open(os.path.join(app.dist, "war_table.html"), "rb") as fh:
                        return self._send(200, raw=fh.read(), ctype="text/html; charset=utf-8")
                if path == "/api/state":
                    return self._send(200, app.state())
                if path == "/api/health":
                    return self._send(200, {"ok": True})
                return self._send(404, {"error": "not found"})
            except (store.StoreError, LedgerError) as e:
                return self._send(500, {"error": f"data layer invalid: {e}"})

        def do_POST(self):
            if not self._host_ok():
                return self._send(403, {"error": "host not allowed"})
            if self.headers.get("X-War-Table") != "1":
                return self._send(403, {"error": "missing X-War-Table header"})
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._send(415, {"error": "application/json required"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, {"error": "bad Content-Length"})
            if n <= 0 or n > MAX_BODY:
                return self._send(413, {"error": f"body must be 1..{MAX_BODY} bytes"})
            try:
                body = json.loads(self.rfile.read(n))
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON"})
            if not isinstance(body, dict):
                return self._send(400, {"error": "JSON object required"})
            path = urlsplit(self.path).path
            try:
                if path == "/api/logbook":
                    rec = app.log(body)
                elif path == "/api/ledger":
                    rec = app.ledger(body)
                else:
                    return self._send(404, {"error": "not found"})
                return self._send(201, {"record": rec, "state": app.state()})
            except BadRequest as e:
                return self._send(e.code, {"error": str(e)})

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--data-dir", default=DATA, help="folder holding ledger/, signals/, logbook/")
    ap.add_argument("--dist", default=DIST, help="folder holding war_table.html and registry_base.json")
    ap.add_argument("--unsafe-host", action="store_true", help="allow binding beyond localhost (not recommended)")
    a = ap.parse_args(argv)
    if a.host not in ("127.0.0.1", "localhost") and not a.unsafe_host:
        sys.exit("refusing to bind beyond localhost; this server has no authentication")
    app = App(a.dist, a.data_dir)
    app.state()                        # fail fast if any layer is invalid
    srv = ThreadingHTTPServer((a.host, a.port), make_handler(app))
    print(f"War table on http://{a.host}:{a.port}  (data: {a.data_dir})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
