# Final validation gates

| Gate | Status | Basis |
|---|---|---|
| Software/runtime | PASS (offline regression) | Compile succeeds and 64/64 offline tests pass, including two external measured DVP regressions. Live NASA and PVGIS Riyadh smoke/integration runs passed on 2026-09-08. The interactive Riyadh three-candidate Streamlit workflow passed on 2026-09-04 without supplier quotes. |
| Numerical implementation | PASS | Existing equation tests plus STC/directional tests pass; switching and lifetime calculations have independent checks. This is not scientific validation. |
| Climate/resource validation | PENDING | Same-year/geometry comparison is complete, but the -5.138% residual lacks site measurement or external engineering-model adjudication. |
| c-Si module model validation | PARTIAL | The IEC 61853 Pmax G-T interpolation layer passed external 12-month validation for one SUPSI reference c-Si module. Jinko/LONGi use a datasheet-fitted fallback and remain candidate-specific PENDING. |
| Cross-technology validation | PENDING | First Solar remains exploratory and decision-ineligible. |
| IEC measured-data validation | PASS — LAYER ONLY | IEA PVPS Task 13 / SUPSI matrix and 28,286 retained outdoor observations validate the measured Pmax G-T interpolation layer: RMSE 18.163 W (6.358% STC), R² 0.9359, cumulative sampled-energy bias -0.0084%. This does not validate the full decision workflow. |
| Decision logic | PASS | Deterministic evidence/guardrail status now precedes the nominal leader; sensitivity/evidence rules are automated. |
| Economics | PENDING | Equation tests pass, but no real authorized supplier quotes or historical procurement data were supplied. |
| Historical EPC validation | PENDING | No closed EPC decision dataset supplied. |
| Bankability | NOT CLAIMED | No lender-grade uncertainty, loss stack, field validation, or financing model. |

Live API success is service- and date-specific. It does not promote climate/resource validation from PENDING or replace deterministic frozen fixtures in CI.

## Current Riyadh scientific conclusion

No robust cross-technology winner. JinkoSolar JKM575N-72HL4-V has the highest provisional modeled annual DC specific energy among the frozen three candidates at 2073.43 kWh/kWp/year, but its 1.2103% lead is below the 2% PoC decision guardrail and First Solar lacks decision-grade cross-technology model evidence.
