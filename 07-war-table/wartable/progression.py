"""Charting progression: stages, points and rank, derived from the logbook. Never stored.

Deterministic and replayable. Events are processed in time order against the registry as it
stood at that moment, so:
  * points already earned are kept when an entity is later retired (ranks do not go down),
  * cluster milestones, once reached, stay reached,
  * an `undo` removes the undone tap from history entirely (a correction, not a penalty),
  * each tap is weighted by the opportunity rating recorded when it was made, so re-scoring a
    facility later never changes points already earned.
Every number here comes from config/progression.json.
"""
import json
import os

from . import CONFIG
from .registry import resolve, STATUS_FOR_CHANGE
from .signals import parse_ts


def config():
    with open(os.path.join(CONFIG, "progression.json")) as fh:
        return json.load(fh)


def rank_table(cfg=None):
    """[(level, title, min_points)], level 1 = first rank. Strictly increasing thresholds."""
    cfg = cfg or config()
    r = cfg["ranks"]
    titles = [f"{n} {g}" for n in r["names"] for g in r["grades"]] + [r["final"]]
    top, exp, step = r["curve"]["top_points"], r["curve"]["exponent"], r["curve"]["round_to"]
    last = len(titles) - 1
    table = []
    for i, title in enumerate(titles):
        pts = 0 if i == 0 else int(round(top * (i / last) ** exp / step) * step)
        if table and pts <= table[-1][2]:
            pts = table[-1][2] + step
        table.append((i + 1, title, pts))
    return table


def rank_for(points, cfg=None):
    table = rank_table(cfg)
    cur = table[0]
    for row in table:
        if points >= row[2]:
            cur = row
    nxt = next((row for row in table if row[2] > points), None)
    return {"level": cur[0], "title": cur[1], "floor": cur[2], "points": points,
            "next_title": nxt[1] if nxt else None, "next_at": nxt[2] if nxt else None,
            "levels": len(table)}


def _weight(entity, cfg, band_at_tap=None):
    """Points multiplier. A tap carries the rating it was earned under; older taps without one
    fall back to the entity's current rating."""
    if entity["kind"] == "facility":
        band = band_at_tap or (entity.get("potential") or {}).get("band")
        return cfg["opportunity_weight"].get(band, 1)
    return cfg["kind_weight"].get(entity["kind"], 1)


