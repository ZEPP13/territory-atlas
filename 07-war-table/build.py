#!/usr/bin/env python3
"""Build the war table.

    python3 07-war-table/build.py                # full build: validate, test, render
    python3 07-war-table/build.py --skip-tests   # faster; the manifest records that tests were skipped

Steps, each of which stops the build on failure:
  1. load every schema (refusing any keyword the validator cannot enforce)
  2. build the base registry from sources with the unchanged merge + opportunity model
  3. seed registry-snapshot signals (append-only; deterministic ids never duplicate)
  4. read and validate the ledger, signals and logbook
  5. compose the dashboard state through the same code path the live server uses
  6. run the test suite
  7. write dist/manifest.json: input hashes, counts, validation and test results
  8. render dist/war_table.html
"""
import argparse
import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from wartable import DATA, DIST, ROOT, CONFIG, SCHEMAS, store          # noqa: E402
from wartable.schema import load as load_schema                        # noqa: E402
from wartable import registry, signals as sigmod, state as statemod    # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "05-preview"))
from industry import FAMILIES, FAMILY_ORDER                            # noqa: E402
from potential import family_catalog, WEIGHTS, BANDS                   # noqa: E402
from palette import COLORS, ICONS                                      # noqa: E402

INPUTS = [
    "02-data/registry/iir_sites.json", "02-data/registry/deq_sites.json", "02-data/registry/registry_sites.json",
    "02-data/registry/egrid_plants.json", "02-data/exclusions.json", "02-data/clusters.json",
    "02-data/model_config.json", "02-data/geo/basemap.json", "02-data/geo/terrain.png",
    "02-data/ledger/registry_changes.jsonl", "02-data/signals/signals.jsonl", "02-data/logbook/logbook.jsonl",
    "04-outputs/merge.py", "05-preview/industry.py", "05-preview/potential.py", "05-preview/ids.py",
    "07-war-table/config/progression.json", "07-war-table/config/signals.json",
    "07-war-table/schemas/entity.schema.json", "07-war-table/schemas/ledger_change.schema.json",
    "07-war-table/schemas/signal.schema.json", "07-war-table/schemas/logbook_event.schema.json",
    "07-war-table/wartable/progression.py", "07-war-table/wartable/registry.py",
    "07-war-table/wartable/signals.py", "07-war-table/wartable/state.py",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def step(n, msg):
    print(f"[{n}] {msg}", flush=True)


def check_dashboard_js(template):
    """Syntax-check the dashboard's module script with Node when it is installed.

    A syntax error stops the whole page silently in a browser, so this is worth a real parser.
    Node is optional; when absent the manifest says the check was skipped rather than passed."""
    import shutil
    import tempfile
    node = shutil.which("node")
    if not node:
        return {"checked": False, "ok": None, "detail": "node not installed; skipped"}
    start = template.index('<script type="module">') + len('<script type="module">')
    js = template[start:template.index("</script>", start)].replace("/*__DATA__*/", "{}")
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
        fh.write(js)
    p = subprocess.run([node, "--check", fh.name], capture_output=True, text=True)
    os.unlink(fh.name)
    return {"checked": True, "ok": p.returncode == 0,
            "detail": "node --check passed" if p.returncode == 0 else p.stderr.strip().splitlines()[:6]}


def run_tests():
    t0 = time.time()
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", os.path.join(HERE, "tests")],
                       cwd=ROOT, capture_output=True, text=True)
    tail = p.stderr.strip().splitlines()
    ran = next((l for l in reversed(tail) if l.startswith("Ran ")), "Ran ? tests")
    return {"passed": p.returncode == 0, "summary": f"{ran} — {tail[-1] if tail else ''}",
            "seconds": round(time.time() - t0, 1), "output_tail": tail[-15:] if p.returncode else []}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()

    step(1, "schemas")
    for name in ("entity", "ledger_change", "signal", "logbook_event"):
        load_schema(name)

    step(2, "base registry (merge + opportunity model)")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        base = registry.build_base()
    registry.save_base(base)
    print(f"    {len(base)} entities, all schema-valid")

    step(3, "seed registry-snapshot signals")
    existing = {s["id"] for s in store.read("signals")}
    added = 0
    for s in sigmod.seed_from_registry(base):
        if s["id"] not in existing:
            store.append("signals", s)
            added += 1
    print(f"    {added} new, {len(existing)} already present")

    step(4, "validate ledger, signals, logbook")
    ledger, sigs, logbook = store.read("ledger"), store.read("signals"), store.read("logbook")
    print(f"    ledger {len(ledger)} · signals {len(sigs)} · logbook {len(logbook)}")

    step(5, "compose state")
    st = statemod.compose(base, ledger=ledger, signals=sigs, logbook=logbook)
    print(f"    rank: {st['progression']['rank']['title']} · {st['progression']['points']['total']} pts")

    tests = {"passed": None, "summary": "skipped (--skip-tests)", "seconds": 0, "output_tail": []}
    if not a.skip_tests:
        step(6, "tests")
        tests = run_tests()
        print(f"    {tests['summary']}")
        if not tests["passed"]:
            print("\n".join(tests["output_tail"]))
            sys.exit("build stopped: tests failed")

    js_check = {"checked": False, "ok": None, "detail": "no dashboard template"}
    tpl_path = os.path.join(HERE, "dashboard_template.html")
    if os.path.exists(tpl_path):
        step("6b", "dashboard script syntax")
        js_check = check_dashboard_js(open(tpl_path).read())
        print(f"    {js_check['detail'] if js_check['ok'] is not False else 'FAILED'}")
        if js_check["ok"] is False:
            print("\n".join(js_check["detail"]))
            sys.exit("build stopped: dashboard script has a syntax error")

    step(7, "manifest")
    manifest = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(),
        "model": {"opportunity_weights": WEIGHTS, "opportunity_bands": dict(BANDS),
                  "progression_version": json.load(open(os.path.join(CONFIG, "progression.json")))["version"],
                  "signals_version": json.load(open(os.path.join(CONFIG, "signals.json")))["version"]},
        "inputs": [{"path": p, "sha256": sha256(os.path.join(ROOT, p)), "bytes": os.path.getsize(os.path.join(ROOT, p))}
                   for p in INPUTS if os.path.exists(os.path.join(ROOT, p))],
        "validation": {"schemas": 4, "entities_valid": len(base), "ledger_valid": len(ledger),
                       "signals_valid": len(sigs), "logbook_valid": len(logbook)},
        "tests": {k: v for k, v in tests.items() if k != "output_tail"},
        "dashboard_js": js_check,
        "counts": st["counts"],
        "ai_generated": {
            "registry_records_from_ai_recall_sweep": sum(1 for e in base if e.get("existence") == "recall"),
            "signals_ai_summarised": sum(1 for s in sigs if s["generated_by"]["kind"] == "ai"),
            "in_scoring_path": False},
    }
    os.makedirs(DIST, exist_ok=True)
    with open(os.path.join(DIST, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    step(8, "dashboard")
    if not os.path.exists(tpl_path):
        print("    dashboard_template.html not present yet; data build complete")
        return
    CL = json.load(open(os.path.join(ROOT, "02-data", "clusters.json")))
    bundle = {
        "entities": base,
        "families": [{"id": f, "label": lb, "icon": ic, "c": COLORS[f][0], "cd": COLORS[f][1]} for f, lb, ic in FAMILIES],
        "icons": ICONS,
        "profiles": {f: family_catalog(f) for f in FAMILY_ORDER},
        "clusters": {c: {"name": v[0], "band": v[1], "j": v[2]} for c, v in CL.items()},
        "geo": json.load(open(os.path.join(ROOT, "02-data", "geo", "basemap.json"))),
        "terrain": json.load(open(os.path.join(ROOT, "02-data", "geo", "terrain.json"))),
        "terrainPng": "data:image/png;base64," + base64.b64encode(
            open(os.path.join(ROOT, "02-data", "geo", "terrain.png"), "rb").read()).decode(),
        "config": {"progression": json.load(open(os.path.join(CONFIG, "progression.json"))),
                   "signals": json.load(open(os.path.join(CONFIG, "signals.json")))},
        "manifest": manifest,
        "state": st,
        "home": {"lat": registry.RICHMOND[0], "lon": registry.RICHMOND[1]},
    }
    html = open(tpl_path).read().replace("/*__DATA__*/", json.dumps(bundle, separators=(",", ":")))
    out = os.path.join(DIST, "war_table.html")
    with open(out, "w") as fh:
        fh.write(html)
    print(f"    {out}  {len(html)/1e6:.2f} MB")
    print(f"done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
