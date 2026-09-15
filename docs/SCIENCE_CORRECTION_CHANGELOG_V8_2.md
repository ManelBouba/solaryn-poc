# SOLARYN V8.2 — Science Correction Changelog

## What was preserved

- Existing Solaryn map-first product and modern UI.
- Original 30-technology master database.
- Material physics, layer stack, defects/contacts, cost/market and evidence data.
- NASA POWER, PVGIS and pvlib foundations.
- Research-oriented technology/material screening path.

## What was corrected for EPC use

1. Added a strict actual-module path linked back to original `technology_id` records.
2. EPC IV simulation requires sourced STC module inputs and refuses physically inconsistent rows.
3. CEC five-parameter fitting uses datasheet Vmp/Imp/Voc/Isc and correctly converted current/voltage temperature coefficients.
4. Hourly operating points use `calcparams_cec` + `singlediode`; the EPC path does not fall back to the research score.
5. Added common front-glass IAM and retained both broadband and technology-class spectral-adjusted results.
6. A class spectral proxy is not allowed to silently create a robust winner.
7. Common project soiling is applied to all EPC candidates; legacy technology soiling-resilience scores do not rank procurement offers.
8. Heat/humidity/UV/thermal-cycle calculations are exposure diagnostics only; they do not create an invented degradation percentage.
9. Manufacturer power-warranty endpoints are translated to an explicit lifetime-energy scenario, not a field degradation prediction or energy guarantee.
10. Module price is blank until the EPC supplies a real quote.
11. Switching-point economics reports an indifference module price plus area-sensitive BOS proxy; it is explicitly not LCOE.
12. Solaryn refuses a robust winner when broadband, spectral-adjusted, and lifetime-scenario leaders disagree or are separated by less than the visible policy threshold.
13. Project-scale DC MWh is derived transparently from specific energy and project MWp; no inverter/AC claim is implied.

## Still not claimed

- PVsyst-equivalent bankability.
- Exact product-specific spectral response without EQE/spectral data.
- Calibrated climate-driven annual degradation.
- Full LCOE.
- AC yield, availability, curtailment, shading/mismatch, or tracker/bifacial behavior.
- Lender-grade P50/P90.

## Validation gate before a real EPC pilot

Run `docs/VALIDATION_PROTOCOL.md`. The next milestone is benchmark validation, not new product features.
