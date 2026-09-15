# SOLARYN implementation plan

Scope: FOUND-001/002/003, SITE-001 and UI-001–005 foundation. Stage names below follow the user's request (the PRD groups milestones differently). No scientific behavior changes in this increment.

## Architecture decision

Reuse Python/FastAPI/Pydantic, SQLite and the existing framework-free browser architecture. Adding React/Vite would duplicate equivalent infrastructure for this bounded slice. Use ES modules, a typed API contract and vendored Leaflet 1.9.4. A separate local entry point on port 8766 avoids changing existing account workflows and stored decisions on 8765. Shared scientific adapters will be connected only after review.

## M0 — Foundation and architecture

- Reuse: Platform FastAPI conventions, installed dependencies, existing static-client approach.
- Missing: canonical v4.1 PRD, repository rules, clean public flow and typed contracts; implemented in this slice.
- Refactor later: consolidate duplicated source trees using explicit versioned imports.
- Scientific risk: older cores implement different policies; imports must not silently select a copy.
- External dependencies: existing Python lockfile; pinned Leaflet with license.
- Tests: API validation, persistence/restart, contract snapshot, browser syntax/type checks, navigation.
- Completion: local launcher, seven routes, original logo, honest unavailable states. Full M0 CI remains a follow-up.

## M1 — Global map and arbitrary coordinates

- Reuse: existing coordinate domain conventions, Leaflet rather than old city controls.
- Missing: clickable world map, draggable marker, manual coordinates, saved site API; implemented here.
- Refactor: remove preset defaults from future integrated project creation, without rewriting old runs.
- Scientific risk: map projection excludes poles visually; manual entry accepts ±90 and ±180 exactly. Provider coverage is a separate check.
- External dependencies: OpenStreetMap tiles; manual entry works without tiles.
- Tests: boundary/invalid/nonfinite coordinates, exact roundtrip, click/drag/manual flow, reload.
- Completion: arbitrary coordinate persists and continues to conditions without substitution.

## M2 — Climate/resource pipeline

Update: `Solaryn_Platform/climate_service.py` now connects PVGIS 5.3 and NASA POWER with immutable raw/normalized hourly sources, year selection, cache/refresh, monthly summaries, per-metric provenance and resource cross-check. Conditions and Evidence render backend values. See `docs/CLIMATE_INTEGRATION.md` for implemented scope and outstanding physics coupling. The original gap inventory below is retained as planning history.

- Reuse: `src/data_fetchers.py`, `pvlib_pipeline.py`, Pilot snapshot/run storage.
- Missing: reviewed PVGIS primary adapter, normalized immutable snapshots, independent NASA cross-check behind new API.
- Refactor: provider retrieval away from synchronous UI/physics runs; cache by coordinate/year/geometry/provider.
- Scientific risks: UTC/leap years, missing hours, incompatible provider geometry, old recorded-site assumptions.
- External dependencies: JRC PVGIS, NASA POWER; no requests made by this foundation.
- Tests: recorded anonymous fixtures, units, errors, time axes, no coordinate substitution, hashes.
- Completion: conditions cards and monthly chart show actual frozen provider values and provenance. Currently NOT_IMPLEMENTED.

## M3 — Commercial PV module catalog

- Reuse: `data/raw/module_candidate_master.csv`, module input validation and evidence files.
- Missing: current commercial verification, versioned catalog imports and complete evidence revisions.
- Refactor: adapt existing source records into nullable presentation fields; never infer bifaciality or availability. Read-only adapter implemented here.
- Scientific risks: inferred cell counts, warranty ≠ field degradation, technology proxies, stale sources.
- External dependencies: exact manufacturer datasheets and date/revision verification.
- Tests: source-field mapping, unknown stays null, selection of 3–10, family filtering.
- Completion: ≥3 currently verified real SKUs; today existing records remain UNKNOWN commercial status and pending review.

## M4 — Physics/performance

Update 2026-09-15: the map-first flow now uses the existing Pilot PVWatts kernel through a strict immutable hourly adapter for PRD Path C. Path A/B integration remains pending candidate-specific evidence. See `docs/PERFORMANCE_INTEGRATION.md`.

- Reuse: `module_iv_engine.py`, `iec61853_engine.py`, `pvlib_pipeline.py`, Pilot `system_physics.py`.
- Missing: reviewed model routing and unified versioned result contract.
- Refactor: isolate legacy family-sensitive proxy paths from recommended annual outputs.
- Scientific risks: thermal defaults, spectral sensitivities, single-diode extrapolation and inferred topology.
- External dependencies: pvlib, measured IEC matrices, source thermal/IAM evidence.
- Tests: numerical invariants, identical inputs, permutation/name invariance, synthetic crossover, no-rear/no-spectral gain.
- Completion: deterministic identical-boundary candidate series with units, model path and extrapolation.

## M5 — Recommendation and Top 3

Update: numeric objectives, Top 3, explicit co-leaders, candidate failures, stored temperature/loss contributions and separate provisional/Marginal status are implemented and tested.

- Reuse: `epc_decision.py`, Platform `decision_chain.py` numerical rankings.
- Missing: v4.1 strength policy and stored contribution decomposition.
- Refactor: separate ranking from unresolved/guardrail wording; deterministic ties need explicit policy.
- Scientific risks: 2% fallback guardrail is not calibrated confidence; first offer as economic reference must not determine winner.
- External dependencies: reviewed decision policy and evidence release.
- Tests: name/order invariance, ties, weak evidence retains calculable leader, all-invalid failure.
- Completion: backend recommended #1 plus Top 3 and separate strength/validation. Layout exists; no fabricated ranks.

## M6 — Lifetime, economics and Δ€/W

Update: explicit-input common lifetime, constant-efficiency AC scenario and EUR switching threshold/headroom are implemented. Blank inputs remain disabled; no warranty rates or quotes are inferred. Advanced candidate degradation and full LCOE remain outside this increment.

- Reuse: Pilot `procurement_model.py`, `lifetime_engine.py`, Platform decision chain.
- Missing: reviewed coupling from exact energy snapshot to declared objective and commercial boundary.
- Refactor: make reference candidate explicit and preserve all assumptions.
- Scientific risks: warranty-to-degradation substitution, currency/AC/DC boundaries, common assumptions misrepresented as differences.
- External dependencies: supplied quotes, energy value, discount rate, lifetime and supported degradation evidence.
- Tests: hand calculations, unit consistency, no quote ⇒ disabled economics, common degradation invariance.
- Completion: lifetime scenario and Δ€/W from immutable backend payload only.

## M7 — Validation, evidence and polish

- Reuse: SUPSI holdout data, `outdoor_validation.py`, existing export/hash storage.
- Missing: unified evidence releases, scoped validation gates, accessible error/recovery paths, CI.
- Refactor: replace old global validity claims with scoped measured evidence.
- Scientific risks: passing software tests is not external scientific validation.
- External dependencies: independently measured datasets and reviewer-defined thresholds.
- Tests: reproduce holdout metrics, immutable replay, responsive keyboard/browser flow, unavailable providers.
- Completion: non-specialist end-to-end real analysis with engineer drill-down. Evidence shell exists now.

## Report/catalog increment — 2026-09-15
Completed canonical 20-record catalog, evidence-gated A/B/C adapter, immutable SVG dashboard, offline EPC HTML and evidence ZIP. Full platform suite: 78 passed; final report checks: 8 passed. Original screening release preserved for replay. See docs/REPORT_CATALOG_DELIVERY.md. Next issue: reviewed exact-SKU electrical evidence and external validation before strength escalation.

