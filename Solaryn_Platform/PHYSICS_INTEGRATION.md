# Physics-driven platform integration — 14 September 2026

## Active execution chain

The project now opens on **Physics & validation**. The API executes the preserved `Solaryn_Pilot/src/pilot_service.py` in a separate Python process. Its imports resolve against the original pilot, avoiding namespace collisions with older copies of `src`.

Project coordinates + source weather → original pvlib irradiance/solar geometry → original thermal and electrical module model → hourly DC specific power → declared hourly AC conversion/clipping → energy-weighted annual AC yield → existing deterministic lifecycle economics.

No new replacement DC physics engine was introduced. Exact catalog module records, electrical model eligibility, thermal assumptions, row/bifacial model options and original scientific decision gates remain in use. The legacy manual-yield procurement workflow remains available as a separate input path. Its generic example offers are not silently mapped to catalog products.

## Weather and simulation

- Offline mode uses the original 8,784-hour NASA POWER Riyadh 2020 fixture, checked against its source metadata SHA-256. It requires coordinates 24.7136, 46.6753 within 0.001 degree. It cannot silently be moved to another project location.
- Live mode calls the existing NASA POWER fetcher for the project's coordinates and a declared calendar year. Network/provider failure stops execution; recorded weather is not substituted. Live retrieval was not exercised in this integration validation.
- Users select 2–5 distinct exact catalog modules. Unknown identifiers, invalid physical controls and stale project revisions are rejected.
- A selected module failure prevents an economic comparison of the partially successful selection.
- The annual DC total must reconcile to the integrated original hourly power within relative tolerance 1e-9.

The original default three-module reference remains:

| Module | DC kWh/kWp/year |
|---|---:|
| Jinko JKM575N-72HL4-V | 2073.433038 |
| LONGi LR5-72HPH-550M | 2034.997755 |
| First Solar Series 7 TR1 530 | 2048.638261 |

These are preserved model outputs, not three independently measured SKU validation results. In particular, the CdTe electrical path remains exploratory and the reference selection retains **INSUFFICIENT_EVIDENCE**.

## DC-to-AC boundary

Per installed DC kWp, at each hourly sample:

`P_AC = min(P_DC × eta, 1/DCAC) × availability × (1−curtailment)`

`E_AC = sum(P_AC × original hourly/year-normalization weight)`

The UI and export separately report DC energy, conversion loss, clipping loss, availability/curtailment loss and net AC energy. Soiling is applied once inside the original DC simulation. This AC bridge is a constant-efficiency engineering approximation: inverter efficiency curves, voltage windows, plant wiring, grid dispatch and measured AC validation are not implemented. It is not labeled as a validated plant AC model.

When every selected module has a quoted EUR/W price, the computed net AC yield is supplied directly to `procurement_model.compare`, together with the project's capacity, CAPEX, O&M, cleaning, real discount rate and PPA. The declared degradation fraction is a scenario, not an inferred climate-dependent lifetime rate. Missing prices leave the physical result available and economics disabled. Economic results remain exploratory, with original physical evidence gates displayed, and cannot receive approval through the separate manual-yield workflow.

## Measured validation and acceptance meaning

Every completed physical run freshly executes the original SUPSI IEC 61853 interpolation validation on the supplied characterization matrix and outdoor observations. It recomputes monthly errors and retains the 13 source-file hashes.

The original validation routine assigns `PASS_EXTERNAL_MEASURED_LAYER` unconditionally when execution completes. The adapter preserves that string only as `inherited_status`; it does **not** treat it as a measured accuracy acceptance test.

The active status is **REFERENCE_BENCHMARK_REPRODUCED**, requiring the source hashes and retained row count to match the existing reference, and RMSE, normalized RMSE, MBE, R² and MAE to match within absolute tolerance 1e-5. Changed inputs or metrics fail the physical submission. This is a regression acceptance policy, not an independently chosen scientific accuracy threshold.

Reproduced metrics: 28,286 retained observations; RMSE 18.163253 W; normalized RMSE 6.357770% STC; MAE 8.600642 W; MBE −0.013910 W; R² 0.935877; maximum absolute residual 184.918243 W; nearest fallback 2.768154%.

