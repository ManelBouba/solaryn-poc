# SOLARYN V9.2.1 Runtime Audit — EPC Module Offer Workflow

## Scope

This audit targets the live EPC module-offer failures observed in Streamlit, especially the CSV upload path. It does not change the SOLARYN physics equations or evidence hierarchy.

## Confirmed failures in V9.2

1. **Missing optional quote column crashed the page**
   - `app/epc_module_mode.py` directly selected `quote_usd_w` from the uploaded dataframe.
   - A valid physics CSV without that optional economics field therefore raised `KeyError: ['quote_usd_w'] not in index`.

2. **Blank template was easy to mistake for runnable input**
   - `data/raw/epc_module_offer_template.csv` contains the 39-column schema but zero rows.
   - Uploading it correctly failed validation, but the UI did not explain the template/example distinction before stopping.

3. **Several optional UI/evidence fields could cause later `KeyError`s**
   - The page later assumed `technology_label`, `project_segment`, `spectral_evidence_level`, `iec61853_matrix_file`, `cells_in_series_basis`, and evidence/source fields existed even though they are not all required by the core physics validator.

4. **Only one finite module result could be treated as a PoC comparison**
   - An exploratory candidate can remain visible with NaN energy after an allowed model failure.
   - `poc_validation_decision` previously required at least one finite result, not at least two, so a one-candidate finite result could receive an infinite separation gap and look stronger than it should.

5. **Excel/locale exports were fragile**
   - EU Excel can save semicolon-separated CSVs and decimal-comma numeric values.
   - The old loader assumed standard comma separation and dot decimals.

## Corrections in V9.2.1

- Added `src/module_offer_io.py` as the single EPC CSV ingestion/normalization path.
- Required physics fields remain strict and fail-closed.
- Optional quote/evidence/display fields are synthesized with explicit blank/neutral defaults.
- Missing or invalid supplier quotes disable economics instead of terminating physics comparison.
- Header-only files return a targeted explanation.
- Duplicate module IDs and duplicate normalized column names are rejected.
- Column names are trimmed/lower-cased and BOM-safe.
- Semicolon-separated EU Excel CSVs and decimal-comma/Unicode-minus numeric values are normalized before strict validation.
- Streamlit tables use safe `reindex` selection for optional metadata.
- Added a candidate-readiness table before simulation.
- Added a packaged three-module example CSV with blank supplier quotes.
- `poc_validation_decision` now requires **at least two finite simulated candidates**.
- Project site summary now uses the selected project segment instead of hard-coding `utility`.
- Report temperature labels were corrected from module temperature to cell temperature where the underlying metric is cell temperature.

## Verification performed

- `pytest -q`: **50 passed**.
- `python -m compileall -q app src tests`: **passed**.
- Regression coverage includes:
  - blank header-only template;
  - missing `quote_usd_w`;
  - missing optional UI/evidence fields;
  - whitespace/case-normalized headers;
  - duplicate module IDs;
  - semicolon/decimal-comma Excel export;
  - only one finite simulated candidate.

## Runtime not executed in this audit environment

The sandbox does not have `pvlib`, `NREL-PySAM`, `streamlit`, or `streamlit-folium` preinstalled and cannot download packages from PyPI. Therefore the live NASA POWER → pvlib → PySAM → Streamlit path could not be executed here. The package still declares these dependencies in `requirements.txt` and the corrected logic is covered by unit/regression tests and compilation.

## Remaining scientific validation boundary

This runtime patch does **not** validate module energy accuracy, IEC 61853 interpolation accuracy, First Solar/CdTe model form, P50/P90, bifacial gain, full LCOE, or bankability. Those remain separate validation tasks.
