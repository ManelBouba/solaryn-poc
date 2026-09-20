# SOLARYN Scientific Corrections V5 — 2026-09-17

This patch hardens the evidence-aware V4 implementation after an external technical review.

## Corrections

1. **IEC TS 63126 T98 definition** — the primary qualification statistic is now the annual all-hours 98th percentile of modeled module temperature. The previous daylight-only P98 is retained only as a diagnostic. No unsupported irradiance threshold is presented as part of the IEC definition.
2. **Bifacial physics** — the active engine already uses `pvlib.bifacial.infinite_sheds.get_irradiance`; no handwritten rear-view-factor patch was introduced.
3. **Reliability gates remain evidence-based** — no universal rule such as `EVA + tropical => fail` or `technology X => coastal-safe` was added. Missing IEC 61701 / damp-heat / snow-load evidence is conditional unless the user explicitly selects a hard qualification policy.
4. **Uncertainty calibration hierarchy** — candidate-specific validation residuals / measurement uncertainty now override screening priors. Screening priors are explicitly fallbacks, not universal IEC/evidence-grade constants.
5. **No fabricated multi-site winners** — no city-to-technology rules and no hard-coded diverse recommendations were added.

## Remaining boundary

Cross-technology recommendations remain only as strong as the product-specific off-STC, bifacial, BOM, degradation, qualification and price evidence supplied for the exact candidates. Missing evidence must remain visible in the Decision Trace.
