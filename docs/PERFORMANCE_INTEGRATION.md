# Provisional performance and recommendation integration

Implemented 2026-09-15 in the map-first application on port 8766.

## Scope

The flow now runs the selected candidates against their **frozen primary climate source**, returns annual/monthly energy and Top 3, and stores a new immutable result. It supports optional common lifetime, AC conversion, and EUR procurement-headroom scenarios. Candidate selection becomes labeled cards in narrow previews.

The four current catalog records do not provide verified candidate-specific IEC matrices, validated electrical coefficients or measured thermal coefficients. This increment therefore implements **PRD Path C: provisional datasheet fallback**. It does not claim that the advanced Path A/B integration, current commercial verification, or external validation of these four SKUs is complete.

## Existing code reused and preserved

- Explicitly load `Solaryn_Pilot/src/climate_physics.py` under an isolated module name; reuse `pvwatts_dc_power_kw_per_kwp` and `faiman_cell_temperature_c` only. No `src` package shadowing or legacy orchestration.
- No changes to the original V9/Pilot equations, historical results, authenticated platform, model coefficients or validation fixtures.
- The new AC adapter uses the same constant-efficiency, clipping and availability equations as `physics_worker.ac_from_dc`; its energy balance is tested independently.
- The old recommendation guardrail is not imported: a calculable provisional leader remains visible even with a small gap or incomplete validation.

## Numerical boundary

Every run declares geometry, soiling, thermal coefficients, wind multiplier and objective. The initial UI scenario is horizontal (tilt 0°), azimuth 180° (irrelevant when horizontal), albedo 0.2 (irrelevant when horizontal), zero soiling, Faiman U0=25, U1=6.84, and unadjusted source wind multiplier 1. These are visible editable screening assumptions, not measurements of the project or candidates.

1. Require the saved coordinate, normalized units, horizontal source, UTC time standard and one-hour integration duration. Reject missing GHI, temperature, wind, duplicated/missing hours, inconsistent timestamp offsets or all-zero solar resource. No weather interpolation or provider blending.
2. For horizontal configurations, POA equals the saved GHI exactly. For tilted configurations, apply pvlib Erbs GHI decomposition and isotropic transposition using the original timestamps and declared geometry. This is an explicitly provisional GHI-only path for both providers; provider DNI/DHI are retained in the source export but not used by this adapter. Solar geometry assumes elevation 0 m. This is not the advanced Pilot Perez/IAM path.
3. Apply the same Faiman temperature calculation to all candidates. Source wind is at 10 m; multiplication by the declared factor is a scenario, not a calibrated height conversion. No module-specific thermal advantage is inferred.
4. `Geff = POA × (1 − soiling_pct/100)`.
5. Existing PVWatts kernel: `Pdc[kW/kWp] = max(0, Geff/1000 × (1 + gamma[%/°C]/100 × (Tcell − 25)))`.
6. Sum hourly powers with one-hour weights for annual and monthly `kWh/kWp`. Module energy equals specific energy × nameplate W / 1000. No rounding before ranking.
7. Optional AC: `preclip = DC × efficiency`; clip at `1 / DC:AC`; then multiply by availability and `(1 − curtailment)`. No inverter-specific efficiency curve or transformer layer.

No spectral, low-light, bifacial/rear, IAM or terrain/row-shading gain is invented. Measured interpolation and extrapolation fractions are **null**, with domain status **UNCHARACTERIZED**, because a datasheet fallback has no characterized irradiance/temperature matrix.

