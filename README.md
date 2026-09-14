# Eastern Virginia Flow War Table

A local Admiralty Chart dashboard for territory intelligence. Python standard library,
pinned three.js, and three separate layers: facility registry, project signals and engagement
logbook. Opportunity and progression are deterministic and inspectable.

Read `CLAUDE.md`, then `00-framework/WAR-TABLE.md` and `07-war-table/README.md`.
The local-only `00-framework/HANDOFF.md` contains historical working context.

## What this repository contains

This is a private, code-only repository: dashboard source, Python build/server/model code,
schemas, scoring configuration, tests, and current design documentation.
It is not an official hosted Emerson product. No open-source license is granted here.

The `.gitignore` is an explicit allowlist. New files are ignored until their exact path is
reviewed and added. Do not override it with `git add -f`.

## What stays local

All of `02-data/`, including licensed exports, facility assessments, source caches, change
ledger, project signals, and engagement logbook; all generated dashboards, screenshots,
spreadsheets, and historical sales-planning documents. `Plant Contacts.xlsx` must never be
read, copied, committed or uploaded. Role titles only belong in the logbook.

GitHub is a code backup, not a complete data backup. Preserve the original local project and
its data separately. A fresh clone intentionally cannot build the real territory dashboard
until authorized local data has been restored. Do not enable GitHub Pages for this project.

## Build and run on Joe's existing Mac

```sh
cd /Users/zepp/Documents/EMERSON/territory-atlas
python3 07-war-table/build.py
python3 07-war-table/serve.py
```

Open http://127.0.0.1:8777. If the server is already running, rebuild and refresh the browser.
Python 3.9+ is used by the current project. Node is optional for the JavaScript syntax check.
Pillow is needed only when rebuilding the terrain assets, not for the daily build/server.
Fonts and pinned three.js currently load from CDNs; offline bundling remains future work.

## Tests

```sh
cd /Users/zepp/Documents/EMERSON/territory-atlas
python3 -m unittest discover 07-war-table/tests
```

All 58 existing tests must pass. Real-registry tests require local data and write a generated
deduplication log; server tests use throwaway fixtures. For manual engagement tests, run the
server against a copy of `02-data/` using `--data-dir`, never the real logbook.

## A fresh development clone

Restore the authorized `02-data/` directory privately into the clone. This includes
`clusters.json`, `model_config.json`, `exclusions.json`, registry/pass1/pass2 data, geo assets
(`basemap.json`, `terrain.json`, `terrain.png`), signals, and any ledger/logbook history.
The build then recreates `07-war-table/dist/`. Do not transfer data through GitHub until its
license and destination use are explicitly cleared.

## Future 3D work

The chart already displaces a three.js mesh using real terrain elevations. Higher-resolution
terrain, improved water/shoreline detail, and zoom-dependent geometry can extend this renderer.
Building footprints and measured building heights need their own attributed geographic data;
unverified geometry must not imply a real facility layout. Data layers and scoring stay intact.
