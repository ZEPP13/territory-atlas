#!/usr/bin/env python3
"""Explainable flow-opportunity potential.

Replaces the Flexim-first strategic-weight ranking. Four things are assessed, and
three things that used to be tangled into the same number are now kept apart:

    POTENTIAL  = what the plant is, and how much flow measurement its operation implies
    TIMING     = whether something is happening there in the near term
    ACCESS     = how expensive it is to cover commercially
    CONFIDENCE = how good the read is

Potential is built from four factors, each 0-3, each with a stated reason:

    A  industry process intensity          weight 30
    B  industry-appropriate plant scale     weight 30
    C  breadth and criticality of need      weight 20
    D  verified plant-fact uplift           weight 20

The authoritative values are WEIGHTS below; the atlas renders the split from that dict
rather than from a hard-coded string, so the two cannot drift apart.

Rules this model is built to obey:
  * Missing information is not zero opportunity. When a plant-scale figure is absent the
    industry-typical value is used, the fact is labelled an assumption, and CONFIDENCE
    drops — POTENTIAL does not.
  * Employee count and floor area do not mean the same thing across industries. Each
    industry names its own scale metric and its own bands (industry.PROFILES).
  * Verified plant facts and industry-derived assumptions are never merged. Factor D can
    only be raised by something a source actually reported about this plant.
  * "Insufficient information" is a real answer and is reported as its own band, distinct
    from "Low".
"""
import re
from industry import family_of, profile_of, APPS, TECH, LOW_FLOW_SECTORS, POWER_SUBTYPES

WEIGHTS = {"intensity": 30, "scale": 30, "breadth": 20, "verified": 20}
BANDS = [("High", 68), ("Medium", 46), ("Low", 0)]

# Calibration note. The weights put industry and plant scale on equal footing, so a big
# plant in a moderate industry and a small plant in an intense one land near each other,
# which is the intended behaviour. The bands are set so that industry characteristics
# ALONE cannot reach High: the most fluid-intensive industry in the taxonomy, with no
# plant-scale figure and no verified operating fact, scores 65 and lands in Medium.
# Reaching High takes either a reported large plant scale or independently filed
# operating facts. That is deliberate — it stops the model from rewarding a record for
# belonging to a good industry when nothing is known about the plant itself.

# Names that describe a group of plants rather than one plant. These came out of the
# early recall sweep and must not be ranked as if they were a single site.
PLACEHOLDER_RX = re.compile(
    r"\b(plants|systems|facilities|campuses|central (utility )?plants|"
    r"secondary sites|area\b.*plants|regional campus)\b", re.I)

BAND_RANK = {"High": 2, "Medium": 1, "Low": 0}

SIZE_FOR_BAND = {"High": 4, "Medium": 3, "Low": 2, "Insufficient information": 1}


_TOKEN_RX = re.compile(r"[A-Za-z0-9]{4,}")
_STOP = {"plant", "mill", "works", "corp", "company", "incorporated", "center", "centre",
         "data", "facility", "systems", "group", "services", "virginia", "station"}

def _name_echo(r):
    """Do the co-located record names share a distinctive word with this one?"""
    def toks(n):
        return {t.lower() for t in _TOKEN_RX.findall(n or "")} - _STOP
    mine = toks(r.get("name"))
    if not mine:
        return False
    for other in r.get("colocated") or []:
        o = toks(other)
        if o and len(mine & o) / len(mine | o) >= 0.3:
            return True
    return False


def _fuel_text(r):
    """Recorded fuel only: the eGRID fuel field and Industrial Info's 'fuel: X' note entry.
    Free-text notes are not used; they mention neighbouring landfills, former fuels, etc."""
    parts = [r.get("fuel") or ""]
    m = re.search(r"fuel:\s*([^|]+)", r.get("note") or "", re.I)
    if m:
        parts.append(m.group(1))
    return " ".join(parts).lower()


