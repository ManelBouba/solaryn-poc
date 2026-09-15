# Solaryn build validation

Executed on 11 September 2026.

- Full suite: **124 passed**, 11 non-failing NumPy timedelta deprecation warnings (118.79 seconds in the available environment).
- Retained all 99 tests from the latest supplied build; added 25 pilot regression/contract/UI cases. Existing equation fixtures now declare evidence eligibility explicitly without weakening their arithmetic assertions.
- Real-weather row geometry now returns positive energy and is invariant to integer versus timestamp indices.
- Four decision states, missing/false evidence, unreviewed claim evidence, all-zero rejection, tie symmetry, failed-candidate retention, immutable run hashes and report/JSON parity are covered.
- Independent switching calculation: 0.200 baseline + 0.020 energy difference + 0.004 area-BOS saving = 0.224 currency/W.
- Saved Riyadh full pipeline reproduces the accepted annual-energy regression.
- Offline replay reproduces annual/lifetime energy and decision status from delivered input snapshots.
- Iqaluit, Timokten and Leuven rerun from real recorded NASA POWER and PVGIS data. All seven selected candidates produce positive energy. No site receives a robust procurement winner.
- Fresh SUPSI measured-layer replay reproduces the recorded metrics and publishes input hashes, MAE, maximum error and interpolation/fallback fractions.
- Final browser check confirms the decision summary, rounded comparison table and seasonal charts render correctly; exact stored values remain unchanged.
- Missing optional economics inputs produce an actionable explanation rather than a raw field-name error.

Tests ran in the available Python environment with a generated 48-package runtime dependency lock. A fresh isolated dependency installation and Docker/cloud deployment were not performed. Scientific field-validation gaps remain explicitly PENDING; bankability is NOT_CLAIMED.
