"""Signal layer: the fast-moving record of things that happened.

Source-agnostic by contract (schemas/signal.schema.json). Today the only adapter turns the
project statuses already inside the Industrial Info export into `registry_snapshot` signals.
Web, trade-press and enterprise adapters produce the same record shape later.
"""
import json
import os
from datetime import datetime, timezone

from . import CONFIG

STAGE_FOR_TIMING = {"construction": "construction", "expansion": "construction",
                    "proposed": "announced", "hold": "on_hold"}
KIND_FOR_TIMING = {"construction": "project_status", "expansion": "expansion",
                   "proposed": "project_status", "hold": "project_status"}


def config():
    with open(os.path.join(CONFIG, "signals.json")) as fh:
        return json.load(fh)


def parse_ts(s):
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def seed_from_registry(base, cfg=None):
    """Adapter: registry snapshot -> signals. Deterministic ids, so re-running never duplicates."""
    cfg = cfg or config()
    snap = cfg["registry_snapshot"]
    out = []
    for e in base:
        t = (e.get("timing") or {}).get("k")
        if e["scope"] != "core" or t not in STAGE_FOR_TIMING:
            continue
        label = e["timing"]["label"]
        out.append({
            "id": f"sig-snap-{e['id']}-{t}",
            "received_at": f"{snap['as_of']}T00:00:00Z",
            "published_at": None,
            "kind": KIND_FOR_TIMING[t],
            "stage": STAGE_FOR_TIMING[t],
            "headline": f"{e['name']}: {label.lower()}"[:200],
            "summary": (f"The {snap['name']} dated {snap['as_of']} lists this project as "
                        f"{label.lower()}. This is the status recorded in that file, not a news report."),
            "url": None,
            "source": {"type": "registry_snapshot", "name": snap["name"], "as_of": snap["as_of"]},
            "entity_id": e["id"],
            "match": {"method": "exact_id", "confidence": "high",
                      "reason": "Status field on the registry record itself."},
            "generated_by": {"kind": "rule", "detail": "07-war-table/wartable/signals.py seed_from_registry"},
        })
    return out


def freshness(sig, now, cfg=None):
    """1.0 = just arrived, 0.0 = no longer fresh. Snapshots never glow (see config note)."""
    cfg = cfg or config()
    if sig["source"]["type"] not in cfg["fresh_source_types"]:
        return 0.0
    hours = (now - parse_ts(sig["received_at"])).total_seconds() / 3600
    bright, fade = cfg["freshness"]["bright_hours"], cfg["freshness"]["fade_days"] * 24
    if hours < 0:
        return 1.0
    if hours <= bright:
        return 1.0
    if hours >= fade:
        return 0.0
    return round(1 - (hours - bright) / (fade - bright), 3)


def in_spec_window(sig, cfg=None):
    cfg = cfg or config()
    return sig.get("stage") in cfg["spec_window"]


def triage(logbook):
    """Latest triage action per signal: reviewed / pinned / dismissed."""
    state = {}
    for ev in sorted(logbook, key=lambda e: e["ts"]):
        if ev["action"].startswith("signal_") and ev.get("signal_id"):
            state[ev["signal_id"]] = {"status": ev["action"][7:], "ts": ev["ts"], "event_id": ev["id"]}
    return state