def power_subtype(r):
    """Classify a generating plant from its name, recorded fuel, and eGRID duty.
    Order matters: fuel and plant type first, then how much it runs, then size."""
    name, fuel = (r.get("name") or "").lower(), _fuel_text(r)
    mw, gen = r.get("mw") or 0, r.get("gen_mwh")
    cf = (gen / (mw * 8760)) if mw and gen is not None else None
    if re.search(r"landfill|\blfg\b|gas.to.energy", name) or "landfill" in fuel:
        return "landfill_gas", cf
    if "hydro" in name or "hydro" in fuel or fuel.strip() == "water":
        return "hydro", cf
    if (re.search(r"nuclear|coal|biomass|black liquor|municipal|wood|refuse", fuel)
            or re.search(r"nuclear|cogen|resource recovery|biomass", name) or r.get("cogen")):
        return "steam", cf
    if re.search(r"combustion turbine|peaking|peaker|\bct\b|combustion station", name) or (cf is not None and cf < 0.10):
        return "peaker", cf
    if not mw and (r.get("employees") or 0) <= 5:
        return "small_unit", cf
    return "thermal", cf


def _scale_read(r, prof):
    """Return (score 0-3, verified?, human sentence). Bands are the industry's own."""
    metric, small, big = prof["scale"]
    val = r.get(metric) or 0
    unit = {"employees": "employees", "sqft": "sq ft of floor area", "mw": "MW nameplate"}[metric]
    if not val:
        # no figure for this plant: fall back to industry-typical, say so, do not penalise
        return 1.5, False, (
            f"No {unit} reported for this plant, so an industry-typical mid-size {unit} "
            f"figure is assumed. @note")
    fmt = f"{val:,.0f}"
    if val >= big:
        return 3.0, True, (f"Large for this industry — {fmt} {unit}, against an industry "
                           f"large-plant threshold of {big:,}. @note")
    if val >= small:
        return 2.0, True, (f"Mid-size for this industry — {fmt} {unit}, between the {small:,} "
                           f"and {big:,} industry bands. @note")
    return 1.0, True, (f"Small for this industry — {fmt} {unit}, below the {small:,} industry "
                       f"threshold. @note")


def _verified_facts(r):
    """Only things a named source reported about THIS plant. Returns (0-3, [facts])."""
    f, pts = [], 0.0
    if r.get("mw"):
        gen = r.get("gen_mwh") or 0
        if gen:
            cf = gen / (r["mw"] * 8760)
            f.append(f"EPA eGRID 2023: {r['mw']:,.0f} MW nameplate, {gen:,.0f} MWh generated in 2023 "
                     f"({cf:.0%} of the year at full output).")
            pts += 1.5
        else:
            f.append(f"EPA eGRID 2023: {r['mw']:,.0f} MW nameplate but ZERO generation reported in "
                     f"2023 — idle or retired. Confirm before spending a visit on it.")
    if r.get("cogen"):
        f.append("Industrial Info records on-site cogeneration — implies a full steam header, "
                 "feedwater and condensate cycle.")
        pts += 1.0
    if r.get("onsite_gen_mw"):
        f.append(f"EPA eGRID 2023 places {r['onsite_gen_mw']:,.0f} MW of {r.get('onsite_gen_fuel','')} "
                 f"generation on this site.")
        pts += 1.0
    srcs = set(r.get("sources") or [])
    if "GHGRP 2023" in srcs:
        f.append("Reports to the EPA Greenhouse Gas Reporting Program — combustion above the "
                 "25,000 tCO2e threshold, so a substantial fuel and steam system.")
        pts += 0.75
    if "TRI 2024" in srcs:
        f.append("Files an EPA Toxics Release Inventory report — the plant handles listed "
                 "chemicals in quantity, which implies real process-liquid measurement.")
        pts += 0.75
    dq = (r.get("deq_class") or "")
    if dq and re.search(r"major|title\s*v", dq, re.I):
        f.append(f"Virginia DEQ classifies this as a major air source ({dq}).")
        pts += 0.75
    elif dq:
        f.append(f"Virginia DEQ air permit on file ({dq}).")
        pts += 0.25
    if r.get("sqft") and r.get("employees"):
        f.append(f"Industrial Info reports {r['employees']:,} employees across "
                 f"{r['sqft']:,} sq ft.")
        pts += 0.25
    return min(3.0, pts), f


