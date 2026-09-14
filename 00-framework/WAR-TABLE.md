# Eastern Virginia Flow War Table — Design (v1.0, 2026-09-13)

Owner: Joe Nelson, Technical Sales Rep, Flow Instrumentation, Emerson Measurement Solutions.
Supersedes the "record only" framing in FRAMEWORK.md. Territory definition is unchanged (TERRITORY.md).

## 1. Purpose

A permanent display on a home monitor that makes Joe the master of his territory: **everything
and everyone that matters**, where each stands, and what changed overnight. Light-touch
gamification rewards the behaviour that actually builds territory mastery: knowing the accounts,
reaching the right ones, responding to change, and keeping the data honest.

It must also survive scrutiny. If it impresses Emerson leadership, Emerson's internal tool
developers will inspect it. Section 2 is written for them.

## 2. Principles an internal reviewer can check

| Principle | How it is enforced |
|---|---|
| Reproducible | `07-war-table/build.py` rebuilds all outputs from sources and writes a manifest with input hashes |
| Validated | Every layer validates against JSON Schema in `07-war-table/schemas/`; the build fails on invalid records |
| Deterministic | Opportunity (`05-preview/potential.py`) and progression (`07-war-table/wartable/progression.py`) are pure functions of data + config; no AI, no randomness |
| Tested | `python3 -m unittest discover 07-war-table/tests` covers scoring invariants, ledger semantics, progression, signal contract, server input handling |
| Provenance | Every fact carries source and as-of; reported vs inferred is explicit; AI output is labelled |
| Human in the loop | No automated process changes the registry. Signals may *propose* a change; only Joe's ledger entry applies it |
| Append-only records | Ledger, signals and logbook are JSONL, append-only. Corrections are new records (undo, reinstate), never edits |
| Least infrastructure | Python stdlib, files not databases, a local server bound to 127.0.0.1 only for writes |
| Inspectable in the product | The dashboard's **Method** panel shows the build manifest, layer counts, validation results and what is AI-generated |

## 3. Architecture: three layers

```
 sources (immutable)            ledger (Joe)                  sources, pluggable
 IIR · EPA · DEQ · eGRID  ─┐    registry_changes.jsonl ─┐     web / trade press / enterprise DB
                           ▼                            ▼                 │
                 04-outputs/merge.py ──► REGISTRY (base) ──► REGISTRY (effective)   SIGNALS ◄┘
                 05-preview/potential.py                          ▲    ▲              │
                                                                  │    └── match ─────┘
                                                        LOGBOOK (Joe) ── derives ──► stages · points · rank
```

**Registry** — the slow layer. Entities and their assessed opportunity. Base registry is built
from source exports; the effective registry is base + Joe's change ledger. Changes rarely.

**Signals** — the fast layer. Things that happened: announcements, permits, construction
starts, expansions, closures. Source-agnostic by contract (§5). Signals point at a registry
entity when they can be matched; unmatched signals wait in an "unplaced" tray, often a new
facility Joe may add.

**Logbook** — Joe's engagement. One-tap actions and signal triage. Progression is derived from
it, never stored. Later replaced or fed by the CRM.

Why three and not two: engagement must not pollute the registry (a visit is not a fact about the
plant), and keeping it separate is what makes the CRM swap clean.

## 4. Registry

### Entity kinds
| Kind | Status | Scoring |
|---|---|---|
| `facility` | 1,728 loaded (after 2026-09-13 exclusions) | flow potential (`potential.py`) |
| `oem` (skid builders, machine builders) | schema ready, none loaded | influence: designed-in, recurring |
| `engineering_office` (A&E, EPC) | schema ready, none loaded | influence: specifies 12-24 months before the PO |
| `integrator`, `distributor` | schema ready, none loaded | influence / channel |

