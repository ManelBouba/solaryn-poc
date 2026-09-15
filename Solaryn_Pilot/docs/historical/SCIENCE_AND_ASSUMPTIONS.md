# Science and assumptions

## Scientific position

Solaryn treats module selection as a **candidate-specific, site-specific decision problem**, not a universal ranking of PERC, TOPCon, HJT, back-contact, CdTe or CIGS. A technology label is useful for research and screening, but procurement decisions require product/SKU evidence and project constraints.

## Physics chain

### Solar resource and plane-of-array irradiance

The model uses a consistent solar/resource basis across candidates. The primary workflow can use 1, 3 or 5 complete hourly years; annual energy is averaged across years and the individual years are retained as shared interannual uncertainty scenarios. An independent PVGIS POA comparison is used as a decision-confidence gate rather than a hidden correction factor. Plane-of-array irradiance is conceptually:

`E_POA = E_beam + E_sky_diffuse + E_ground_reflected`

Transposition choice and geometry are common inputs, so resource differences cannot independently favor one candidate.

### Temperature

Module heat transfer is kept separate from electrical temperature sensitivity. The Faiman form used as a recognized thermal model is:

`T_module = T_ambient + E_POA / (U0 + U1 * wind_speed)`

Candidate/mount-specific coefficients are preferred when evidence exists. Generic coefficients are a fallback with wider uncertainty.

### Off-reference-condition electrical behavior

A single STC wattage and temperature coefficient are insufficient to represent a module over all operating conditions. Candidate-specific IEC 61853 P(G,T) data are the preferred electrical evidence. Datasheet-fitted electrical models are transparent fallbacks and are assigned larger model uncertainty.

Thin-film technologies must not be forced through silicon-specific parameterizations without applicable validation.

### Spectrum and incidence angle

Spectrum and angle-of-incidence can legitimately create climate-dependent differences, but Solaryn does not apply fixed family bonuses. Candidate-specific spectral responsivity/EQE and IAM data are preferred. Unsupported spectral differentiation stays a sensitivity rather than a primary winner-making mechanism.

### Bifacial response

Bifaciality is treated as a module/system property, not a standalone technology. When row/rear modeling is enabled, Solaryn uses a common pvlib infinite-sheds geometry (row shading, GCR, height, pitch, albedo) for every candidate and combines the modeled rear field with candidate-specific sourced bifaciality. No fixed annual bifacial uplift is assigned. If rear geometry is disabled, bifacial candidates receive no rear gain. Rear thermal coupling remains an explicit validation boundary rather than an invented absorption coefficient.

### Soiling and system effects

Soiling is a site/O&M process. Technology-specific soiling differences require evidence for actual glass/coating behavior. System effects such as inverter limits, clipping, mismatch, wiring, availability and curtailment can change delivered energy and must not be hidden inside a single unexplained annual loss scalar for investment-grade use.

## Lifetime treatment

The neutral common degradation scenario now uses compounded year-to-year retention:

`E_y = E_1 * product(1 - d_k)`

A common degradation path supports lifetime-energy projection but **does not differentiate product reliability**. Manufacturer warranty slopes are kept in a separate sensitivity path and are not presented as measured field degradation.

Product-level lifetime differentiation should only be activated when there is credible same-SKU/BOM field evidence, a closely matched analogue, or a calibrated mechanism-specific reliability model.

## Economics

General project NPV follows:

`NPV = -CAPEX + sum((Revenue_y - OPEX_y - Replacement_y) / (1+r)^y)`

LCOE is implemented as discounted lifetime costs divided by discounted delivered energy.

The module switching-value output answers a narrower procurement question: how much additional module price per watt can a candidate justify from modeled incremental value before it becomes economically indifferent to a baseline. In the current packaged workflow this is a **screening sensitivity**, not a complete project-finance result, unless real project costs/revenues are supplied.

## Uncertainty

Solaryn separates:

- shared uncertainty such as solar resource/interannual variation,
- candidate-specific model uncertainty such as electrical response and thermal evidence.

Evidence quality changes uncertainty width rather than adding a hidden performance bonus. Multi-year weather years are sampled jointly across candidates so resource uncertainty is correlated. Solaryn now reports two distinct probability views: **Decision P(best)** among evidence-eligible candidates and a clearly labeled **exploratory probability** including evidence-limited candidates. The latter can never promote an ineligible candidate into a procurement recommendation. Outputs also include expected regret and P50/P90 envelopes.

## Recommendation confidence gates

- **Resource confidence High:** independent annual POA sources differ by ≤5%.
- **Moderate:** >5% to 10%.
- **Low:** >10%; recommendation wording is capped at Conditional until reconciled.
- These are transparent product-governance bands, not scientific constants and they do not alter mean energy.
- If the numerical exploratory leader lacks decision-grade electrical evidence, Solaryn returns **No decision**.
- A common degradation scenario never upgrades lifetime evidence.

## Hard scientific boundaries

Solaryn does not intentionally include:

- hard-coded climate bonuses,
- universal technology-family degradation rates,
- arbitrary weighted scores that directly choose a winner,
- fixed bifacial gains without rear-irradiance modeling,
- fixed spectral gains without candidate-applicable evidence,
- benchmark-specific correction factors introduced after observing the target result.

## Primary references

- IEC 61215-1:2021: https://webstore.iec.ch/en/publication/61345
- IEC 61853-1:2011: https://webstore.iec.ch/en/publication/6035
- IEA PVPS climate optimisation: https://iea-pvps.org/key-topics/t13-optimisation-pv-systems-different-climates-2025/
- IEA PVPS project decisions: https://iea-pvps.org/key-topics/t13-pv-project-decisions-2026/
- Sandia PVPMC Faiman temperature model: https://pvpmc.sandia.gov/modeling-guide/2-dc-module-iv/module-temperature/faiman-module-temperature-model/
- Sandia PVPMC modeling guide: https://pvpmc.sandia.gov/modeling-guide/


## Robust recommendation claim gate

The numerical ranking and the recommendation label are separate. A large modeled gap is not sufficient for `Robust`. The strongest label additionally requires multi-year shared resource scenarios, strong independent resource agreement, measured/independently validated off-STC electrical evidence for the decision-critical candidates, strong thermal evidence, project-specific geometry, and no unvalidated decision-material rear-side contribution. These gates change wording only; they do not alter modeled mean energy.

The current rear-irradiance path uses pvlib infinite-sheds geometry and sourced product bifaciality. Until that path is independently validated against measured rear POA for the applicable project/geometry, a material bifacial rear contribution cannot by itself support `Robust` wording.