def apps_verified(r, prof):
    """Which of the industry's typical applications a VERIFIED plant fact actually implies.
    The full application list lives once per family (see family_catalog); only this short
    list of exceptions is stored per record."""
    keys, out = set(prof["apps"]), set()
    if r.get("cogen") or r.get("mw") or r.get("onsite_gen_mw"):
        out |= {k for k in ("steam_header", "bfw", "cond_return", "fuel_gas") if k in keys}
    if "TRI 2024" in (r.get("sources") or []):
        out |= {k for k in ("process_liquid", "corrosive", "effluent") if k in keys}
    return sorted(out)


def family_catalog(family):
    """Everything that is true of an industry rather than of a plant, emitted once."""
    prof = profile_of(family)
    apps = [{"k": k, "label": APPS[k][0], "why": APPS[k][1], "tech": APPS[k][2]}
            for k in prof["apps"]]
    weight = {}
    for a in apps:
        for i, t in enumerate(a["tech"]):
            weight[t] = weight.get(t, 0) + (2 if i == 0 else 1)
    order = sorted(weight, key=lambda t: -weight[t])
    return {
        "why": prof["why"], "scale_note": prof["scale_note"],
        "scale_metric": prof["scale"][0], "scale_bands": list(prof["scale"][1:]),
        "intensity": prof["intensity"], "breadth": prof["breadth"],
        "apps": apps, "ask": prof["ask"], "tech_fit": order,
        "tech_detail": [{"k": t, "name": TECH[t][0], "line": TECH[t][1], "why": TECH[t][2],
                         "apps": [a["label"] for a in apps if t in a["tech"]][:4]} for t in order],
    }


def near_duplicates(rows, max_miles=1.2, min_jaccard=0.55, min_shared=2):
    """Flag records that are probably the same plant listed twice.

    The merge already folds together anything co-located AND name-matched. What it will
    not do is guess, so a plant that two sources place 1-2 miles apart under slightly
    different names survives as two records. That is the right call for a merge and the
    wrong answer for a call list, so those pairs are flagged here instead — surfaced for
    a human, never deleted."""
    import math
    # Place names are not distinguishing. "Sterling Data Center Building A" and "Sterling
    # Data Center IAD-128" share only the town, and are two different buildings. Strip
    # every town and jurisdiction name that appears anywhere in the data, then require at
    # least two remaining words in common.
    place = set()
    for r in rows:
        for fld in (r.get("city"), r.get("jurisdiction")):
            for t in _TOKEN_RX.findall(fld or ""):
                place.add(t.lower())
    stop = _STOP | place

    def toks(n):
        return {t.lower() for t in _TOKEN_RX.findall(n or "")} - stop

    # How distinguishing is a word? "Data", "Sterling" and "Terminal" appear everywhere and
    # prove nothing; "Advansix" appears twice and proves a great deal. Two common words in
    # common is evidence; ONE rare word in common is better evidence than either.
    df = {}
    for r in rows:
        for t in toks(r.get("name")):
            df[t] = df.get(t, 0) + 1
    RARE = 4

    by_j = {}
    for r in rows:
        r["_dupes"] = []
        by_j.setdefault(r.get("jurisdiction"), []).append(r)
    for group in by_j.values():
        for i, a in enumerate(group):
            ta = toks(a["name"])
            if not ta:
                continue
            for b in group[i + 1:]:
                tb = toks(b["name"])
                if not tb:
                    continue
                shared = ta & tb
                if not shared:
                    continue
                rare = any(df.get(t, 99) <= RARE for t in shared)
                if not rare and len(shared) < min_shared:
                    continue
                if len(shared) / len(ta | tb) < min_jaccard:
                    continue
                dy = (a["lat"] - b["lat"]) * 69.0
                dx = (a["lon"] - b["lon"]) * 69.0 * math.cos(math.radians(37.7))
                if math.hypot(dx, dy) > max_miles:
                    continue
                a["_dupes"].append(b["name"])
                b["_dupes"].append(a["name"])
    return rows


