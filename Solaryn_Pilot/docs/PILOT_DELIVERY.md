# Solaryn pilot delivery

## Scope delivered

This implements the PRD's local vertical slice on the latest supplied application, with the original archives preserved. The active frontend remains Streamlit, backed by a deterministic Python service. It is a technical pilot, not the complete cloud platform described in the PRD roadmap.

| PRD requirement | Delivered behavior |
|---|---|
| FR-PROJ/SITE/SYS, UI-001 | Named project, segment/stage/objective/capacity/lifetime; city search, map and coordinates; common fixed-tilt and optional row/rear geometry |
| CLIM-001/002/003/005 | NASA/PVGIS adapters, explicit UTC and complete-year validation, raw/normalized provider snapshots, monthly resource benchmark and visible discrepancies |
| MOD-001/003, PHY-001/004 | Ten exact commercial module records, strict CSV import and finite/physical checks; repaired row irradiance alignment; daylight/zero-output failure handling |
| DEC-001/002/003/004 | Four deterministic PRD states, strict evidence booleans, no first-row tie winner, failed candidates retained, reviewed evidence required for robust claims |
| RUN-001, schema 2.0 | Local content-addressed runs, atomic publication, idempotent completed-run retrieval, immutable project/site/input snapshots, source/code/parameter checksums |
| ECO-001/002 | Real baseline quote required, USD or EUR as consistent declared currency, discounted energy plus area-BOS threshold, ineligible economics blocked |
| RPT-001, FR-XAI-01 | HTML renders stored JSON; input/result files and hashes export together; deterministic local explanation cannot alter numbers or send data externally |
| VAL-001 | Fresh measured reference-layer replay with error/fallback metrics; separate pending cross-technology and EPC gates; bankability NOT_CLAIMED |

The reference electrical gate passing does not validate commercial candidates. Source-linked catalog values are retained with explicit reviewer limitations, not promoted to independently measured evidence. Published parameter review/RBAC is not simulated; the pilot cannot promote user-entered coefficients alone into reviewed evidence.

## Corrected reports

All three supplied reports previously showed every candidate at zero energy and first-row Mono PERC at 100% probability of best. The irradiance adapter misaligned timestamp and integer indices; a tie-handling defect then selected the first row.

The repaired 2018-2020 real-weather runs use the reports' coordinates, 25-degree tilt, south-facing azimuth, albedo 0.2, GCR 0.4, 2% soiling, 100 MWp and enabled row/rear geometry. Recorded row center height/pitch defaults are 1.5 m/5 m; these must be replaced by actual design geometry for project use.

| Site | Highest modeled annual DC module | kWh/kWp/year | Scientific status |
|---|---|---:|---|
| Iqaluit | Trina TSM-NEG21C.20-700, bifacial TOPCon | 1159.34 | Insufficient evidence |
| Timokten | Canadian Solar CS6.2-66HB-635H, bifacial HJT | 2206.59 | Insufficient evidence |
| Leuven | Canadian Solar CS6.2-66HB-635H, bifacial HJT | 1354.86 | Insufficient evidence |

These are conditional model outputs, not procurement endorsements. In Leuven the next module is very close (1354.34); the small difference must not be marketed as a demonstrated technology advantage. No constants were tuned to force different climates to produce different winners.

## Verification and reproducibility

See BUILD_VALIDATION.md for the final executed checks. The accepted no-row Riyadh annual regression remains TOPCon 2073.43, CdTe 2048.64 and PERC 2035.00 kWh/kWp/year. A 1.21% gap and incomplete evidence correctly prevent a robust winner.

Tests cover actual RangeIndex weather through geometry/electrical models, index invariance, missing/non-finite inputs, all-zero rejection, four-state transitions, strict evidence, fair ties, source snapshots, hashing/tamper detection, report/JSON parity, monthly integration, offline replay and UI navigation. Equation fixtures now explicitly declare eligibility instead of relying on the removed unsafe default; their original arithmetic assertions remain.

`tools/validate_measured.py` reruns 28,286 retained measured observations: RMSE 18.163 W, MAE 8.601 W, MBE -0.0139 W and normalized RMSE 6.358% STC. The Benguerir historical ordering failure and unavailable KU Leuven raw holdout remain disclosed.

## Remaining PRD stages

Not implemented in this local stage: Next.js/FastAPI public API, PostgreSQL/PostGIS CRUD and migrations, Redis/async job worker, multi-workspace RBAC, cloud object storage/signed URLs, managed TLS/encryption, formal parameter publication approvals, cloud CI deployment, historical EPC decision-replay datasets, and bankable uncertainty. Current application calculations use a foreground service with visible progress; live provider fetches are cached, not background distributed jobs.

Timezone metadata denotes the UTC calculation standard, not a geocoded civil timezone. Elevation/polygon and full layout/tracker design are not implemented. Completed project revisions persist with runs; independent draft-project CRUD is a later stage. These limits are explicit so the pilot is not mistaken for a fully deployed multi-user service.

## Packaging

`Solaryn_Client_Delivery.zip` contains one `Solaryn/` directory. Start with README. Runtime environments, caches and development run storage are excluded. Corrected example analysis archives include all input snapshots and outputs and are consequently larger than source-only delivery. Dependency versions are locked; model/schema versions remain internal provenance metadata. Original all-zero reports are superseded and are not included.

A development-folder ACL repair was rejected by automatic approval review; those folders were left untouched. The client archive excludes that development storage. New run folders use ordinary inherited permissions without changing existing access rights.

## Cleanup and presentation checklist

- Retained the original physics, measured validation datasets, strict input checks, ten commercial modules, thirty research technology records and all 99 original tests.
- Moved superseded design documents into `docs/historical/`; current implementation and model documentation identify the active behavior.
- Replaced the active legacy recommendation flow with the service-backed project workflow. Legacy helper/research modules remain where existing tools still depend on them; this is not a claim that every legacy function was removed.
- Client packaging excludes environments, bytecode, caches, development outputs and local run storage. Original supplied archives remain untouched outside the delivery.
- Main application branding and download names use Solaryn without POC/draft/version suffixes. Technical release identifiers remain in reproducibility metadata and historical documents deliberately; a literal removal of all version references is not claimed.
- UI presents decision status and reasons first, followed by rounded module comparisons, seasonal energy, separate resource/economic/evidence tabs and consistent exports.
- Analysis names include the project and highest modeled technology, not an unsupported winning-technology claim.
- Catalog structural/physical audit passes for all 10 modules and 30 research records. This does not independently certify every manufacturer claim or demonstrate catalogue completeness across the market.
