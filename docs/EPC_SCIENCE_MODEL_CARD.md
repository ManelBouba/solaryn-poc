# SOLARYN V8.2 — EPC Science Model Card

## Intended use

Screen real commercial module offers for a utility-scale, fixed-tilt, monofacial PV project before detailed EPC design. The result is intended to support expert review and procurement discussion, not replace PVsyst design, independent engineering, bankability review, certification, or manufacturer validation.

## Preserved Solaryn architecture

The full technology/material database remains part of Solaryn. EPC mode is a stricter execution path, not a new product concept. Technology labels link back to the original `technology_id` records.

## Physics chain

1. Full reference year of NASA POWER hourly GHI/DNI/DHI, temperature, relative humidity, 10 m wind, precipitation and surface pressure.
2. pvlib solar position.
3. Fixed-tilt POA using isotropic transposition.
4. Common physical front-glass incidence-angle modifier (IAM), including diffuse IAM integration.
5. Pressure-adjusted air mass and Gueymard precipitable-water estimate.
6. First-order technology-class spectral mismatch modifier where supported.
7. Module-construction-aware SAPM cell temperature.
8. CEC five-parameter model fitted from actual datasheet STC points.
9. `calcparams_cec` + `singlediode` at each hourly operating point.
10. Common project-level soiling assumption.
11. Annual DC specific energy in kWh/kWp.

## Inputs that are allowed to affect EPC energy

- project location and reference year;
- tilt/azimuth;
- NASA/PVGIS weather-resource data;
- module STC IV points;
- sourced current/voltage/power temperature coefficients;
- electrical series-cell count;
- module construction category for thermal model;
- technology-class spectral model;
- common project soiling assumption.

## Inputs that DO NOT decide the EPC winner

The following original Solaryn database fields are retained for research/material intelligence but do not directly enter EPC module ranking until they are validated for that use:

- generic `physics_quality_score`;
- absorber mobility/lifetime/defect aggregate score;
- heat-resilience score;
- humidity-resilience score;
- soiling-resilience score;
- generic confidence score;
- static database module-price proxy;
- uncalibrated Arrhenius/Peck stress multiplier.

## Lifetime / reliability boundary

Solaryn reports heat, hot-humid, UV-proxy and thermal-cycle exposure diagnostics. These are not converted to degradation rates.

The current 25-year energy number is a **warranty-derived scenario** based on manufacturer power-warranty endpoints. It is not:

- a field degradation prediction;
- an energy warranty;
- a probability distribution;
- P50/P90;
- a bankability conclusion.

## Spectral limitation

The default pvlib coefficients represent technology classes, not the exact quantum-efficiency curve of each selected modern module. The spectral result is therefore a first-order differentiation. Exact measured/simulated spectral response can replace the class coefficients when available.

## Thermal limitation

The SAPM open-rack construction models use generic glass/glass or glass/polymer thermal parameters. Actual mounting, module construction, wind field and tracker/row interactions can change cell temperature.

## Optical limitation

The common physical-glass IAM improves absolute energy modeling but does not represent product-specific AR coatings or textured glass. Product-specific IAM measurements should supersede it when available.

## Economics boundary

The switching-point engine is not LCOE. It includes:

- actual module quote;
- discounted value of modeled DC energy;
- optional area-sensitive BOS proxy.

It excludes detailed inverter/electrical BOS, labor, logistics, tax, financing, O&M, availability, curtailment and replacement modeling.

## Decision rule

Solaryn does not need to declare a winner. It reports a stable energy leader only when the same module leads:

- broadband CEC-IV annual DC specific energy (without the class spectral proxy);
- spectral-adjusted annual DC specific energy; and
- the warranty-derived lifetime-energy scenario;

and every lead exceeds the user-visible minimum separation policy.

This safeguard prevents a first-order technology-class spectral proxy from silently creating the winner. If the leader changes across these declared scenarios, the output is **No robust winner under declared scenarios** and stronger module-specific evidence is required.

This is deterministic scenario stability, not statistical confidence.

## Validation status

Software/science integration: PoC.

External performance validation: pending.

Bankability validated: no.

Required next evidence: cross-model benchmark, module-specific data review, project-specific loss assumptions, and EPC/expert challenge.
# 2026-08-25 audit addendum

The independently rerun Riyadh 2020 three-candidate case reproduces Jinko 2073.433, First Solar 2048.638, and LONGi 2034.998 kWh/kWp/year. Jinko's 1.2103% nominal lead is below the declared 2% PoC decision guardrail. First Solar remains decision-ineligible because its CEC-style fallback is exploratory and no module-specific measured IEC 61853 matrix was supplied. The deterministic scientific conclusion therefore precedes the nominal leader: no robust cross-technology winner.

The resource chain reproduces NASA-to-pvlib POA 2346.767 versus PVGIS 2473.875 kWh/m2/year (-5.138%). This residual is documented monthly in `RESOURCE_BENCHMARK.csv` and is not bias-corrected. PVGIS horizon handling and source/model differences remain part of the boundary.

CEC STC fit residuals for the c-Si candidates are exported in `MODULE_FIT_RESIDUALS.csv`. Passing an STC fit target is an internal numerical diagnostic, not IEC conformity or candidate-specific measured off-STC validation. Separately, the measured IEC 61853 Pmax G-T interpolation layer passed external validation against the IEA PVPS Task 13 / SUPSI reference c-Si module and 12 months of outdoor observations. This layer-level result does not validate the Jinko/LONGi fallback models, cross-technology decisions, procurement, historical EPC performance, or bankability.

---

# 2026-08-28 final hardening addendum

The final offline regression suite passes 62/62 tests: the previously successful 54 tests, frozen three-candidate Riyadh, frozen four-candidate-universe, official PVGIS-orientation regressions, and five frontend UX contract regressions. Live NASA POWER and PVGIS integrations passed for Riyadh 2020 on 2026-08-28. The interactive Riyadh three-candidate Streamlit workflow passed on 2026-09-04 without supplier quotes; the commercial quote/economics path was not executed because no real quote was supplied. These statuses are reported separately.

The exact frozen candidate hashes are `e5953b0d0b3cbf873ef2c04c6780947547e90a115b3c10a6e877598626c0f590` for Jinko/First Solar/LONGi and `25ec930ffa48a856493cfcf88b8682181c065ec2d9bdf23946383a87cd7a7376` when REC is added. The nominal leader changes from Jinko to REC, making candidate-universe drift explicit; neither universe has a robust cross-technology winner.

Offline software regression PASS and date-specific live-service execution do not promote climate/resource, candidate-specific c-Si off-STC, cross-technology, economics, or historical EPC validation. The external measured IEC PASS is limited to the Pmax G-T interpolation layer for the supplied reference module. Bankability remains NOT CLAIMED.

---
