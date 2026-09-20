# SOLARYN UI upgrade — 2026-09-16

## Scope

Frontend-focused upgrade for the map-first SOLARYN Decision Engine. Scientific calculations, ranking logic, climate calculations, catalog data and economic formulas are unchanged.

## User-facing architecture

The main workflow is now visibly organized as:

1. Site & Project
2. Climate Fingerprint
3. Technology Behaviour
4. Lifetime Performance
5. Lifetime Economics
6. Decision

A persistent decision bar shows the current stage and backend-derived readiness state.

## Main changes

- Rebuilt the application shell into a professional enterprise SaaS layout with a sticky header, selected-site context, utility actions and persistent six-stage navigation.
- Added presentation-only reverse geocoding. The exact WGS84 coordinate remains authoritative. The place label is cached client-side and fails gracefully to “Location name unavailable”.
- Added a small backend proxy endpoint, `GET /api/v1/geocode/reverse`, only to make reverse geocoding reliable and keep external-service access out of browser CORS concerns. It does not alter analysis inputs or calculations.
- Split the workflow UI so Lifetime Performance and Lifetime Economics are visually separate stages. A new SPA route `/economics` was added; existing API contracts are unchanged.
- Technology Behaviour now uses a product-library layout with filters, exact-SKU cards, evidence metadata and real site-response outputs after analysis.
- Lifetime Performance now shows backend year-1 / lifetime metrics, a backend-value 25-year/project-life curve, and common-degradation labeling.
- Lifetime Economics now exposes only supported commercial outputs: maximum justified premium Δ€/W, procurement headroom, supplied quote, energy value and discount rate. No LCOE/NPV is invented.
- Decision is now a hero screen with Top 3, no-clear-winner support, recommendation strength, scientific status and final Decision Trace.
- Decision Trace uses stored analysis outputs for all six stages and shows neutral unavailable states instead of fabricated values.

## Files changed

- `Solaryn_Platform/web/foundation/app.js`
- `Solaryn_Platform/web/foundation/style.css`
- `Solaryn_Platform/web/foundation/index.html`
- `Solaryn_Platform/foundation.py` — only the reverse-geocoding UI proxy and `/economics` SPA route whitelist.

## Validation performed in the build environment

- `node --check Solaryn_Platform/web/foundation/app.js` — passed.
- `python -m py_compile Solaryn_Platform/foundation.py` — passed.
- FastAPI smoke test with a temporary PVLIB import stub:
  - `/api/v1/health` → 200
  - `/economics` → 200 and serves the Decision Intelligence shell
  - `/api/v1/geocode/reverse` with a mocked Nominatim response → `Leuven, Belgium`
- Full Python test collection could not run in this build container because `pvlib` is not installed and outbound package installation is blocked. No calculation code was changed.

## Run locally

From the repository root on Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\Solaryn_Platform\requirements-lock.txt
.\.venv\Scripts\python.exe .\Solaryn_Platform\run_foundation.py
```

Open `http://127.0.0.1:8766`.
