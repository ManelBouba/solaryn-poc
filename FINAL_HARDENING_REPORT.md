# SOLARYN V9.2.1 final hardening report

Date: 2026-08-28. This pass changed reproducibility, regression coverage, orientation conversion, validation wording, and packaging only. It did not alter physics constants, irradiance models, module ranking logic, spectral assumptions, temperature assumptions, degradation assumptions, or decision thresholds.

## Verification

- Python compile: PASS.
- Offline automated regression: 64/64 PASS (original 54, three scientific hardening regressions, five frontend UX contract regressions, and two external measured DVP regressions).
- `src` line coverage: 66%.
- NASA POWER Riyadh 2020 live integration: PASS, 8,784 hourly rows.
- PVGIS Riyadh 2020 live integration: PASS, 8,784 hourly rows.
- Interactive Streamlit browser workflow: PASS on 2026-09-04 for the Riyadh 2020 three-candidate comparison without supplier quotes; the commercial quote/economics path remains unexecuted because no real quote was supplied.
- Upstream warning: pvlib imports emit one NumPy generic-timedelta deprecation warning.

## Frozen three-candidate case

- IDs: `MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530`, `MOD_PERC_LONGI_LR5_72HPH_550M`, `MOD_TOPCON_JINKO_JKM575N_72HL4_V`.
- Candidate-set SHA256: `e5953b0d0b3cbf873ef2c04c6780947547e90a115b3c10a6e877598626c0f590`.
- LONGi: 2034.9977553450485 kWh/kWp/year.
- Jinko: 2073.4330376001335 kWh/kWp/year.
- First Solar: 2048.638260682794 kWh/kWp/year, exploratory and decision-ineligible.
- Nominal leader: Jinko; lead 1.2103052741519815%; robust winner: none.

## Four-candidate universe

- Adds `MOD_HJT_REC_ALPHA_PURE_RX_470`.
- Candidate-set SHA256: `25ec930ffa48a856493cfcf88b8682181c065ec2d9bdf23946383a87cd7a7376`.
- REC: 2104.202038744053 kWh/kWp/year.
- Nominal leader: REC; lead 1.4839640627860653%; robust winner: none.

## Resource rerun

- NASA -> pvlib POA: 2346.7667558685853 kWh/m2/year.
- PVGIS POA: 2473.8748299999997 kWh/m2/year.
- Difference: -5.138015577425738%.
- Climate/resource validation remains PENDING; the residual was not calibrated away.

## Validation gates

The IEC 61853 Pmax G-T interpolation layer has external measured validation for one SUPSI reference c-Si module. Climate/resource, candidate-specific Jinko/LONGi off-STC, cross-technology, economics, and historical EPC validation remain PENDING. Bankability is NOT CLAIMED.
