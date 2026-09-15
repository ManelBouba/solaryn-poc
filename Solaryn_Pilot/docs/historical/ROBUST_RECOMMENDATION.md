# Robust recommendation architecture

Solaryn separates a **numerical model result** from a **decision-grade recommendation**.

## Decision sequence

1. **Resource** — use multiple complete hourly resource years where available. Annual outputs are the mean across years, not the sum of years.
2. **Independent resource check** — compare annual POA against PVGIS. Resource agreement is reported as High (≤5% difference), Moderate (>5–10%), or Low (>10%). These are configurable product-governance bands; they change claim strength, not the modeled mean.
3. **Common geometry** — every candidate sees the same tilt, azimuth, row layout, albedo, soiling and resource realization.
4. **Rear irradiance** — when enabled, pvlib infinite-sheds geometry models front/rear irradiance and row shading. Candidate bifaciality converts rear irradiance to electrical contribution; no fixed annual bifacial bonus is used.
5. **Thermal model** — Faiman/SAPM routing remains separate from electrical temperature sensitivity. Rear thermal coupling is not assigned an invented absorption coefficient; it remains an explicit model boundary until validated.
6. **Electrical response** — candidate-specific IEC 61853 P(G,T) is preferred. Crystalline-silicon datasheet fits remain a fallback with wider uncertainty. Unsupported model forms remain exploratory and decision-ineligible.
7. **Uncertainty** — multi-year calendar years are sampled as a *shared* resource scenario for all candidates; candidate-model residual uncertainty remains candidate-specific.
8. **Two probability frontiers** — `Decision P(best)` is calculated only among decision-eligible candidates. Evidence-ineligible candidates retain a separate exploratory probability for falsification/evidence planning.
9. **Lifetime** — the common 25-year degradation path is explicitly a neutral sensitivity. It cannot establish a lifetime technology winner.
10. **Decision** — Solaryn can return Robust, Probable, Conditional, or No decision. A low resource-confidence input or an evidence-limited competing candidate prevents overconfident recommendation wording.

## What “Robust” now requires

`Robust` is deliberately hard to earn. The strongest label requires all of the following at the same time:

- at least two decision-eligible candidates and no selected evidence-ineligible competitor,
- High independent resource agreement,
- at least two complete resource years so interannual variability is sampled empirically and shared across candidates,
- measured IEC 61853 P(G,T) or independently validated off-STC electrical evidence for the top decision candidates,
- module-specific, measured, or independently validated thermal evidence for the top decision candidates,
- project-design or measured geometry rather than generic screening geometry,
- no decision-material rear-side contribution unless the rear-POA path has independent measured validation (the current packaged rear model is therefore capped below Robust when rear gain is material),
- the configured P(best), expected-regret, and deterministic separation guardrails all pass.

These are claim-strength gates, not hidden ranking weights. Failing a gate does not change modeled mean energy; it changes what Solaryn is allowed to say about that result.

## Physics diagnostics

Each candidate returns diagnostic ablations from the same hourly simulation:

- off-STC irradiance-response effect,
- temperature-response effect,
- rear-side energy contribution,
- front geometry/IAM effect,
- P95 cell/module temperature,
- annual front/rear optical POA,
- electrical/thermal evidence path.

These diagnostics explain the ranking; they are **not additive weighted scores**.

## Claim boundary

The included measured SUPSI / IEA PVPS Task 13 validation supports the measured GPOA + measured module temperature → IEC Pmax(G,T) layer. It does not independently validate resource, POA transposition, every commercial SKU, rear irradiance, cross-technology ranking, lifetime, AC delivery or economics.

## Primary methodology references

- IEA PVPS, Climatic Rating of Photovoltaic Modules: https://iea-pvps.org/key-topics/climatic-rating-of-photovoltaic-modules/
- pvlib, total in-plane irradiance: https://pvlib-python.readthedocs.io/en/v0.13.1/reference/generated/pvlib.irradiance.get_total_irradiance.html
- pvlib, infinite-sheds bifacial model: https://pvlib-python.readthedocs.io/en/v0.13.0/reference/generated/pvlib.bifacial.infinite_sheds.get_irradiance.html
- NREL, Quantifying Uncertainty in PV Energy: https://www.nrel.gov/docs/fy23osti/84993.pdf
- Sandia PVPMC modeling guide: https://pvpmc.sandia.gov/modeling-guide/
