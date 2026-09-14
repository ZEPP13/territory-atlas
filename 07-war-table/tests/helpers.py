import os
import sys
import tempfile
import warnings

# 04-outputs/merge.py (legacy, deliberately unmodified) opens files without closing them
warnings.simplefilter("ignore", ResourceWarning)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def entity(eid, cluster="C1", band="Medium", scope="core", kind="facility", timing="operating"):
    e = {
        "id": eid, "kind": kind, "name": f"Plant {eid}", "parent": "", "operator": "",
        "lat": 37.5, "lon": -77.4, "jurisdiction": "Henrico", "cluster": cluster, "band": 1, "miles": 5.0,
        "scope": scope, "family": "chemicals", "sector": "chemical", "subindustry": "", "note": "",
        "existence": "registry", "address": "", "city": "",
        "confidence": {"k": "high", "label": "High", "why": "test"},
        "timing": {"k": timing, "label": timing.title(), "why": ""},
        "facts": {"employees": 0, "sqft": 0, "mw": 0.0, "fuel": "", "gen_mwh": None, "cogen": False},
        "sources": [{"label": "Industrial Info", "what": "test", "as_of": "2026-09-09"}],
        "flags": [],
        "status": {"value": "active", "change_id": None, "reason": None, "duplicate_of": None, "since": None},
    }
    if kind == "facility":
        e["potential"] = {"band": band, "score": 50.0,
                          "factors": {"intensity": 2.0, "scale": 1.5, "breadth": 2.0, "verified": 0.0},
                          "reasons": ["@why"], "scale_verified": False, "scale_text": "", "verified_facts": [],
                          "apps_verified": []}
    return e


def change(cid, ts, kind, eid, **kw):
    return {"id": f"lc-{cid:0>12}", "ts": ts, "actor": "joe", "change": kind, "entity_id": eid,
            "reason": kw.pop("reason", "test reason"), **kw}


def tap(n, ts, action, eid=None, **kw):
    rec = {"id": f"lb-{n:0>12}", "ts": ts, "actor": "joe", "action": action}
    if eid:
        rec["entity_id"] = eid
    rec.update(kw)
    return rec


def tempdir():
    return tempfile.mkdtemp(prefix="wartable-test-")
