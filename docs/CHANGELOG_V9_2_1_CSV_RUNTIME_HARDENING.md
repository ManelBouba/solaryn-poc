# SOLARYN V9.2.1 — EPC CSV Runtime Hardening

This patch fixes the upload/runtime failures observed during live EPC module-offer testing without changing the physics, evidence hierarchy, lifetime equations, or switching-point equations.

## Fixed

- Missing optional `quote_usd_w` no longer raises a Pandas `KeyError`; the field is synthesized as blank/NaN and economics remains disabled until a real quote is entered.
- User CSV column names are normalized (trimmed and lower-cased) before schema checks.
- Header-only/blank templates now return a specific explanation instead of a generic failure.
- Optional UI/evidence columns (`project_segment`, `spectral_evidence_level`, `iec61853_matrix_file`, source fields, etc.) are synthesized with explicit neutral defaults rather than crashing later table renders.
- Duplicate `module_id` values and duplicate normalized column names are rejected with actionable messages.
- Quote values are parsed safely; blank/non-numeric quotes remain NaN and negative quotes are rejected.
- UI tables use safe `reindex(...)` selection so missing optional metadata cannot terminate the page.
- A candidate-readiness table now shows electrical-model evidence and quote readiness before simulation.
- Download controls are shown before upload validation, so users can recover from an invalid file immediately.
- Added a populated three-module example CSV using the packaged datasheet seed records; supplier quotes remain intentionally blank.

## Validation

- Automated tests: 50 passed.
- Python compile check: passed.
- Added seven regression tests covering the exact CSV/runtime failures observed in the UI.

## Scientific boundary

No module prices, IEC 61853 measurements, thermal coefficients, spectral evidence, or degradation parameters are fabricated by this patch. Missing commercial evidence disables only the dependent economic output; required physics fields remain fail-closed.
