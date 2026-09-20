# SOLARYN Evidence-Aware Decision Engine v4

Date: 2026-09-17

## Why this upgrade exists

The prior PoC could allow the Pmax temperature coefficient to dominate candidate separation whenever product-specific irradiance, spectral, angular, bifacial, degradation and reliability evidence was absent or shared. This release does **not** hard-code climate-to-technology winners. It adds independent, traceable pathways so a candidate can gain or lose value for documented physical, qualification and economic reasons.

## Implemented in this release

### 1. Product/BOM evidence layer
- New `src/evidence_hierarchy.py`.
- Grades electrical, thermal, spectral, BOM, degradation and qualification evidence using A/B/C/D evidence levels.
- Evidence grade controls confidence/claim strength and uncertainty width; it does **not** silently alter modeled mean energy.

### 2. Site qualification / reliability gates
- New `src/site_qualification.py`.
- Calculates daylight module T98 and maps it to high-temperature qualification requirements.
- Coastal/salinity exposure can require IEC 61701 evidence.
- High-humidity exposure can require damp-heat/BOM evidence.
- Snow exposure triggers a mechanical snow-load review requirement.
- Missing evidence is `conditional` by default, or can be a hard exclusion when `hard_qualification_gates=true`.
- Salinity is not inferred from coordinates without a declared/geospatial salinity data source.

### 3. Snow physics
- `src/module_iv_engine.py` now has an NREL/pvlib snow-coverage and DC-loss path.
- The snow model runs only when direct snowfall data are supplied. Rain is never silently converted to snow.
- Optional snow depth is supported.
- Snow losses are applied to decision irradiance and exported in hourly diagnostics.

### 4. Dynamic albedo / bifacial pathway
- Hourly `surface_albedo` can now override the common scalar albedo when an upstream source provides it.
- Existing pvlib bifacial geometry remains the rear-irradiance pathway; no fixed technology bonus is introduced.

### 5. High-temperature diagnostics
- Candidate summaries now include daylight P98 module and cell temperature.
- T98 is used by the qualification layer rather than average ambient temperature alone.

### 6. Lifetime uncertainty
- `src/lifetime_engine.py` adds a lifetime-energy distribution with P50/P90 output.
- The default mean degradation remains a common project assumption unless product evidence exists; technology-family labels do not receive arbitrary mean degradation bonuses.
- Evidence affects uncertainty width, not the modeled mean.

### 7. Correlated Monte Carlo decision layer
- `src/pilot_service.py` now calls the existing correlated candidate uncertainty engine.
- Outputs include candidate probability of best.
- A low probability of best triggers `NO_CLEAR_WINNER_UNDER_UNCERTAINTY` instead of manufacturing a winner.

### 8. Economics and procurement
- `src/economics_engine.py` retains maximum justified premium / switching price and now exposes a net lifetime value index when a quote is available.
- When all eligible candidates have real quotes, procurement recommendation is based on net lifetime economic value rather than highest annual yield alone.
- Without real quotes, the output remains explicitly a technical lifetime-performance screening.

### 9. Decision trace
- New `src/decision_trace.py` produces a structured chain:
  `Site -> Climate stress -> Product response -> Reliability/evidence -> Lifetime -> Economics -> Decision`.
- Candidate outputs include evidence grade, missing qualification evidence, lifetime P50/P90 and limitations.

### 10. Platform controls
The physical simulation UI/API now includes:
- explicit salinity/coastal exposure;
- conditional vs hard qualification policy;
- snow-model enable/disable.

These values are passed through `Solaryn_Platform/physics_worker.py` to the science core.

## Deliberately NOT implemented as shortcuts

- No `if hot: CdTe`, `if snow: TOPCon`, or any coordinate/technology lookup.
- No generic family-level humidity score.
- No automatic coastal classification from latitude/longitude without a defensible salinity dataset.
- No fixed bifacial gain when rear irradiance cannot be calculated.
- No claim that IEC 61215 qualification predicts lifetime.
- No evidence-grade multiplier on expected energy.

## Existing strong parts preserved

The uploaded code already contained several scientifically useful pieces and they were preserved rather than rewritten:
- pvlib-based POA / IAM / temperature workflow;
- exact IEC 61853 matrix path when supplied;
- CEC/single-diode datasheet fallback;
- bifacial infinite-sheds geometry;
- existing correlated Monte Carlo engine;
- switching-price economics;
- independent SUPSI/IEA-PVPS electrical benchmark replay.

## Validation performed here

- Modified Python modules compile successfully.
- New evidence-aware unit tests: **5 passed**.
- Combined new tests + existing procurement tests: **20 passed; 1 environment-only failure** because `streamlit` is not installed in this execution environment.
- A full end-to-end hourly rerun was not possible in this environment because `pvlib`, `PySAM`, and `streamlit` are not installed and external package installation is unavailable. The project requirements already declare pvlib/PySAM; run the full suite in the normal SOLARYN virtual environment before using screenshots or pitch numbers.

## What still needs real data to unlock genuinely diverse recommendations

Different technology winners should emerge only when the candidate records contain differentiating evidence. Highest priorities:
1. product-specific IEC 61853 matrices or validated PAN/CEC/SAPM parameters;
2. measured/declared bifaciality plus actual rear-irradiance geometry and time-varying albedo;
3. direct snowfall/snow-depth data for snow-loss modeling;
4. product/BOM damp-heat, PID, thermal-cycle, mechanical-load and salt-mist evidence;
5. product-/field-specific degradation distributions;
6. real supplier quotes and BOS deltas;
7. independent measured-site validation.

If those inputs remain identical or missing across candidates, the engine must be allowed to return a close ranking or `NO CLEAR WINNER` rather than fabricating separation.

## Primary modified/new files

- `Solaryn_Pilot/src/evidence_hierarchy.py` (new)
- `Solaryn_Pilot/src/site_qualification.py` (new)
- `Solaryn_Pilot/src/decision_trace.py` (new)
- `Solaryn_Pilot/src/module_iv_engine.py`
- `Solaryn_Pilot/src/pvlib_pipeline.py`
- `Solaryn_Pilot/src/lifetime_engine.py`
- `Solaryn_Pilot/src/economics_engine.py`
- `Solaryn_Pilot/src/pilot_service.py`
- `Solaryn_Pilot/tests/test_evidence_aware_upgrade.py` (new)
- `Solaryn_Platform/server.py`
- `Solaryn_Platform/physics_worker.py`
- `Solaryn_Platform/web/physics.js`
