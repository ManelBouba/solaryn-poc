# Report, visuals and catalog delivery — 2026-09-15

## Delivered

The map-first application now exposes a canonical versioned catalog, evidence-gated electrical routing, a visual decision dashboard, an offline EPC HTML report and a ZIP evidence package. The original `performance_service.py` remains unchanged for replay of screening-1.0.0 records; new calculations use `performance_v2.py` (screening-1.1.0). Saved analyses are not migrated or recalculated by downloads.

### Catalog

`data/catalog/commercial_modules.csv` is the active source. The JSON-formatted YAML sidecars supply provenance and taxonomy. The earlier root/Pilot CSVs remain historical migration/reproduction inputs, not alternate active catalogs.

- 20 exact power-bin/variant records; 13 currently officially listed, 7 with UNKNOWN exact current availability.
- 10 populated technology/architecture groups: PERC, TOPCon, HJT/SHJ, CdTe, HPBC, IBC, TOPCon bifacial, HJT bifacial, ABC and CIGS.
- An eleventh browser group, perovskite–silicon tandem, is evidence gated and contains no invented selectable SKU.
- Ten migrated Pilot records plus five AIKO Neostar 3S+60 ABC bins, three Maxeon 6 IBC bins and two AVANCIS SKALA black facade bins. Power bins are exact catalog records, not independent technology validations.
- Current official listings support REC, First Solar, LONGi HPBC, the two Canadian Solar variants, AIKO and Maxeon 6. Exact URLs, revisions where established, checked dates and restrictions are stored per record.
- SKALA AU 4.11 is restricted to BIPV_FACADE; its exact current availability remains UNKNOWN. First Solar TR1 is restricted to US utility use. Other regional variants retain their source regions.
- Ten of thirteen distinct datasheet URLs returned PDF bytes. Old Maxeon 7 failed TLS verification; JA Solar and Trina returned HTTP 403. These failures are recorded, not treated as fresh verification. See `source_http_checks.json` and per-record provenance.
- AIKO and SKALA electrical tables were visually inspected; AIKO, SKALA, Maxeon 6 and both Canadian Solar electrical tables were parsed. Historical fields not newly established retain their original transcription or null.

All 20 seeded rows are SCREENING_ONLY. No independently reviewed IEC matrix or validated CEC parameter set is fabricated. Bifaciality is metadata, not an applied generation gain. Official listings do not guarantee inventory, quotation or installation eligibility.

### Routes and model policy

- A: exact-SKU reviewed measured G/T/Pmax matrix; STC consistency gate; explicit daylight envelope/convex-hull accounting. Reuses the isolated Pilot matrix primitive. Not an IEC 61853-3 conformity claim.
- B: exact-SKU reviewed CEC coefficients with a declared validated domain and STC consistency gate; pvlib CEC/single-diode calculation. No inferred topology or unreviewed datasheet fit is promoted to B.
- C: existing deterministic PVWatts fallback. Temperature coefficient remains the only candidate-specific DC specific-yield driver.
- Application and declared market incompatibility produce visible candidate failures. Undeclared market remains an explicitly limited screening boundary.
- Recommendation strength is conservatively Marginal under versioned policy `conservative-evidence-ceiling-1.0`. Electrical evidence alone does not establish project-level validation. No probability-of-best or uncalibrated confidence is displayed.

### Visuals and downloads

Results and evidence pages offer **Download EPC Report**, **Download Evidence Package** and report preview.

`GET /api/v1/analyses/{id}/report` returns branded self-contained HTML, with the exact SOLARYN PNG embedded as data and inline SVG. `?inline=true` previews it. `GET /api/v1/analyses/{id}/package` returns report, complete immutable JSON, comparison/monthly CSVs, conditional lifetime/economics CSVs, provenance and a file-hash manifest. `GET /api/v1/analyses/{id}/visuals` supplies the shared escaped dashboard markup.

Charts include annual DC energy, Top-3 monthly energy, common lifetime sensitivity for the supplied horizon (including Year 1–25), cumulative lifetime for new runs, stored contribution differences, optional procurement headroom and resource cross-check. A connected stage diagram and stored operating-condition diagnostics explain the calculation boundary. No unavailable lifetime or price values are invented. Older runs display their existing stored contributions and omit new derived fields.

The renderer has no physics imports and does not rerun energy, degradation or economics. New cumulative, driver and diagnostic values are calculated once in the backend and hashed. Chart axes include zero; narrow panels scroll charts rather than shrinking labels to unreadable sizes.

## Verification

- Baseline: 70 platform tests passed.
- Full platform suite after implementation: **78 passed**, five dependency deprecation warnings.
- After the final responsive renderer adjustment: **8 report/catalog tests passed**, three dependency warnings.
- Frontend ESLint, Node syntax and API TypeScript checks: **passed**.
- Synthetic tests cover A/B routing, STC gates, domain accounting, catalog coverage, scope exclusions, name/order neutrality, preserved Path-C annual energy, exact stored 25-year points, conditional CSVs, HTML/CSV escaping and ZIP checksums.
- Existing user analysis `85d675c9-9b6a-4dd6-bca0-a19af6be5610` replayed exactly under its original release. Its report and evidence package downloaded successfully without recalculation.
- Browser inspected recommendation/download controls and connected dashboard in the narrow desktop preview. Backend tests verify attachment headers and bytes; an actual operating-system Save dialog is not automated.
- Software verification does not establish external scientific validation.

## Changed files

New: `catalog_service.py`, `electrical_router.py`, `performance_v2.py`, `report_service.py`, `tests/test_report_catalog.py`, canonical catalog CSV/YAML, catalog seed builder and HTTP source audit, this delivery note, audit note, corrected-code packager and setup guide. An exact archive of the original service is under `Solaryn_Platform/releases/screening-1.0.0/`.

Updated: `foundation.py`, `replay_screening.py`, frontend `app.js`, `api.js`, `contracts.d.ts`, `style.css`, foundation/performance tests, OpenAPI snapshot and plan. Preserved numerical core and original screening service remain available.

## Remaining limitations / next issue

Next scientific issue: obtain and independently review exact-SKU IEC matrices or validated electrical coefficients, measured thermal/IAM/spectral/rear-side evidence and external holdout validation. Then define a reviewed strength escalation policy. Candidate-specific degradation, calibrated crossover sensitivity and full LCOE remain unavailable. Common lifetime degradation is a supplied scenario, not warranty-derived field behavior. Cross-provider resource differences are descriptive; no calibrated acceptance threshold is configured. Confirm unknown source revisions and regional procurement availability before a decision-grade release.
