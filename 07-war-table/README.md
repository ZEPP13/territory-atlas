# War table

The permanent, lightly gamified territory display. Design: `00-framework/WAR-TABLE.md`.

## Run it
```
python3 07-war-table/build.py        # validate, test, build   (about 6 s)
python3 07-war-table/serve.py        # then open http://127.0.0.1:8777
```
Needs internet on load for three.js and fonts. Opening `dist/war_table.html` directly works too,
read-only (no logging).

## Use it
- **Click a marker or facility** → charting card. Tap **Surveyed · Visited · Met · Quoted · Won**.
  *Met* takes an optional role title (never a name). **Undo last tap** reverses a mistake.
- **Signals** on the card: *Mark reviewed*, *Pin*, *Dismiss*.
- **Record status…** on the card retires a facility from the chart (not a fit, defunct, assigned
  elsewhere, duplicate) with a required reason. Nothing is deleted; **Reinstate** reverses it.
- **Briefing** tours new arrivals, or the specification window when nothing is new.
- **Method** (or click the rank plate) explains every layer, number, rule and input hash.
- **Present** hides all editing controls for showing the tool to someone.
- Keys: `B` briefing · `D` drift · `R` reset view · `M` method · `P` present · `Esc` close ·
  arrows pan · `+`/`-` zoom · `Q`/`E` rotate · `W`/`S` tilt.

## Layout
| Path | What |
|---|---|
| `wartable/schema.py` | stdlib JSON Schema subset validator; refuses keywords it cannot enforce |
| `wartable/store.py` | append-only JSONL stores (ledger, signals, logbook) |
| `wartable/registry.py` | base registry from the unchanged merge + opportunity model; change ledger |
| `wartable/signals.py` | signal contract, registry-snapshot adapter, freshness, triage |
| `wartable/progression.py` | stages, points, milestones, ranks: replayed from history |
| `wartable/state.py` | one composer used by both the build and the server |
| `serve.py` | local server (127.0.0.1 only) for one-tap writes |
| `build.py` | the one command; writes `dist/manifest.json` with input hashes and test results |
| `dashboard_template.html` | the Admiralty Chart page |
| `schemas/`, `config/` | contracts and every tunable number |
| `tests/` | 51 tests: validator, ledger, progression, signals, real registry, server |

## Known limits
- three.js and fonts load from CDNs. For a monitor that must work offline, vendor them.
- Only one signal source exists so far: the Industrial Info project statuses in the export. The
  horizon says so on screen. Web, trade-press and enterprise adapters are Phase B.
- A facility added through `add_entity` appears after the next build, not live.
- Close-zoom sharpness is limited by the single 4096 px chart texture.