def derive(base_ents, ledger, logbook, signals, cfg=None):
    """Full progression state. base_ents: dict id -> entity BEFORE ledger (history is replayed)."""
    import copy
    cfg = cfg or config()
    stage_ids = [s["id"] for s in cfg["stages"]]
    stage_pts = {s["id"]: s["points"] for s in cfg["stages"]}
    rank_of = {s: i for i, s in enumerate(stage_ids)}

    undone = {e["undo_of"] for e in logbook if e["action"] == "undo" and e.get("undo_of")}
    events = [e for e in logbook if e["id"] not in undone and e["action"] != "undo"]
    stream = ([("ledger", c["ts"], i, c) for i, c in enumerate(ledger)] +
              [("log", e["ts"], i, e) for i, e in enumerate(events)])
    # same timestamp: ledger first, then append order within each file
    stream.sort(key=lambda s: (s[1], 0 if s[0] == "ledger" else 1, s[2]))

    ents = {k: copy.deepcopy(v) for k, v in base_ents.items()}
    stage = {}                     # entity id -> stage id (after duplicate resolution)
    earned = {}                    # entity id -> points earned (sticky)
    by_stage_pts = {s: 0 for s in stage_ids}
    milestones = {}                # cluster -> set of shares reached (sticky)
    milestone_pts = 0
    sig_by_id = {s["id"]: s for s in signals}
    reviewed, review_pts = set(), 0
    history = []

    def cluster_share(cluster):
        pool = [e for e in ents.values() if e["kind"] == "facility" and e["cluster"] == cluster
                and e["scope"] == "core" and e["status"]["value"] == "active"]
        if not pool:
            return 0.0
        done = sum(1 for e in pool if rank_of.get(stage.get(e["id"], "uncharted"), 0) >= 1)
        return done / len(pool)

    for kind, ts, _, rec in stream:
        if kind == "ledger":
            c = rec["change"]
            if c == "add_entity":
                ent = copy.deepcopy(rec["entity"]); ent["existence"] = "ledger"; ents[rec["entity_id"]] = ent
            elif rec["entity_id"] in ents:
                e = ents[rec["entity_id"]]
                if c in STATUS_FOR_CHANGE:
                    e["status"] = {"value": STATUS_FOR_CHANGE[c], "change_id": rec["id"], "reason": rec["reason"],
                                   "duplicate_of": rec.get("duplicate_of"), "since": ts}
                    if c == "mark_duplicate" and rec["entity_id"] in stage:
                        tgt = resolve(ents, rec["entity_id"])
                        s_old = stage.pop(rec["entity_id"])
                        if rank_of[s_old] > rank_of.get(stage.get(tgt, "uncharted"), 0):
                            stage[tgt] = s_old
                elif c == "reinstate":
                    e["status"] = {"value": "active", "change_id": rec["id"], "reason": rec["reason"],
                                   "duplicate_of": None, "since": ts}
            continue
        act = rec["action"]
        if act.startswith("signal_"):
            sig = sig_by_id.get(rec.get("signal_id"))
            if act == "signal_reviewed" and sig and sig["id"] not in reviewed:
                reviewed.add(sig["id"])
                age = (parse_ts(ts) - parse_ts(sig["received_at"])).total_seconds() / 86400
                if 0 <= age <= cfg["signal_review"]["within_days"]:
                    review_pts += cfg["signal_review"]["points"]
            continue
        eid = rec.get("entity_id")
        if eid not in ents:
            continue
        tgt = resolve(ents, eid)
        new_stage = cfg["action_stage"][act]
        old_stage = stage.get(tgt, "uncharted")
        if rank_of[new_stage] <= rank_of[old_stage]:
            continue
        stage[tgt] = new_stage
        w = _weight(ents[tgt], cfg, rec.get("band"))
        gained = 0
        for s in stage_ids[rank_of[old_stage] + 1: rank_of[new_stage] + 1]:
            gained += stage_pts[s] * w
            by_stage_pts[s] += stage_pts[s] * w
        earned[tgt] = earned.get(tgt, 0) + gained
        history.append({"ts": ts, "entity_id": tgt, "stage": new_stage, "points": gained})
        cl = ents[tgt]["cluster"]
        share = cluster_share(cl)
        for m in cfg["cluster_milestones"]:
            if share >= m["share"] and m["share"] not in milestones.setdefault(cl, set()):
                milestones[cl].add(m["share"])
                milestone_pts += m["points"]
                history.append({"ts": ts, "cluster": cl, "milestone": m["share"], "points": m["points"]})

    total = sum(earned.values()) + milestone_pts + review_pts
    clusters = {}
    for cl in sorted({e["cluster"] for e in ents.values()}, key=lambda c: int(c[1:])):
        pool = [e for e in ents.values() if e["kind"] == "facility" and e["cluster"] == cl
                and e["scope"] == "core" and e["status"]["value"] == "active"]
        counts = {s: 0 for s in stage_ids}
        for e in pool:
            counts[stage.get(e["id"], "uncharted")] += 1
        n = len(pool)
        clusters[cl] = {"entities": n, "stages": counts,
                        "surveyed_share": round((n - counts["uncharted"]) / n, 4) if n else 0.0,
                        "milestones": sorted(milestones.get(cl, set()))}
    return {
        "stages": stage,
        "points": {"total": total, "by_stage": by_stage_pts, "milestones": milestone_pts,
                   "signal_reviews": review_pts},
        "rank": rank_for(total, cfg),
        "clusters": clusters,
        "history": history[-200:],
    }
