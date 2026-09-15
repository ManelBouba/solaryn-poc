# SOLARYN V9.2.1 architecture map

## Scope and entry points

- `app/streamlit_app.py` is the Streamlit entry point. It exposes a legacy technology-screening view and delegates the commercial workflow to `app/epc_module_mode.py`.
- `app/epc_module_mode.py` owns project inputs, map/location selection, module CSV upload, climate fetch orchestration, module simulation, deterministic decisions, economics, tables, and report downloads.
- `run_pipeline.py` is explicitly a legacy research-screening runner; it is not the EPC procurement engine.

## End-to-end EPC data flow

`Project input` -> `NASA POWER hourly` -> `pvlib solar position and irradiance` -> `front-surface POA` -> `IAM-adjusted optical POA` -> `module/cell temperature` -> `IEC matrix or CEC single-diode model` -> `hourly module Pmp` -> `annual DC specific energy` -> `common and warranty lifetime scenarios` -> `evidence policy and deterministic guardrail` -> `optional module + area-BOS switching threshold` -> `Streamlit and HTML report`.

### Project input and candidates

- Project controls: `app/epc_module_mode.py::render_epc_module_mode`.
- CSV parsing and canonicalization: `src/module_offer_io.py`.
- Strict electrical validation: `src/module_iv_engine.py::validate_module_candidates`.
- Segment compatibility and evidence policy: `src/evidence_policy.py`.
- Seed candidates: `data/raw/module_candidate_master.csv`; user template and example are in the same directory.

### Climate and resource

- NASA POWER and PVGIS HTTP clients/parsers: `src/data_fetchers.py`.
- NASA timestamps are requested and parsed as UTC. The 2020 leap year produces 8,784 hourly rows.
- `src/pvlib_pipeline.py::nasa_hourly_to_pvlib_weather` computes solar position, retains NASA GHI/DNI/DHI when present, uses Erbs only for missing direct/diffuse components, and applies Perez-Driesse transposition at fixed tilt/azimuth with albedo 0.20.
- POA columns include raw front-surface POA and component terms. IAM creates a separate `poa_optical_w_m2` used by electrical and thermal calculations.
- PVGIS `seriescalc` is an independent in-plane-resource cross-check with horizon enabled. It is not used to calibrate NASA.

### Temperature, spectrum, and electrical power

- `src/module_iv_engine.py::module_operating_temperatures` uses module-specific Faiman U0/U1 when present; otherwise it uses a construction-class SAPM fallback and returns module and cell temperatures separately.
- `spectral_factor_for_module` uses pvlib's technology-class First Solar spectral factor only as a sensitivity unless module-specific evidence policy permits decision use. Unsupported hours are neutralized to 1.0 and disclosed.
- `electrical_model_policy` selects a module-specific IEC 61853-style matrix when available. c-Si otherwise uses a CEC single-diode datasheet fit. Non-c-Si using that fallback is explicitly exploratory and decision-ineligible.
- `src/iec61853_engine.py` validates G-T-Pmax matrices and uses linear interpolation with nearest-neighbor fallback; extrapolation/fallback fractions are reported.
- `simulate_module_hourly` integrates hourly `Pmp / datasheet Pmax` to kWh/kWp. The primary decision value is broadband unless module-specific spectral evidence is available.

### Lifetime, stress, decision, and economics

- `src/lifetime_engine.py` keeps common degradation and manufacturer-warranty scenarios separate.
- `src/degradation_stress.py` computes heat/humidity/thermal-cycle exposure diagnostics and does not convert them into degradation rates.
- `src/epc_decision.py` produces both a strict evidence/guardrail result and a nominal PoC ranking. The 2% value is a deterministic PoC decision guardrail, not a probability or confidence interval.
- `src/economics_engine.py` computes a module + area-BOS switching threshold. Missing baseline quotes disable economics; no prices are imputed.
- `src/epc_report.py` generates the downloadable HTML report. `src/copilot_prompt.py` creates explanatory text but does not control deterministic status.

## Tests and evidence assets

- Existing tests cover data fetch parsing, module input validation, core physics helpers, evidence policy, decision logic, and bias-control rules.
- `data/raw/iec61853_matrix_template.csv` is a blank template, not measured evidence. No measured IEC matrix or external PVsyst/PAN/SAM export exists under `external_validation/`.
- Source/evidence documentation is under `docs/`, notably `EPC_SCIENCE_MODEL_CARD.md`, `SOURCE_EVIDENCE_MAP.md`, `SOURCES_AND_ASSUMPTIONS.md`, and `VALIDATION_PROTOCOL.md`.

## Boundary between commercial and research paths

The commercial EPC path uses exact module records, hourly resource, electrical quantities, evidence grades, and quotes. `src/recommendation_engine.py` and the material/device tables support research screening only and must not enter EPC winner selection.
