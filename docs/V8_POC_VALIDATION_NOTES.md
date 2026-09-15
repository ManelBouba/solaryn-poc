# SOLARYN V8 — PoC Validation Notes

## Purpose

V8 converts the merged V7 prototype into a more defensible startup-validation PoC. It is deliberately narrower than the long-term Solaryn company vision.

## Product decision

The default experience is now a commercial project decision, not an open-ended research ranking. Research and pilot technologies are separated from the procurement candidate universe.

## Recommendation structure

The project user chooses what “best” means. Solaryn then returns a Top 3 with a visible project-fit score, underlying lifetime/value/risk lenses, reasons, trade-offs and a bounded PoC confidence indicator.

## Important modelling correction

The previous build multiplied a field-style annual degradation baseline by raw Arrhenius/Peck acceleration. This can create unrealistic annual degradation in hot climates because the two quantities do not share a validated calibration basis. V8 therefore uses the technology database baseline degradation for the 25-year scenario and retains Arrhenius/Peck as a relative environmental stress signal for climate-risk comparison.

## Bifacial boundary

Bifacial technologies remain in the database but are excluded from the default commercial ranking because rear-side irradiance and bifacial gain are not yet explicitly simulated.

## Validation behaviour

Offline regression tests verify that the default commercial universe excludes research and unmodelled bifacial variants, that a Top 3 is returned, and that the balanced PoC is not mechanically locked to a single winner across the supplied climate examples.

## What remains unresolved

Technology and material data provenance is incomplete; degradation and environmental stress parameters require evidence and calibration; the physics path is not yet technology-specific full I–V/device simulation; field data validation and uncertainty/P50-P90 are not yet implemented.
