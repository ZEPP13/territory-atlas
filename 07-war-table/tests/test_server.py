"""The local server: input handling and security posture. Uses a throwaway data folder."""
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from helpers import entity, tempdir
import serve
from wartable import store


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempdir()
        with open(os.path.join(cls.dir, "registry_base.json"), "w") as fh:
            json.dump([entity("S-1", band="High"), entity("S-2"), entity("S-3")], fh)
        with open(os.path.join(cls.dir, "war_table.html"), "w") as fh:
            fh.write("<p>stub</p>")
        cls.app = serve.App(dist=cls.dir, data_dir=cls.dir)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(cls.app, quiet=True))
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, method, path, body=None, headers=None, raw=None):
        h = {"Host": f"127.0.0.1:{self.port}"}
        data = None
        if body is not None or raw is not None:
            data = raw if raw is not None else json.dumps(body).encode()
            h.update({"Content-Type": "application/json", "X-War-Table": "1"})
        h.update(headers or {})
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read() or b"null") if "json" in resp.headers["Content-Type"] else resp.read()
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_state_is_served(self):
        code, st = self.req("GET", "/api/state")
        self.assertEqual(code, 200)
        self.assertIn("rank", st["progression"])

    def test_foreign_host_header_is_refused(self):
        code, _ = self.req("GET", "/api/state", headers={"Host": "evil.example"})
        self.assertEqual(code, 403)

    def test_post_without_custom_header_is_refused(self):
        code, _ = self.req("POST", "/api/logbook", body={"action": "surveyed", "entity_id": "S-1"},
                           headers={"X-War-Table": "0"})
        self.assertEqual(code, 403)

    def test_oversize_body_is_refused(self):
        code, _ = self.req("POST", "/api/logbook", raw=b"{" + b" " * 20000 + b"}")
        self.assertEqual(code, 413)

    def test_unknown_fields_and_actions_are_refused(self):
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "surveyed", "entity_id": "S-1", "note": "x"})[0], 400)
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "deleted", "entity_id": "S-1"})[0], 400)
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "surveyed", "entity_id": "NOPE"})[0], 400)

    def test_a_tap_is_appended_and_state_updates(self):
        code, out = self.req("POST", "/api/logbook", body={"action": "visited", "entity_id": "S-2"})
        self.assertEqual(code, 201)
        self.assertEqual(out["state"]["stages"]["S-2"], "landfall")
        self.assertEqual(out["record"]["band"], "Medium")
        self.assertTrue(any(r["id"] == out["record"]["id"] for r in store.read("logbook", self.dir)))

    def test_role_is_only_accepted_for_met_and_never_an_email(self):
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "visited", "entity_id": "S-1", "role": "Plant manager"})[0], 400)
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "met", "entity_id": "S-1", "role": "a@b.com"})[0], 400)
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "met", "entity_id": "S-1", "role": "Plant manager"})[0], 201)

    def test_undo_reverses_a_tap_once(self):
        _, out = self.req("POST", "/api/logbook", body={"action": "won", "entity_id": "S-3"})
        tap_id = out["record"]["id"]
        code, out2 = self.req("POST", "/api/logbook", body={"action": "undo", "undo_of": tap_id})
        self.assertEqual(code, 201)
        self.assertNotIn("S-3", out2["state"]["stages"])
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "undo", "undo_of": tap_id})[0], 409)

    def test_ledger_change_needs_a_reason_and_blocks_taps_until_reinstated(self):
        self.assertEqual(self.req("POST", "/api/ledger", body={"change": "mark_not_a_fit", "entity_id": "S-1", "reason": ""})[0], 400)
        code, out = self.req("POST", "/api/ledger", body={"change": "mark_not_a_fit", "entity_id": "S-1", "reason": "no process fluid"})
        self.assertEqual(code, 201)
        self.assertEqual(out["state"]["statuses"]["S-1"]["value"], "not_a_fit")
        self.assertEqual(self.req("POST", "/api/logbook", body={"action": "surveyed", "entity_id": "S-1"})[0], 409)
        self.assertEqual(self.req("POST", "/api/ledger", body={"change": "reinstate", "entity_id": "S-1", "reason": "was wrong"})[0], 201)

    def test_add_entity_is_not_available_from_the_dashboard(self):
        self.assertEqual(self.req("POST", "/api/ledger", body={"change": "add_entity", "entity_id": "Z-1", "reason": "test"})[0], 400)


if __name__ == "__main__":
    unittest.main()
