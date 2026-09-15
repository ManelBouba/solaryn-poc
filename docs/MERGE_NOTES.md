# V7 Merge Notes

## Kept from `solaryn_poc_v7_modern_no_sidebar`
- modern no-sidebar Streamlit UI
- map-first project selection
- three-objective recommendation engine (`lifetime`, `value`, `risk`)
- explainability and comparison views
- PVGIS hourly source
- existing technology/material datasets

## Imported from `solaryn_v7_poc_step1_hourly_pvlib`
- NASA POWER true hourly downloader
- hourly GHI/DNI/DHI + meteorology schema
- `pvlib_pipeline.py`
- pvlib solar position
- pvlib plane-of-array irradiance
- pvlib Sandia cell temperature
- pvlib PVWatts DC implementation
- corrected hourly rain-cleaning handling
- hourly-data tests

## Integration choices
- NASA hourly + pvlib is the **primary physics path**.
- PVGIS is an **independent hourly cross-check**, not a replacement for NASA meteorology.
- The V6 single weighted `suitability_score` was **not reintroduced**.
- Forecast now accepts the same hourly weather used by ranking.
- Copilot payload was updated to understand the three independent decision objectives.