The UI exposes monthly errors and a measured-versus-predicted scatter plot of at most 300 evenly spaced retained records. Metrics use all retained observations. The plot is a visual diagnostic, not an additional validation dataset.

This evidence applies to the reference electrical interpolation layer using measured irradiance and back-of-module temperature. It does not validate site climate, transposition, thermal modeling, rear irradiance, arbitrary commercial SKUs, cross-technology ranking, AC conversion, degradation, economics or bankability. Those original limitations remain visible.

## Persistence and exports

Physics runs are registered in an additive `physics_runs` table, scoped to organization and project through the existing authorization rules. Execution uses a fresh server-selected UUID folder under `workspace/physics/{organization}/{project}/{run}`. The original project revision travels with the result; subsequent edits are identified as newer inputs.

The analysis ZIP includes original pilot artifacts, source weather, exact module inputs, hourly DC/AC outputs, the measured monthly replay, measured validation source files, preserved Python model-source files and manifests. Every read/download verifies the artifact hashes. SHA-256 is an integrity check, not a cryptographic signature or protection against a privileged operator rewriting both files and hashes.

Execution is synchronous with a five-minute subprocess timeout. There is no durable worker queue, cancellation UI or concurrency-scale claim. Scientific data, the pilot source tree and additional runtime dependencies must accompany the platform deployment.

## Validation performed

- Platform integration suite: 13 tests passed after the initial implementation, including a real full-hourly API run, exact DC regression values, measured replay, AC energy conservation, derived-yield economics, source ZIP contents, wrong-site rejection, organization isolation and tamper rejection.
- Original preserved pilot: 29 targeted decision-contract, outdoor-validation and physics-sanity tests passed; the underlying pilot code was not modified.
- Browser: completed a reference-weather physical run with three original catalog modules and hypothetical EUR 0.12/W prices. Original evidence restrictions remained visible. Jinko's derived AC yield was 1946.11 kWh/kWp/year under DC/AC 1.3, eta 0.97 and availability 0.99; this is an AC model output, not measured AC validation.

Dependency deprecation warnings remain in pvlib/NumPy timedelta and Starlette/httpx. They did not fail the executed tests.

## Eight-stage decision chain — 2026-09-14

The physical workspace now follows site, climate, physics, exact module technology, lifetime, uncertainty, economics and recommendation. An offline schematic map selects coordinates; numeric fields provide precision. The map coastlines are illustrative, not GIS boundaries. Save coordinates before simulating; recorded Riyadh data remains geographically locked.

New decision_chain.py adds annual production with E_y = E_1 (1-d)^(y-1), climate summaries from the actual input resource, lifetime MWh, cash-flow-derived simple payback, CAPEX/OPEX/revenue and one-at-a-time NPV sensitivities. Ranking is computed from scenario NPV for exact modules; no TOPCon/HJT/CdTe order is hardcoded. Missing prices withhold ranking. Physical evidence gates remain visible.

Optional yield_log_sigma defines a lognormal yield scenario: the deterministic result is assumed to be the median, P90 = P50 exp(Phi^-1(0.1) sigma). This is 90% exceedance, not the 90th percentile. Lifetime quantiles assume a common persistent yield factor across all years, with fixed degradation. Without sigma, uncertainty remains NOT_QUANTIFIED. These are not calibrated bankable P50/P90 values; no confidence percentage is invented.

Heat, humidity, wind and precipitation summaries describe resource exposure. They do not infer aging. Climate-dependent degradation, thermal cycling damage and technology-specific failure probabilities still require calibrated models and independent validation. Spectral and bifacial claims retain the original engine's scope and eligibility gates.

Verification: 14 platform tests passed (29.87 seconds), including a complete real physics API run and conditional-quantile/lifetime checks. JavaScript syntax check passed. Earlier 29 targeted original-pilot tests passed. Final visual inspection of the new eight-stage UI was blocked by browser tool usage limits; interaction/layout QA remains outstanding. Live NASA retrieval was not exercised.
