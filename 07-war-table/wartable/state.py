"""Compose the dashboard's live state from the three layers.

One function, used by both build.py (the static snapshot embedded in the page) and serve.py
(live state after every tap), so the numbers on screen always come from the same code path.
"""
from collections import Counter
from datetime import datetime, timezone

from . import store
from .progression import derive, rank_table, config as prog_config
from .registry import apply_ledger, is_visible
from .signals import freshness, in_spec_window, triage, config as sig_config


def compose(base, data_dir=None, now=None, ledger=None, signals=None, logbook=None):
    now = now or datetime.now(timezone.utc)
    ledger = store.read("ledger", data_dir) if ledger is None else ledger
    signals = store.read("signals", data_dir) if signals is None else signals
    logbook = store.read("logbook", data_dir) if logbook is None else logbook
    scfg, pcfg = sig_config(), prog_config()

    ents, audit = apply_ledger(base, ledger)
    base_by_id = {e["id"]: e for e in base}
    prog = derive(base_by_id, ledger, logbook, signals, pcfg)
    tri = triage(logbook)

    sig_out, orphaned = [], 0
    for s in signals:
        # the signal file is append-only, so a signal can outlive its facility (for example a
        # solar project after solar was excluded). It stays on record but is not shown.
        if s["entity_id"] and s["entity_id"] not in ents:
            orphaned += 1
            continue
        t = tri.get(s["id"], {}).get("status")
        sig_out.append({"id": s["id"], "entity_id": s["entity_id"], "stage": s["stage"], "kind": s["kind"],
                        "headline": s["headline"], "summary": s["summary"], "url": s["url"],
                        "received_at": s["received_at"], "source": s["source"],
                        "generated_by": s["generated_by"]["kind"], "match": s["match"]["confidence"],
                        "fresh": freshness(s, now, scfg), "spec_window": in_spec_window(s, scfg),
                        "triage": t})

    statuses = {eid: e["status"] for eid, e in ents.items() if e["status"]["value"] != "active"}
    added = [e for eid, e in ents.items() if e.get("existence") == "ledger"]
    visible = [e for e in ents.values() if is_visible(e)]

    recent = []
    for ev in sorted(logbook, key=lambda e: e["ts"], reverse=True)[:40]:
        recent.append({k: ev[k] for k in ("id", "ts", "action", "entity_id", "signal_id", "role", "undo_of") if k in ev})

    undone = {e["undo_of"] for e in logbook if e["action"] == "undo"}
    last_tap = {}
    for ev in sorted(logbook, key=lambda e: e["ts"]):
        if ev["action"] in pcfg["action_stage"] and ev["id"] not in undone and ev.get("entity_id"):
            last_tap[ev["entity_id"]] = ev["id"]

    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "statuses": statuses,
        "added_entities": added,
        "stages": prog["stages"],
        "last_tap": last_tap,
        "progression": {"points": prog["points"], "rank": prog["rank"], "clusters": prog["clusters"],
                        "history": prog["history"][-30:]},
        "rank_table": [{"level": l, "title": t, "points": p} for l, t, p in rank_table(pcfg)],
        "signals": sig_out,
        "recent": recent,
        "counts": {
            "entities": len(ents), "visible": len(visible),
            "by_kind": dict(Counter(e["kind"] for e in ents.values())),
            "by_status": dict(Counter(e["status"]["value"] for e in ents.values())),
            "ledger_changes": len(ledger), "signals": len(signals),
            "signals_by_source": dict(Counter(s["source"]["type"] for s in signals)),
            "signals_by_generator": dict(Counter(s["generated_by"]["kind"] for s in signals)),
            "signals_unplaced": sum(1 for s in signals if not s["entity_id"]),
            "signals_orphaned": orphaned,
            "logbook_events": len(logbook),
            "ledger_audit": len(audit),
        },
    }
