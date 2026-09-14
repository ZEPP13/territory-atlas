#!/usr/bin/env python3
"""Stable, unique record ids.

Bug found 2026-09-13 by the war table's schema/uniqueness checks: the DEQ and EPA registry
importers built ids from the first ten letters of a facility's name, so different real
facilities collided. 119 records shared 49 ids (six separate Microsoft data centers were all
`C9-DEQ-MICROSOFTC`). Any page that looked a record up by id could show the wrong facility.

The source files are left untouched. Colliding ids are made unique here, deterministically:
  * the Virginia DEQ registration number when the record has one (the state's own permanent id)
  * otherwise a short fingerprint of name + coordinates to 4 decimals (~11 m)
Records whose id was already unique keep it exactly, so nothing that references them changes.
"""
import hashlib
from collections import Counter, defaultdict


def make_ids_unique(rows):
    counts = Counter(r["id"] for r in rows)
    renamed = []
    for r in rows:
        if counts[r["id"]] < 2:
            continue
        old = r["id"]
        if r.get("deq_reg"):
            suffix = str(r["deq_reg"])
        else:
            key = f"{r['name']}|{r['lat']:.4f}|{r['lon']:.4f}"
            suffix = hashlib.sha1(key.encode()).hexdigest()[:6]
        r["id"] = f"{old}-{suffix}"
        renamed.append((old, r["id"]))
    # last resort for records identical in name and position: numbered in their existing order
    groups = defaultdict(list)
    for r in rows:
        groups[r["id"]].append(r)
    for rid, members in groups.items():
        if len(members) > 1:
            for n, r in enumerate(members[1:], 2):
                r["id"] = f"{rid}-{n}"
                renamed.append((rid, r["id"]))
    final = Counter(r["id"] for r in rows)
    dup = [k for k, v in final.items() if v > 1]
    if dup:
        raise ValueError(f"ids still not unique after repair: {dup[:5]}")
    return renamed
