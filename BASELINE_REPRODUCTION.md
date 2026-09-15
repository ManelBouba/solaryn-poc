# SOLARYN V9.2.1 baseline reproduction

Baseline captured on 2026-08-25 before production-code changes, on Windows in `Europe/Paris`.

## Environment

| Component | Version |
|---|---:|
| Python | 3.12.10 |
| pvlib | 0.15.2 |
| NREL-PySAM | 7.1.1.post1 |
| pandas | 2.3.3 |
| numpy | 2.5.2 |
| scipy | 1.18.1 |
| Streamlit | 1.62.0 |
| pytest | 8.4.2 |
| requests | 2.34.2 |

The repository includes `requirements.txt` but no exact cross-platform lockfile. The working directory contains no Git metadata; the supplied ZIP and `FILE_MANIFEST_SHA256.txt` are the immutable source baseline.

## Commands and outcomes

- `.venv\Scripts\python.exe -m compileall -q app src tests run_pipeline.py`: PASS.
- import smoke test of the Streamlit entry point and core modules: FAIL. Importing `app.streamlit_app` executes the page in bare mode and reaches `results["annual_dc_specific_energy_kwh_kwp"]` with an empty/unshaped result table, raising `KeyError`.
- `.venv\Scripts\python.exe -m pytest -ra`: 48 passed, 2 failed, 1 warning. Both failures use `Path.read_text()` without an encoding and fail on UTF-8 source under Windows CP-1252. pvlib also emits one NumPy timedelta deprecation warning.
- `.venv\Scripts\python.exe run_pipeline.py`: PASS, but this is the research-screening runner and does not exercise the EPC chain.
- Live NASA POWER + pvlib + module engine + PVGIS benchmark: PASS after network permission was granted.

## Riyadh frozen assumptions

Latitude 24.7136, longitude 46.6753, calendar year 2020, 100 MWp project scaling, utility segment, fixed tilt 25 degrees, azimuth 180 degrees, monofacial front side, albedo 0.20, common soiling loss 2%, common degradation scenario 0.5%/year, and PoC guardrail 2%.

## Exact three-candidate result

| Candidate | Annual DC specific energy (kWh/kWp/year) | Electrical model | Decision eligible |
|---|---:|---|---|
| JinkoSolar JKM575N-72HL4-V | 2073.433038 | c-Si CEC single-diode datasheet fit | Yes |
| First Solar Series 7 TR1 530 | 2048.638261 | CEC single-diode exploratory only | No |
| LONGi LR5-72HPH-550M | 2034.997755 | c-Si CEC single-diode datasheet fit | Yes |

Jinko's lead over First Solar is 1.210305%. This is below the 2% guardrail. The strict deterministic result is: no robust cross-technology winner because at least one selected candidate lacks an accepted decision-grade model/evidence path.

## Resource reproduction

- NASA POWER rows: 8,784 (complete leap year in UTC).
- NASA -> pvlib POA: 2346.766756 kWh/m2/year.
- PVGIS in-plane irradiation: 2473.874830 kWh/m2/year.
- Difference `(NASA - PVGIS) / PVGIS`: -5.137985%.

The year, coordinates, tilt, and orientation are harmonized. Remaining boundary differences include source datasets, PVGIS horizon handling, albedo/model metadata, and transposition implementation. The residual must not be removed by tuning.

## Default-selection drift

The packaged master file contains a fourth module, REC Alpha Pure-RX 470. Selecting all defaults produces REC at 2104.202039 kWh/kWp/year, 1.483964% ahead of Jinko. Therefore the historical three-candidate report is reproducible only when its candidate set is explicitly frozen; the UI default is not itself a stable regression case.

## Baseline warnings and limitations

- No frozen NASA/PVGIS response is packaged, so the exact benchmark depends on live services.
- No measured IEC 61853 matrix, holdout set, external PVsyst/PAN/SAM benchmark, actual supplier quote, or historical closed-procurement record is present.
- The supplied HTML is a prior generated artifact and is not proof that the current default UI path remains reproducible.
