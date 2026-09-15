# Validation record

## Real measured use case — IEC 61853 electrical layer

`validation/results/Solaryn_Real_World_Validation_Report.html` is the client-readable validation report generated from the packaged measured outdoor dataset.

The test uses the IEA PVPS Task 13 / SUPSI outdoor measurements with measured plane-of-array irradiance and measured module temperature as direct inputs to the IEC 61853 Pmax(G,T) interpolation layer.

Recorded result:

- raw observations: **36,449**
- retained observations inside physical/characterization filters: **28,286**
- RMSE: **18.163 W**
- normalized RMSE: **6.358% of STC Pmax**
- MBE: **-0.0139 W**
- R²: **0.9359**
- cumulative sampled-energy bias: **-0.0084%**

`validation/results/measured_electrical_validation_monthly.csv` exposes the 12 monthly error blocks so annual error cancellation cannot hide seasonal bias.

**Claim supported:** measured GPOA + measured module temperature → IEC Pmax(G,T) interpolation for the supplied reference c-Si module.

**Claims not supported by this test:** weather-resource accuracy, POA transposition, thermal prediction, current commercial SKU ranking, AC output, cross-technology recommendation, product-specific degradation, lifetime economics or procurement choice.

## Thermal layer

`validation/results/thermal_validation_ku_leuven.csv` records an independent thermal holdout:

- holdout observations: **42,025**
- RMSE: **1.389 K**
- MAE: **0.938 K**
- MBE: **0.326 K**
- R²: **0.935**
- baseline holdout RMSE: **1.915 K**
- RMSE reduction versus baseline: **27.44%**

This evidence is scoped to the tested thermal configuration. Transfer to other mounting/BOM classes must remain explicit and uncertain.

## Cross-technology falsification

`validation/results/field_benchmark_summary.csv` retains the compact field benchmark registry. It currently records two passing benchmark comparisons and one preserved Morocco failure. Failures are not removed or converted into site-specific corrections.

A high-value external target is the 2025 Scientific Reports analysis of the 1.2 MW Tenaga Suria Brunei experimental plant, which used three years of co-located data across six PV technologies. Solaryn uses such studies as frozen falsification targets; their observed winner is never imported as a climate bonus.

Source: https://www.nature.com/articles/s41598-025-99958-x

## Validation gates for stronger claims

1. **V1 Resource/POA:** measured POA and documented bias/error.
2. **V2 Thermal:** independent measured module/cell-temperature holdout.
3. **V3 Electrical:** measured P(G,T) or equivalent outdoor power validation by model class.
4. **V4 System:** measured DC→AC/meter validation.
5. **V5 Cross-technology rank:** frozen multi-technology field benchmarks across climates.
6. **V6 Lifetime:** field degradation and/or calibrated reliability evidence matched to product/BOM and climate.
7. **V7 Procurement:** closed tender replay using actual offers, system design and commercial assumptions.
8. **V8 Prospective pilot:** recommendation recorded before procurement/build, then scored against operation.

The anti-circularity rule is mandatory: freeze the model before benchmark scoring, preserve failures, and accept a correction only when it represents a general physical mechanism and transfers across independent cases.


## Recommendation-engine safeguards added

The product test suite now verifies that:

- evidence-ineligible candidates are excluded from procurement `P(best)` but remain visible in exploratory uncertainty;
- an evidence-ineligible numerical leader forces `No decision`;
- >10% independent POA disagreement caps the recommendation at `Conditional`;
- multi-year resource totals are annualized rather than summed;
- monthly exports preserve all 12 months;
- candidate-specific bifaciality fields are sourced and structurally validated.

The row/rear irradiance path uses pvlib infinite-sheds with Hay-Davies diffuse irradiance when enabled. This is a physically structured screening model, not project-specific rear-field validation.


## Robustness-gate regression tests

The automated suite now verifies that:

- evidence-ineligible candidates cannot enter decision P(best),
- an evidence-ineligible exploratory numerical leader forces No decision,
- low resource agreement caps the recommendation,
- a datasheet-only electrical fit cannot earn Robust even with a large numerical gap,
- generic thermal proxies cannot earn Robust,
- a single-year uncertainty prior cannot earn Robust,
- screening geometry cannot earn Robust,
- decision-material bifacial rear gain remains below Robust until the rear-POA path has independent measured validation,
- invalid bifaciality inputs fail closed,
- multi-year resource is annualized rather than summed, and monthly exports preserve all 12 months.