def assess(r):
    """Attach the potential model to one merged site record, in place."""
    fam = family_of(r.get("sector") or "")
    prof = profile_of(fam)
    r["family"] = fam
    r["subindustry"] = r.get("subsector") or r.get("sector") or ""

    # ---- review flags (never auto-deleted; surfaced for a human decision) ----
    flags = []
    if PLACEHOLDER_RX.search(r.get("name") or ""):
        flags.append(("placeholder", "The name describes a group of plants rather than one plant. "
                                     "It is a Pass-1 aggregate that needs splitting into real sites."))
    if r.get("_dupes"):
        flags.append(("dupe", "Very likely the same plant as "
                      + " and ".join(f'"{n}"' for n in r["_dupes"][:3])
                      + ". The names match closely and they sit within three miles of each "
                        "other, but the merge refuses to guess. Reconcile before calling."))
    if r.get("colocated"):
        if _name_echo(r) and not r.get("_dupes"):
            flags.append(("dupe", f"Shares a location with {len(r['colocated'])} other record(s) and "
                                  "the names overlap. Likely the same plant listed twice under "
                                  "different source spellings — reconcile before calling."))
        else:
            flags.append(("shared_site", f"Shares a location with {len(r['colocated'])} other "
                                         "record(s) whose names do not overlap. Most likely a "
                                         "genuine multi-tenant industrial site."))
    if (r.get("sector") or "") in LOW_FLOW_SECTORS:
        flags.append(("low_flow", "This whole category carries little or no process fluid. Flagged "
                                  "as a block for a keep-or-drop decision, not removed."))
    if r.get("existence") == "recall":
        flags.append(("unverified", "Named from unverified research only. No registry source "
                                    "confirms this facility exists. Verify before calling."))
    r["flags"] = [{"k": k, "why": w} for k, w in flags]

    # ---- factors ----
    A = float(prof["intensity"])
    B, b_ver, b_txt = _scale_read(r, prof)
    C = float(prof["breadth"])
    D, dfacts = _verified_facts(r)

    subtype = None
    if (r.get("sector") or "") == "power-generation":
        subtype, _cf = power_subtype(r)
        A = float(POWER_SUBTYPES[subtype]["intensity"])
        C = float(POWER_SUBTYPES[subtype]["breadth"])

    # a solar farm or a warehouse is not a chemical plant, whatever family it sits in
    if (r.get("sector") or "") in LOW_FLOW_SECTORS:
        A = min(A, 0.5); C = min(C, 0.5)

    score = sum(WEIGHTS[k] * v / 3.0 for k, v in
                (("intensity", A), ("scale", B), ("breadth", C), ("verified", D)))
    r["potential_score"] = round(score, 1)
    r["power_subtype"] = subtype
    r["factors"] = {"intensity": A, "scale": B, "breadth": C, "verified": D}
    r["scale_verified"] = b_ver
    r["scale_text"] = b_txt
    r["verified_facts"] = dfacts

    insufficient = (
        any(f[0] == "placeholder" for f in flags) or
        (fam == "other-mfg" and not r.get("employees") and not r.get("sqft")
         and not dfacts and not (r.get("subsector") or "").strip()))
    if insufficient:
        r["potential"] = "Insufficient information"
    else:
        r["potential"] = next(b for b, t in BANDS if score >= t)
    # Some plant types have a ceiling. Nameplate size and EPA filings prove a peaking plant is
    # big; they do not give it a steam cycle. The score is kept and shown; only the band is capped.
    cap = POWER_SUBTYPES[subtype].get("max_band") if subtype else None
    r["potential_capped"] = False
    if cap and r["potential"] in BAND_RANK and BAND_RANK[r["potential"]] > BAND_RANK[cap]:
        r["potential"], r["potential_capped"] = cap, True
    r["marker_size"] = SIZE_FOR_BAND[r["potential"]]

    # ---- reasons: the 2-3 things that actually drove the band ----
    lead = "@why"
    if subtype:
        lead = f"{POWER_SUBTYPES[subtype]['label']}. {POWER_SUBTYPES[subtype]['why']}"
        if r["potential_capped"]:
            lead += (f" Rated {r['potential']} at most for this plant type, although its score is "
                     f"{r['potential_score']}.")
    reasons = [lead]
    reasons.append(b_txt)
    if dfacts:
        reasons.append(dfacts[0])
    elif r["potential"] != "Insufficient information":
        reasons.append("No plant-specific operating facts were reported by any source, so this "
                       "rating rests on industry characteristics alone.")
    if r["potential"] == "Insufficient information":
        reasons = [next((w for k, w in flags if k == "placeholder"),
                        "Too little is known about what this site does to place it in an "
                        "industry, let alone rate it."),
                   "Shown at the smallest marker size. This is not a judgement that the site is "
                   "worth nothing — it is a judgement that the data cannot yet say."]
    r["reasons"] = reasons[:3]

    # ---- applications: only the per-plant exceptions are stored here ----
    r["apps_verified"] = apps_verified(r, prof)

    # ---- the separate axes ----
    r["timing"] = _timing(r)
    r["confidence_new"] = _confidence(r, fam, b_ver, dfacts)
    return r