Reference documentation: [pvlib Faiman parameters and wind-height convention](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.temperature.faiman.html), [pvlib temperature-model guidance](https://pvlib-python.readthedocs.io/en/stable/user_guide/modeling_topics/temperature.html). Generic coefficients are not candidate-specific calibration.

## Recommendation and explanation

Supported objectives: annual DC specific energy, annual AC specific energy, lifetime DC specific energy, and procurement headroom. Sort the unrounded numeric objective descending, then stable module ID for exact ties. Co-leaders within relative/absolute 1e-12 numerical tolerance are explicitly listed; display order does not establish a physical preference.

Return Top 3 when at least three candidates are feasible; retain visible reasons for excluded candidates. All-invalid inputs yield `CANNOT_RECOMMEND`. Recommendation strength is conservatively **MARGINAL** under this unvalidated fallback policy; it is not a calibrated probability or a sensitivity-validation claim. Scientific status is separately `PROVISIONAL_NOT_EXTERNALLY_VALIDATED`.

The saved DC decomposition reconciles incident reference-25°C energy, common soiling loss at 25°C, and the candidate's modeled temperature effect. Specific DC yield differs only through the supplied gamma coefficient in this model. Shared resource/soiling are not reported as independent reasons one candidate wins. AC losses, quotes and discounted value enter only if configured.

## Optional lifetime and economics

- Lifetime requires explicit project years and a common annual degradation percentage: `E_y = E_1 × (1−d)^(y−1)`. Year 1 equals annual modeled energy. No warranty or family rate is substituted.
- Lifetime AC scales the modeled year-1 net AC by common annual retention; it does not recalculate hourly inverter clipping for each later year. This limitation appears in commercial-run assumptions.
- Economics requires AC + lifetime, an explicit feasible reference candidate, energy value in EUR/kWh, discount rate, module quote EUR/W for each feasible candidate, and present-value non-module costs EUR/W for each. Zero cost must be supplied explicitly if that boundary is excluded.
- Discount energy-value differences at each year end, divide kWh/kWp revenue by 1000 W/kWp, subtract the supplied incremental present-value non-module cost difference. This is the maximum justified price premium EUR/W.
- Headroom = maximum justified premium − actual module-price premium. This is a switching-threshold scenario, not full LCOE or an investment recommendation.
- Missing optional inputs leave the stage not requested; missing dependencies for a requested objective return a useful validation error.

## Persistence and replay

`POST /api/v1/analyses` saves the selection and climate snapshot. `POST /api/v1/analyses/{id}/run` accepts the explicit configuration and saves a **new** result with parent ID. Existing requests/results are never overwritten. Rerunning a completed result uses its frozen inputs, not the latest climate or catalog.

The export contains normalized hourly weather and source provenance, selected module parameters and catalog hash, configuration, results, runtime versions and numerical-source hashes. `implementation_sources` stores the two numerical source files as **base64 of original bytes**, preserving original line endings. These archives are data; the replay command never executes code from an export.

```powershell
.\.venv\Scripts\python.exe Solaryn_Platform/replay_screening.py path\to\export.json
```

Replay validates frozen-input/configuration/decision checksums, current numerical code hashes and runtime versions, then compares the recomputed decision exactly. Restore the recorded implementation/runtime before replay if versions changed. `manifest.result_sha256` covers the decision payload, including candidate monthly/lifetime values and contributions.

## Verification

- Pre-change platform baseline: **49 passed**.
- Preserved V9 core baseline from the foundation stage: **64 passed**; no core files were edited.
- New tests cover horizontal hand totals, monthly reconciliation, per-module units, deterministic replay, identical candidates, name/family/order invariance, shared-loss invariance, hot/cold crossover, corrupt/incomplete climate, infeasible candidates, AC energy balance, lifetime hand math, economic discount/unit/reference/quote behavior, dependency validation and both provider formats with tilted geometry.
- Browser checks: real four-candidate selection, narrow card layout, explicit scenario form, calculation progress and actual Top 3 display. Existing snapshots remain retrievable.
- Full platform regression: **69 passed**. Final focused adapter/API check, including one additional complete optional-scenario test: **36 passed** (70 unique platform tests verified across these checks). Frontend lint, syntax and type checks pass. Dependency deprecation warnings remain.
- The live reference export replay returned **REPRODUCED** with decision SHA-256 `a32002c6c53fa9f284ae519bacb2b742e040d10a3d023c7cf8bf512e28d1b327`. Browser console reported no errors during final evidence verification.

## Live reference run

Run `e2d95cb1-25ca-48d0-94f0-013f2e889ea7` uses the user's saved coordinate and 2023 PVGIS source, with the initial horizontal DC screening scenario. No lifetime, AC or commercial inputs were invented.

| Rank | Candidate | Annual DC kWh/kWp |
|---|---|---:|
| 1 | REC Alpha Pure-RX 470 | 1,973.3 |
| 2 | JinkoSolar JKM575N-72HL4-V | 1,949.2 |
| 3 | First Solar Series 7 TR1 530 | 1,941.1 |
| 4 | LONGi LR5-72HPH-550M | 1,933.1 |

These are provisional model outputs under the stated boundary, not measured field yields or a validated claim of technology superiority.
