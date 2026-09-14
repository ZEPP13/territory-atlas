"""Registry layer: base registry from sources, effective registry = base + Joe's change ledger.

The base is built by the existing, unchanged pipeline — 04-outputs/merge.py for the merge and
05-preview/potential.py for the opportunity model — so the war table cannot drift from the
atlas on any fact about a plant.
"""
import copy
import json
import math
import os
import sys

from . import ROOT, DIST
from .schema import load as load_schema, validate

sys.path.insert(0, os.path.join(ROOT, "04-outputs"))
sys.path.insert(0, os.path.join(ROOT, "05-preview"))

RICHMOND = (37.5407, -77.4360)
HIDDEN_STATUSES = {"defunct", "not_a_fit", "assigned_elsewhere", "duplicate"}
STATUS_FOR_CHANGE = {"mark_defunct": "defunct", "mark_not_a_fit": "not_a_fit",
                     "mark_assigned_elsewhere": "assigned_elsewhere", "mark_duplicate": "duplicate"}
CORRECTABLE = {"name", "lat", "lon", "subindustry", "parent"}
BASE_PATH = os.path.join(DIST, "registry_base.json")


class LedgerError(Exception):
    pass


def miles_from_richmond(lat, lon):
    dy = (lat - RICHMOND[0]) * 69.0
    dx = (lon - RICHMOND[1]) * 69.0 * math.cos(math.radians(37.5))
    return round(math.hypot(dx, dy), 1)


def entity_from_record(r, source_labels):
    """The merged/assessed site record -> the registry entity contract."""
    return {
        "id": r["id"], "kind": "facility", "name": r["name"],
        "parent": r.get("parent") or "", "operator": r.get("operator") or "",
        "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
        "jurisdiction": r["jurisdiction"], "cluster": r["cluster"], "band": int(r["band"]),
        "miles": miles_from_richmond(r["lat"], r["lon"]), "scope": r["scope"],
        "family": r["family"], "sector": r.get("sector") or "", "subindustry": r.get("subindustry") or "",
        "note": r.get("note") or "", "existence": r.get("existence") or "registry",
        "address": r.get("address") or "", "city": r.get("city") or "",
        "potential": {
            "band": r["potential"], "score": r["potential_score"],
            "factors": {k: float(v) for k, v in r["factors"].items()},
            "reasons": r["reasons"], "scale_verified": bool(r["scale_verified"]),
            "scale_text": r["scale_text"], "verified_facts": r["verified_facts"],
            "apps_verified": r["apps_verified"],
            "subtype": r.get("power_subtype"),
        },
        "confidence": {"k": r["confidence_new"]["k"], "label": r["confidence_new"]["label"],
                       "why": r["confidence_new"]["why"]},
        "timing": {"k": r["timing"]["k"], "label": r["timing"]["label"], "why": r["timing"].get("why") or ""},
        "facts": {
            "employees": int(r.get("employees") or 0), "sqft": int(r.get("sqft") or 0),
            "mw": float(r.get("mw") or 0), "fuel": r.get("fuel") or "",
            "gen_mwh": (float(r.get("gen_mwh") or 0) if r.get("mw") else None),
            "cogen": bool(r.get("cogen")),
        },
        "sources": [{"label": source_labels.get(s, (s, s, ""))[0], "what": source_labels.get(s, (s, s, ""))[1],
                     "as_of": source_labels.get(s, (s, s, ""))[2]} for s in (r.get("sources") or [])],
        "flags": r["flags"],
        "status": {"value": "active", "change_id": None, "reason": None, "duplicate_of": None, "since": None},
    }


def build_base():
    """Run the merge + opportunity model and return validated base entities."""
    from merge import load
    from potential import assess, near_duplicates
    from palette import SOURCE_LABELS
    from ids import make_ids_unique
    rows, _ = load()
    make_ids_unique(rows)
    near_duplicates(rows)
    for r in rows:
        assess(r)
    schema = load_schema("entity")
    entities, problems = [], []
    for r in rows:
        e = entity_from_record(r, SOURCE_LABELS)
        errs = validate(e, schema)
        if errs:
            problems.append(f"{e['id']}: {'; '.join(errs[:3])}")
        entities.append(e)
    if problems:
        raise ValueError(f"{len(problems)} registry entities fail the schema, first: {problems[:3]}")
    ids = [e["id"] for e in entities]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate entity ids in the base registry")
    return entities


