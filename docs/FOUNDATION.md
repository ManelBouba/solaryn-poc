# Map-first foundation delivery

**Current follow-up:** Annual performance, recommendation/Top 3 and optional lifetime/AC/economics are now connected through the provisional datasheet path. See [PERFORMANCE_INTEGRATION.md](PERFORMANCE_INTEGRATION.md) for scope, assumptions, replay and validation limits.

**Follow-up:** PVGIS + NASA POWER are now connected. See [CLIMATE_INTEGRATION.md](CLIMATE_INTEGRATION.md) for the current climate behavior and checks. The initial foundation report below describes its original delivery state.

## Scope and architecture

Requirement IDs: FOUND-001, FOUND-002, FOUND-003, SITE-001, UI-001–005.

The repository contains V9 Streamlit/core code at the root, a later Pilot core, a FastAPI/SQLite procurement and physics platform, and multiple archived deliveries. The existing Platform uses plain HTML/CSS/JavaScript, not React. This increment reuses that architecture and dependency bundle, adds Leaflet, and gives the new flow its own local entry point and database. No existing scientific or authenticated-platform code was modified.

The supplied v4.1 PRD is copied verbatim to `docs/PRD.md`. `Solaryn_Pilot/docs/PRD.md` remains the older historical baseline. The user's attached execution request governs this bounded implementation; example instructions embedded in the PRD do not extend its scope.

## Start

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe Solaryn_Platform/run_foundation.py
```

- Frontend: http://127.0.0.1:8766/
- Backend: http://127.0.0.1:8766/api/v1/health
- Interactive API: http://127.0.0.1:8766/api/docs
- OpenAPI: http://127.0.0.1:8766/openapi.json
- Original authenticated platform still has its original launcher and port 8765.

For a fresh install, use the existing `Solaryn_Platform/requirements-lock.txt` in a Python 3.12 environment. This workspace already includes those dependencies in `Solaryn_Platform/.packages`; the launcher prepends that directory. Restricted Windows sandboxes may require permission to read the bundled files. No Node build is needed to serve the app.

## Screens

`/`, `/site`, `/conditions`, `/candidates`, `/processing`, `/results`, `/evidence`.

Home and Site Selection are the principal screenshot routes. Conditions, Candidates, Results and Evidence have complete visual layouts with truthful development states.

- Original PNG reused by `SolarynLogo` without cropping, recoloring or geometry changes; header/compact/report variants scale the same asset.
- Leaflet 1.9.4 JS/CSS and license are vendored. OpenStreetMap tiles need network access; manual coordinates remain available when tiles fail.
- Coordinates are WGS84 decimal degrees, latitude ±90, longitude ±180. Manual entry preserves the submitted numeric precision. Leaflet's Mercator map cannot visually cover the exact poles, so those remain manually selectable.
- The saved site is round-tripped through Pydantic and SQLite, not replaced with a named place or preset coordinate.
- Four existing SKU records are displayed with original source metadata. Current market availability and missing bifacial flags remain unknown. No online market verification was performed in this task.
- Select 3–10 candidates; filtering does not discard selection. Unrepresented families display an evidence-required empty state.
- Analysis submission saves a request with frozen candidate values and a SHA-256 catalog release. It does not run climate or scientific calculations. Stage states, empty ranking/contributions, and null model/economic fields are explicit.
- There are no completed scientific results in this increment. Requests cannot be updated through the API; repeat submissions create new IDs.
- Evidence links point to the source URLs already recorded in the catalog. JSON export exports the saved request, clearly labeled as such.

## API, persistence and units

`foundation.py` owns input/output schemas and SQLite persistence. `api.js` is the browser network boundary. `contracts.d.ts` describes presentation data; `docs/foundation-openapi.json` is a tested schema snapshot.

Site and saved request records use `Solaryn_Platform/workspace/foundation.sqlite3`, separate from existing account/project data. This is a single-user loopback PoC. It has no account-management or production hosting claim. Cross-origin browser writes are rejected.

Climate placeholders explicitly carry kWh/m²/year, W/m², °C, m/s and % with null values and null provider/period. Catalog values retain W, %, and %/°C. The browser calculates no resource, energy, lifetime, economics or recommendation numbers.

## Scientific baseline and review findings

- Root suite before changes: 64 passed, one pvlib/NumPy deprecation warning.
- Existing Platform suite before changes: 18 passed, dependency deprecation warnings.
- Initial Platform execution was blocked by Windows access restrictions on `.packages`. Retrying with access to the existing bundle passed; dependencies were not replaced.
- `docs/MODEL_EQUATIONS.md` documents legacy weighted suitability scores, a blended temperature approximation, resilience coefficients and climate-adjusted degradation. These historical formulas are not imported by the new service and are not approved v4.1 models.
- `src/module_iv_engine.py` contains technology-class spectral sensitivity mapping, neutral unsupported-hour fallback and a candidate-evidence policy separating primary broadband energy from sensitivity outputs. Review exact evidence and thermal routing before adapting it.
- `Solaryn_Platform/decision_chain.py` contains a fallback 2% guardrail and unresolved/tie wording. v4.1 requires best-available recommendation separated from recommendation strength. Do not reinterpret the guardrail as calibrated probability.
- Existing Platform project input defaults to a specific coordinate; recorded fixtures also use named sites. The new site flow has no default selected site or city dropdown. Existing runs and regression fixtures were preserved.
- Existing procurement workflow takes its first offer as a premium baseline; audit reference/order behavior before integration.
- Catalog records include inferred electrical topology, source warranty language, missing scientific evidence, and no verified current market dates. No missing fields were promoted to measured evidence.

These are integration review findings, not claims that a complete scientific audit has passed. No equation, coefficient, physics routing, scientific fixture, validation threshold or old decision policy was changed.

## Verification commands

Root baseline:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=.test-foundation-baseline
```