**Power plants are scored by type** (added 2026-09-13), because generation is not one industry
for flow purposes: steam-cycle (nuclear, coal, biomass, waste-to-energy, cogeneration), thermal,
hydro and peaking plants (Medium at most), landfill-gas engines and small units (Low at most).
The type comes from the plant name, the recorded fuel and eGRID duty; the score is kept and shown
even where the band is capped. Solar, battery storage and wind were removed by exclusion rule.

Influence entities get their own scoring model when their data arrives; they are never forced
through the flow-potential model. Relationships (engineering office → facility, OEM → facility)
are a planned registry extension.

### Change ledger (`02-data/ledger/registry_changes.jsonl`)
| Change | Effect |
|---|---|
| `mark_defunct` | hidden from the default view, retained, excluded from progression denominators |
| `mark_not_a_fit` | same, reason required |
| `mark_assigned_elsewhere` | same; comes back with `reinstate` |
| `mark_duplicate` | hidden; its logbook history counts toward `duplicate_of` |
| `reinstate` | clears the latest status change |
| `correct` | whitelisted fields only: name, lat, lon, subindustry, parent |
| `add_entity` | new facility, OEM, engineering office… with a stated source |

Latest change per entity wins. Every change records who, when, why, and optional evidence.

## 5. Signals contract (`schemas/signal.schema.json`)

Each signal: `id`, `received_at`, `published_at`, `kind`, `stage`, `headline`, `summary`, `url`,
`source {type, name, as_of}`, `entity_id` or null, `match {method, confidence, reason}`,
`generated_by {kind: human|rule|ai, detail}`.

- **Source types:** `registry_snapshot`, `public_web`, `trade_press`, `government_record`,
  `enterprise_db`, `manual`. Adapters produce records in this shape; nothing downstream knows
  or cares which source it was.
- **Stages** form the horizon: `rumored → announced → design → permitting → construction →
  commissioning → operating`, plus `on_hold` and `cancelled`. Announced through permitting is the
  **specification window**, when meters get specified.
- **Freshness:** bright for 72 hours, fading over 7 days, then log-only.
- **Trade press:** headline, link and a short original summary only. Never full articles.
- **AI-generated summaries** are marked `generated_by.kind = ai` and shown with an "AI summary"
  tag beside the source link.

Seeded today from real data: the Industrial Info statuses already in the export
(under construction, expansion, proposed, on hold) become `registry_snapshot` signals dated to
the export. They are honest "as of Sept 9" records, not news.

## 6. Logbook and progression

### One-tap actions → charting stage
| Action | Stage reached |
|---|---|
| (none) | Uncharted |
| `surveyed` — researched, confirmed operating | Surveyed |
| `visited` or `met` (role title only) | Landfall |
| `quoted` | Established |
| `won` — installed base or order | Anchored |

Also `undo` (reverses a prior event) and signal triage: `signal_reviewed`, `signal_pinned`,
`signal_dismissed`. Stage is the highest stage reached across non-undone events.

### Charting points (all values in `07-war-table/config/progression.json`)
- Stage points, earned once per entity: Surveyed 1 · Landfall +3 · Established +5 · Anchored +8.
- Multiplied by opportunity: High ×3 · Medium ×2 · Low ×1 · Insufficient ×1. Reaching the right
  accounts counts for more than reaching many.
- Cluster milestones: 10% / 25% / 50% / 75% of a cluster's in-portfolio entities surveyed →
  5 / 15 / 30 / 50 points.
- Signal responsiveness: a signal reviewed within 3 days of arrival → 1 point.
- No points for volume of calls, emails or logins. Nothing rewards empty activity.
- Each tap records the opportunity rating in force when it was made. Re-scoring a facility later
  never changes points already earned.

### Ranks — 22 levels
Seven ranks with three grades each, then a final rank. Thresholds rise steeply, so the first
promotions come in the first week and the last take years.