def save_base(entities, path=BASE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(entities, fh, separators=(",", ":"), sort_keys=True)


def load_base(path=BASE_PATH):
    with open(path) as fh:
        return json.load(fh)


def check_change(change, known_ids):
    """Semantics the schema cannot express. Raises LedgerError with a plain explanation."""
    c = change["change"]
    if c == "add_entity":
        if change["entity_id"] in known_ids:
            raise LedgerError(f"add_entity: {change['entity_id']} already exists")
        ent = change.get("entity")
        if not isinstance(ent, dict) or ent.get("id") != change["entity_id"]:
            raise LedgerError("add_entity: 'entity' must be an object whose id matches entity_id")
        errs = validate(ent, load_schema("entity"))
        if errs:
            raise LedgerError("add_entity: entity fails the schema: " + "; ".join(errs[:3]))
        return
    if change["entity_id"] not in known_ids:
        raise LedgerError(f"{c}: unknown entity {change['entity_id']}")
    if c == "mark_duplicate":
        target = change.get("duplicate_of")
        if not target or target not in known_ids:
            raise LedgerError("mark_duplicate needs duplicate_of naming an existing entity")
        if target == change["entity_id"]:
            raise LedgerError("mark_duplicate: an entity cannot duplicate itself")
    if c == "correct":
        if change.get("field") not in CORRECTABLE or "value" not in change:
            raise LedgerError(f"correct needs field in {sorted(CORRECTABLE)} and a value")
        if change["field"] in ("lat", "lon") and not isinstance(change["value"], (int, float)):
            raise LedgerError("correct: lat/lon must be numbers")


def apply_ledger(base, changes):
    """Effective registry. Changes apply in timestamp order; the latest status change wins.

    Returns (entities_by_id, audit) where audit lists what each change did."""
    ents = {e["id"]: copy.deepcopy(e) for e in base}
    audit = []
    # stable sort: records with the same timestamp keep their append order in the file
    for ch in sorted(changes, key=lambda c: c["ts"]):
        check_change(ch, ents.keys())
        c, eid = ch["change"], ch["entity_id"]
        if c == "add_entity":
            ent = copy.deepcopy(ch["entity"])
            ent["existence"] = "ledger"
            ents[eid] = ent
            audit.append((ch["id"], eid, "added"))
        elif c in STATUS_FOR_CHANGE:
            ents[eid]["status"] = {"value": STATUS_FOR_CHANGE[c], "change_id": ch["id"], "reason": ch["reason"],
                                   "duplicate_of": ch.get("duplicate_of"), "since": ch["ts"]}
            audit.append((ch["id"], eid, STATUS_FOR_CHANGE[c]))
        elif c == "reinstate":
            ents[eid]["status"] = {"value": "active", "change_id": ch["id"], "reason": ch["reason"],
                                   "duplicate_of": None, "since": ch["ts"]}
            audit.append((ch["id"], eid, "reinstated"))
        elif c == "correct":
            ents[eid][ch["field"]] = ch["value"]
            if ch["field"] in ("lat", "lon"):
                ents[eid]["miles"] = miles_from_richmond(ents[eid]["lat"], ents[eid]["lon"])
            audit.append((ch["id"], eid, f"corrected {ch['field']}"))
    # a duplicate chain must end at an active or hidden-but-real entity, never loop
    for eid, e in ents.items():
        seen, cur = {eid}, e
        while cur["status"]["value"] == "duplicate":
            nxt = cur["status"]["duplicate_of"]
            if nxt in seen:
                raise LedgerError(f"duplicate chain loops at {nxt}")
            seen.add(nxt)
            cur = ents[nxt]
    return ents, audit


def resolve(ents, eid):
    """Follow duplicate_of to the entity that engagement should count toward."""
    cur = ents[eid]
    while cur["status"]["value"] == "duplicate":
        cur = ents[cur["status"]["duplicate_of"]]
    return cur["id"]


def is_visible(e):
    """Shown on the default map: in portfolio and not retired by the ledger."""
    return e["scope"] == "core" and e["status"]["value"] not in HIDDEN_STATUSES
