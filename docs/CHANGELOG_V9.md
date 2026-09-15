# SOLARYN V9 Bias-Correction Changelog

## Baseline

Forked from `SOLARYN_V8_2_DB_IV_EPC_SCIENCE_CORRECTED` after reproducing the legacy technology-screening bias pattern. The EPC/module path is retained as the commercial foundation; the legacy technology/material ranking remains explicitly research-only.

## Decision architecture changes

1. Added an IEC-61853-style module-specific G-T performance-matrix engine with evidence validation and interpolation/extrapolation diagnostics.
2. Added model-evidence policy. Module-specific measured matrix is preferred. Crystalline-silicon candidates may use a datasheet-fitted CEC single-diode fallback. Non-c-Si candidates without validated module-specific evidence fail closed for robust cross-technology decisions.
3. Removed legacy resilience/technology scores from the EPC decision path. The EPC path does not import `recommendation_engine.py`.
4. Added a declared uncertainty guardrail and a `NO ROBUST WINNER` outcome when numerical separation is below the threshold or model evidence is incomplete.
5. Separated broadband primary energy from technology-class spectral sensitivity. Current spectral proxy cannot manufacture the primary winner.
6. Separated common-degradation lifetime comparison from manufacturer-warranty sensitivity. Warranty language cannot manufacture the primary lifetime winner.
7. Blocked economic switching conclusions for physics/model-ineligible candidates.
8. Added project-segment compatibility to prevent residential and utility products from being compared as if they were interchangeable.

## Physics/data changes

1. Hourly site comparison is gated to a near-complete reference year before annual/lifetime labels are populated.
2. POA transposition changed to Perez-Driesse for anisotropic diffuse treatment.
3. Surface-pressure unit handling was hardened to avoid kPa/hPa/Pa magnitude ambiguity.
4. Module temperature evidence hierarchy now prefers module-specific Faiman U0/U1; SAPM construction-class parameters are a disclosed fallback.
5. The IEC matrix uses module/device temperature; CEC single-diode uses cell temperature.
6. Technology-family low-light scores are not used by the EPC engine; low-light behavior must emerge from a module-specific G-T matrix or an accepted physical model.
7. Technology-class spectral behavior remains sensitivity-only until module-specific spectral response is coupled to time-resolved spectral irradiance.
8. BOM/climate degradation coefficients are not invented. Stress-exposure diagnostics may be shown, but calibrated degradation requires empirical BOM/module evidence.

## Evidence and audit changes

- Added source/evidence fields for IEC matrix, spectral response, IAM, U0/U1, model validation and BOM references.
- Added `docs/PARAMETER_AUDIT_V9.csv`, now explicitly classifying all 39 commercial module-master fields plus project, climate, optical, electrical, lifetime, economics and decision parameters (84 rows total).
- Added `docs/V8_2_TO_V9_CODE_DIFF.patch`, a line-by-line implementation diff against the V8.2 baseline.
- Added legacy bias audit and synthetic anti-bias behavior fixtures/results.

## Validation status

- Original V8.2 internal suite: 19 passing tests.
- V9 final internal suite: 38 passing tests.
- Python compileall: PASS.
- Legacy bias pattern: reproduced and archived.
- Synthetic G-T leader-switch test: PASS; software-behavior test only.
- Measured IEA/Sandia Annex-1 field validation: PENDING because dataset bytes and pvlib/PySAM runtime were not available in this execution environment.
- PVsyst/PAN and PVGIS external benchmarks: PENDING.

No claim of bankability-grade or measured predictive validation is made by this build.