| Level | Title | Points |
|---|---|---|
| 1–3 | Chart Cadet I–III | 0 · 10 · 40 |
| 4–6 | Surveyor I–III | 95 · 175 · 285 |
| 7–9 | Senior Surveyor I–III | 415 · 575 · 760 |
| 10–12 | Navigator I–III | 970 · 1,215 · 1,480 |
| 13–15 | Master Navigator I–III | 1,780 · 2,105 · 2,460 |
| 16–18 | Harbor Master I–III | 2,840 · 3,255 · 3,695 |
| 19–21 | Commodore I–III | 4,165 · 4,670 · 5,200 |
| 22 | Admiral of the Chart | 5,760 |

The table is generated from config; the dashboard always shows the live values and how the
current total was earned. Ranks never go down.

## 7. Dashboard (Admiralty Chart)

- **Base:** the Admiralty Chart style chosen from `06-map-mockups`: tilted three.js chart,
  depth-shaded water, isobaths, real relief.
- **Uncharted areas:** each cluster is drawn as a pencil-sketched, unfinished chart until it is
  surveyed, and inks in as coverage grows. Facilities stay fully legible; only the chart finish changes.
- **Declutter:** the overview shows High and Medium facilities. Low-opportunity facilities fade
  in as you zoom, and always show once charted. Nothing is removed from the data.
- **Signals:** freshness glow; a sonar ping from the location of each new arrival; otherwise one
  faint morning ping from Richmond.
- **Horizon panel:** projects by stage, with the specification window called out.
- **Rank plate:** title, points, progress to next grade, and the breakdown on click.
- **Charting card:** the facility detail plus the five one-tap actions and the stage pips.
- **Ship's log strip:** recent logbook entries and signals, as a slow ticker.
- **Chart furniture:** scale bar, graticule, compass, title cartouche.
- **Always-on care:** time-of-day light, night dimming, slow ambient drift and HUD pixel shift
  against burn-in.
- **Presentation mode:** for showing leadership. Larger type, no editing controls, and the
  **Method** panel open: layers, counts, validation, build manifest, data rights.
- **Read-only fallback:** opened as a file without the server, everything works except logging.

## 8. People policy

"Everyone that matters" is modelled as **roles within organisations**, not named individuals.
The logbook's `met` action accepts a role title. Named contacts, phone numbers and email live in
the CRM, where Emerson's data governance applies. `Plant Contacts.xlsx` stays off limits.

## 9. Data-rights register

| Source | Rights | Use here |
|---|---|---|
| Industrial Info Resources plant export | **Licensed.** Confirm terms before showing outside Joe's own use or moving into an Emerson system; Emerson may hold its own subscription | registry backbone |
| EPA TRI 2024, GHGRP 2023, eGRID 2023 | US government, public domain | registry enrichment |
| Virginia DEQ air permit register | Public record | registry enrichment |
| US Census TIGER | Public domain | basemap |
| AWS Terrain Tiles (USGS 3DEP, NOAA/GEBCO) | Open data; attribution given in the UI | terrain, bathymetry |
| AI recall sweep (Pass 1, 142 records) | AI-generated | labelled "unverified research"; never a citation |
| Trade press / web (future) | Publisher terms; headline + link + short summary only | signals |
| three.js (MIT), IBM Plex and Cormorant fonts (OFL) | Open source | front end |

## 10. Roadmap

| Phase | Scope |
|---|---|
| **A (now)** | Three-layer data structure with schemas, ledger, seeded signals, logbook, progression, tests; local server; Admiralty dashboard with charting, ranks, horizon, Method panel |
| B | Signals adapter v1 (public sources) and the morning briefing tour from real arrivals |
| C | OEMs and engineering offices: schema already supports them; needs data and an influence model |
| D | Enterprise: Emerson plant lists and project databases as adapters; CRM as the logbook source |

## 11. Open items
1. Industrial Info licence terms for display to Emerson and for an Emerson-hosted version.
2. Version control. The project is not a git repository; a local repo would give reviewers a
   full change history. Licensed exports and raw caches would be excluded.
3. Influence scoring model for OEMs and engineering offices (Phase C).
4. The 05-preview model is canonical but still lives in the preview folder; promote it when the
   preview is formally approved.