def _timing(r):
    s = (r.get("iir_status") or "").lower()
    raw = (r.get("status") or "")
    if r.get("mw") and (r.get("gen_mwh") or 0) == 0:
        return {"k": "idle", "label": "Idle or retired",
                "why": "eGRID reports zero 2023 generation against a live nameplate capacity."}
    if s in ("under construction",):
        return {"k": "construction", "label": "Under construction",
                "why": "Industrial Info has this as an active build. Instrument standards get set now."}
    if s in ("proposed",):
        return {"k": "proposed", "label": "Proposed",
                "why": "Announced but not committed. Worth spec influence, not a forecast."}
    if s in ("on hold",):
        return {"k": "hold", "label": "On hold",
                "why": "Project paused. Keep warm; these restart."}
    if s in ("expansion",):
        return {"k": "expansion", "label": "Expansion under way",
                "why": "Existing plant adding capacity — brownfield work with a live budget."}
    if re.search(r"verify", raw, re.I):
        return {"k": "verify", "label": "Operating status unconfirmed", "why": raw}
    if s == "operating" or "operating" in raw.lower():
        return {"k": "operating", "label": "Operating", "why": raw or "Reported as operating."}
    return {"k": "unknown", "label": "Operating status not established",
            "why": "The source proves the facility exists but says nothing current about whether "
                   "it is running."}


def _confidence(r, fam, scale_verified, dfacts):
    if r.get("existence") == "recall":
        return {"k": "low", "label": "Low",
                "why": "Unverified research only — no registry source confirms the facility."}
    strong = scale_verified and bool(r.get("subsector"))
    if strong and dfacts:
        return {"k": "high", "label": "High",
                "why": "A named registry lists this plant, its subindustry is known, a plant-scale "
                       "figure is reported, and at least one operating fact is independently filed."}
    if strong or dfacts:
        return {"k": "medium", "label": "Medium",
                "why": "A named registry lists this plant, but part of the read — scale or operating "
                       "detail — is inferred from the industry rather than reported."}
    return {"k": "low", "label": "Low",
            "why": "The facility is listed by a registry, but nothing about its scale or operation "
                   "is reported, so the rating is industry-derived throughout."}
