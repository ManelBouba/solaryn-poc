# Solaryn refactor and validation report

## 1. Cleanup

The delivery was reduced from **288 files in the supplied tree to a focused application package** before final cache removal. Removed material included generated output directories, coverage artifacts, Python caches, duplicate technology tables, historical change/audit notes, screenshots, patch files, stale lock material and redundant intermediate reports. Runtime code, measured validation evidence, regression benchmarks, core data, tests and source traceability were retained.

The duplicated technology table was removed after confirming it was a strict subset of the retained master table. Duplicate alias columns in the technology master were also consolidated around one canonical field name.

## 2. Documentation / code / model / data alignment

- Commercial SKU decisions now use `module_candidate_master.csv`; technology-family rows are explicitly research-screening records.
- Candidate and technology records carry a declared decision role and evidence metadata.
- `module_field_policy.csv` documents which fields actually affect physics/uncertainty versus display/provenance.
- Unknown BOM/evidence fields remain unknown rather than being inferred.
- Reports and UI use the same concepts: technical leader, lifetime leader, uncertainty, evidence scope and switching-value sensitivity.

## 3. Physics reinforcement

- Kept hard feasibility/evidence checks and strengthened dataset physical-consistency validation.
- Separated shared solar-resource uncertainty from candidate-specific model uncertainty.
- Made candidate evidence change uncertainty width rather than the predicted mean.
- Replaced linear common degradation arithmetic with compounded year-to-year retention.
- Preserved warranty as a separate sensitivity rather than calling it measured degradation.
- Kept measured IEC P(G,T) validation strictly scoped to the layer actually tested.
- Preserved a failed Morocco field benchmark as falsification evidence rather than tuning it away.

## 4. Economics reinforcement

- Added explicit project NPV and LCOE helpers with unit/input checks.
- Clarified switching value as a procurement sensitivity based on incremental modeled value.
- Prevented evidence-limited candidates from silently receiving a confident economic preference by default.
- Retained technical and commercial leadership as separate concepts.

## 5. UI / presentation

The Streamlit navigation is reduced to five purposeful pages: Overview, Module Recommendation, Technology Library, Downloads, and Method & Evidence. Historical workspace/setup concepts that did not support the recorded demo were removed. The recommendation surface now emphasizes one decision hierarchy, with evidence and uncertainty visible instead of buried in diagnostics.

Client exports are generated dynamically from the selected city/project and the technical-leading technology. The source delivery itself remains generic (`Solaryn.zip`); no city or preselected technology is embedded in the product identity.

## 6. Verification

- Data-quality audit: **PASS** for 4 commercial candidates and 30 technology research records.
- Test suite in the available environment: **79 passed, 1 skipped**. The skipped integration test requires `pvlib` and `NREL-PySAM`; dependency installation could not be completed in the isolated build environment, but both are declared in `requirements.txt`.
- Python compile check: required before packaging.
- Branding scan: required before packaging; Solaryn product copy contains no historical status/release labels.

## 7. Remaining scientific limitations

The package is intentionally conservative about what the present evidence proves. Stronger cross-technology and lifetime claims still require candidate-specific off-condition characterization, frozen multi-technology field benchmarks, BOM/reliability evidence, real procurement inputs and eventually a prospective monitored decision. These are scientific evidence gaps, not UI defects, and the product now exposes them rather than concealing them.