Platform and new API tests, from `Solaryn_Platform` (use a fresh basetemp for each run):

```powershell
$env:PYTHONPATH='.packages'
..\.venv\Scripts\python.exe -m pytest tests -q --basetemp=.test-foundation-check
```

Client checks, from `Solaryn_Platform/web/foundation`:

```powershell
npm.cmd ci --ignore-scripts
npm.cmd run build
```

Build checks run ESLint and Node syntax checks on application modules, plus TypeScript checking of the API boundary, declarations and logo module. The DOM-rendering `app.js` remains JavaScript and is linted, not fully type-checked. Runtime assets are served directly; no transpilation/bundling step exists in this architecture.

New tests cover arbitrary/boundary coordinate roundtrips, invalid/missing/nonfinite inputs, source preservation, null scientific outputs, distinct candidate validation, persistence across app recreation, request immutability, origin rejection, route/assets and OpenAPI consistency.

## Next issue

CLIM-001/003/004: connect the reviewed PVGIS provider behind the climate-snapshot API, normalize UTC/units, preserve raw responses and hashes, and populate the conditions cards/chart from immutable snapshots. Test anonymous fixtures, provider failures and coordinate fidelity before integrating candidate physics. Keep NASA POWER cross-check separate and expose its availability.

## Final verification results

- Core baseline: **64 passed**.
- Platform + foundation API suite: **33 passed** (18 existing + 15 new).
- After tightening response schemas and adding direct backend export: **15 foundation tests passed again**, including OpenAPI equality and export payload/attachment headers.
- Final `npm run build`: **passed** (ESLint, syntax checks, typed API/contract/Logo checks).
- Python compile check: **passed**. Existing dependency deprecation warnings remain.
- Browser: all seven views navigated; manual precision, map click, marker drag, exact saved-site display, three-module selection, empty CIGS filter with retained selection, request creation and reload inspected. Mobile Site/Evidence layouts inspected at 390px; viewport restored afterward.
- Browser export initially used a Blob download; the browser harness did not report a download event. It was replaced by a direct backend attachment link. Backend response content and attachment headers are tested; the browser's download-save destination is not verified.
- Supplied and copied logo SHA-256 match: `BD399F47AD97485EC8C49359B5D95BCDE1D5E6D8E3810B47551B7C3345A15269`.
- Local server starts successfully on loopback port 8766. A browser QA site and a NOT_IMPLEMENTED request are saved in the new foundation database only.

## File inventory

Created:

- `AGENTS.md`, `PLAN.md`
- `docs/PRD.md` (verbatim supplied document), `docs/FOUNDATION.md`, `docs/foundation-openapi.json`
- `frontend/public/brand/solaryn-logo.png` (exact supplied asset)
- `Solaryn_Platform/foundation.py`, `Solaryn_Platform/run_foundation.py`
- `Solaryn_Platform/tests/test_foundation.py`
- `Solaryn_Platform/web/foundation/index.html`, `app.js`, `api.js`, `logo.js`, `contracts.d.ts`, `style.css`
- `Solaryn_Platform/web/foundation/package.json`, `package-lock.json`, `eslint.config.js`, `.gitignore`
- `Solaryn_Platform/web/foundation/vendor/leaflet.js`, `leaflet.css`, `LICENSE.leaflet`

Changed existing file: root `README.md`, adding the new start instructions while retaining the earlier guide.

Local generated files: ignored npm dependencies, SQLite foundation/contract databases and temporary test directories. No existing scientific source, source catalog data, account database or historical run was modified.
