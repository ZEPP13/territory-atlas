# Eastern Virginia Flow War Table

Territory intelligence tool for **Joe Nelson, Technical Sales Rep, Flow Instrumentation, Emerson
Measurement Solutions**. Base: Richmond VA.

**What this is (rewritten 2026-09-13 at Joe's direction):** a permanent, lightly gamified war
table that lives on a home monitor and helps Joe become the master of his territory: every
facility, project, OEM and engineering office that matters, where it stands, and what changed.
It IS an ongoing-use tool. The earlier "record only, no activity logging" rule is retired.

Read `00-framework/WAR-TABLE.md` before building anything. It is the authoritative design.

## Build to be inspected
Emerson executives may see this, and Emerson's internal tool developers may review it. Everything
must be inspectable and defensible:
- **Reproducible.** One command rebuilds every output from sources. No hand-edited outputs.
- **Schemas are the contract.** Every data layer validates against `07-war-table/schemas/`. The
  build fails loudly on invalid data rather than silently dropping it.
- **Deterministic scoring.** Opportunity and progression are rule-based, weights live in config,
  invariants are covered by tests. No AI in the scoring path.
- **Provenance on every fact:** source, as-of date, and whether it is reported or inferred.
- **AI output is always labelled** as AI-generated, with its source link. AI never changes the
  registry on its own; it can only propose a change for Joe to approve.
- **Stdlib first.** Python stdlib (+ Pillow for terrain only). Front end: three.js pinned. No new
  dependency without a stated reason.
- **Tests pass before anything is shown or published:** `python3 -m unittest discover 07-war-table/tests`

## Three data layers (never merged into one another)
| Layer | Holds | Changes | Where |
|---|---|---|---|
| **Registry** | Entities: facilities now; OEMs, engineering offices, integrators later | Rarely, only through the change ledger | built from `02-data/registry/*` + `02-data/ledger/registry_changes.jsonl` |
| **Signals** | Project news, permits, announcements, closures | Often | `02-data/signals/signals.jsonl` (append-only, source-agnostic contract) |
| **Logbook** | Joe's engagement: surveyed / visited / met / quoted / won, signal triage | As he works | `02-data/logbook/logbook.jsonl` (append-only) |

Signal sourcing is deliberately source-agnostic: public web and trade press now, Emerson project
databases and plant lists later (Claude Enterprise). Build adapters, never source-specific logic
in the dashboard.

## Portfolio scope
Flow ONLY: Coriolis (Micro Motion), Magnetic, Clamp-on Ultrasonic (Flexim), Vortex.
**Level is out.** **Municipal water/wastewater utilities are out** (`scope: out_of_portfolio`,
hidden by default). Industrial pretreatment inside a plant is in.

**Flexim-first scoring is retired (Joe, 2026-09-11).** Assess the plant's operation first and let
the application choose the technology. The compensation-weighted view survives only as a
secondary, clearly labelled option. Never put quota, commission or comp-plan figures on screen.

## Hard rules
- **Never mutate a source export.** Exclusions go in `02-data/exclusions.json`; Joe's registry
  decisions (defunct, not a fit, duplicate, reinstate) go in the change ledger.
- **`Plant Contacts.xlsx` is off limits.** PII. Do not read, ingest, or publish it.
- **People: roles, not names.** The logbook records a role title ("E&I maintenance supervisor"),
  never a personal name. Named contacts belong in the CRM.
- **Not a CRM.** One-tap engagement logging only. No notes fields, pipelines or deal tracking.
- **Dollar figures are modelled, never researched.** ASPs in `02-data/model_config.json` are
  placeholders. Never present them as forecasts.
- **Provenance is never collapsed.** Existence (a source proves it exists), operating status, and
  assessment confidence are three separate questions.
- **Territory** is the official 74-jurisdiction list in `00-framework/TERRITORY.md`.
- **Licensed data.** The Industrial Info export is licensed. Confirm terms before it is shown
  outside Joe's own use or moved into an Emerson system (see the data-rights register in WAR-TABLE.md).

## Layout
| Folder | Role | Status |
|---|---|---|
| `00-framework/` | TERRITORY, FRAMEWORK (historical), HANDOFF, **WAR-TABLE (current design)** | |
| `02-data/` | sources, ledger, signals, logbook, geo | source of truth |
| `04-outputs/` | original atlas: `merge.py` is still the merge logic | published atlas, being superseded |
| `05-preview/` | industry families + explainable potential model (`industry.py`, `potential.py`) | preview; model is canonical |
| `06-map-mockups/` | three 3D style studies; Joe chose **Admiralty Chart** | reference |
| `07-war-table/` | the war table: data layers, progression, server, dashboard, tests | active |

## Commands
```
python3 06-map-mockups/terrain_build.py            # once: terrain + bathymetry grid
python3 07-war-table/build.py                      # validate every layer, build registry + dashboard
python3 -m unittest discover 07-war-table/tests    # must pass
python3 07-war-table/serve.py                      # http://127.0.0.1:8777 (local only; enables one-tap logging)
```
The old atlas still rebuilds with `python3 04-outputs/build.py && python3 04-outputs/build_atlas.py`.
**Published artifact** (old atlas; do not replace until Joe approves):
https://claude.ai/code/artifact/7a7c7f38-f772-4efb-96dc-3be79f4494ee
