# SOLARYN correction and validation plan

## Change-control rule

Preserve the reproduced physics constants and benchmark outputs unless a failing independent test proves a defect. Every behavior change receives a regression test and changelog entry. Generic spectral, warranty, material, and stress scores remain outside the primary EPC winner calculation.

## Software and schema

1. Fix locale-dependent tests and add import/report smoke coverage.
2. Harden empty/failed simulation handling before result-column access.
3. Expand CSV tests for blank/header-only, 1/2/many rows, optional quotes, missing critical fields, duplicates, localized separators/decimal commas, Unicode minus, normalized headers, reordering, extras, and malformed values.
4. Add deterministic benchmark tooling and keep live NASA/PVGIS tests separately marked.

Acceptance: supported workflows have no unhandled exception; offline tests do not require web APIs; invalid physics input names the exact field/row.

## Climate/resource

1. Freeze year, coordinates, UTC timestamps, 8,784 leap-year hours, tilt, azimuth, albedo, horizon metadata, and transposition model.
2. Export monthly NASA GHI/DNI/DHI, SOLARYN POA, PVGIS POA, absolute residual, and percentage residual plus annual total.
3. Diagnose missing hours and component consistency. Do not bias-correct NASA to PVGIS.

Acceptance: monthly totals reconcile to annual sums and all boundary differences are disclosed. A climate/resource scientific PASS requires independent evidence beyond successful code execution; current status remains PENDING.

## Module electrical physics

1. Export datasheet identity/consistency and fitted STC residuals for Jinko and LONGi.
2. Test temperature direction, irradiance direction, night zero, IAM bounds, soiling monotonicity, annual integration, and 100 MWp scaling.
3. Retain First Solar as exploratory and decision-ineligible without module-specific measured evidence.

Acceptance: c-Si Pmp internal investigation target is within +/-1% at STC and all residuals are visible. Cross-technology and IEC gates remain PENDING until measured holdout evidence exists.

## IEC 61853 measured validation

When legally usable measured data are supplied, pre-register a calibration/holdout split, fit/interpolate calibration only, and report MBE, MAE, RMSE, normalized RMSE, maximum absolute residual, interpolation fraction, extrapolation fraction, and nearest fallback fraction. Do not fabricate or populate the blank template. Until then `MEASURED_VALIDATION_RESULTS.csv` records PENDING/no measured dataset.

## Decision and reporting

1. Deterministic scientific status precedes any nominal leader in UI and HTML.
2. Implement and test robust, provisional/tied, no robust winner, and insufficient-evidence cases.
3. Ensure explanatory/AI text cannot override the deterministic status.
4. Describe 2% only as a declared PoC validation/decision guardrail.

Acceptance: below-guardrail, sensitivity-flip, or incomplete-evidence cases cannot headline a robust winner.

## Economics

Add an independent hand calculation for `allowable price A = baseline price B + discounted energy-value difference + area-BOS difference`. Missing quotes disable economics without affecting physics. Continue to use "module + area-BOS switching threshold," never LCOE.

## Regression matrix and external validation

Create frozen-resource regression cases for Riyadh, Brussels, Algiers, and a cold/high-irradiance site. Store numerical tolerances and investigate dependency-driven changes. Separate opt-in live NASA/PVGIS smoke tests. External PVsyst/PAN/SAM and historical procurement gates remain PENDING until inputs are supplied.

## Final gates

Software/runtime and numerical implementation may pass on code/test evidence. Climate/resource, c-Si scientific validation, cross-technology, IEC measured-data, economics procurement validation, and historical EPC validation require their stated external evidence; test execution alone cannot promote them.
