# SOLARYN V9.2.1 audit findings

This register was written after baseline reproduction and before production-code corrections.

## F-01 - Evidence-last primary headline

- Severity/category: High - Decision logic / Reporting UI.
- What/where: `poc_validation_decision` and the Streamlit success banner lead with a named "POC provisional leader" even when the strict result is no robust winner or insufficient evidence.
- Why it matters/winner impact: It does not change arithmetic but can change the procurement interpretation and overstate a cross-technology result.
- Test/correction: Assert that the primary headline begins with deterministic scientific status and mentions the nominal leader second.

## F-02 - Bare import executes and can crash the UI

- Severity/category: High - Runtime/software.
- What/where: importing `app/streamlit_app.py` executes the entire page; the baseline bare import reached an empty results table and raised `KeyError` in `app/epc_module_mode.py`.
- Why it matters/winner impact: CI/import checks are unreliable and an empty set of successful simulations is not guarded immediately before result-column access.
- Test/correction: use a targeted module import smoke test and add a fail-closed shaped-results guard before lifetime/project scaling.

## F-03 - Windows-locale-dependent tests

- Severity/category: Medium - Testing.
- What/where: two source-inspection tests call `Path.read_text()` without `encoding="utf-8"`.
- Why it matters/winner impact: 2/50 tests fail on a valid Windows installation; no winner impact.
- Test/correction: read source explicitly as UTF-8 and run the full suite on Windows.

## F-04 - No deterministic EPC benchmark runner or frozen API fixture

- Severity/category: High - Testing / Climate-resource.
- What/where: `run_pipeline.py` is research-only; the EPC benchmark exists only behind Streamlit and live NASA/PVGIS calls.
- Why it matters/winner impact: API drift or candidate-set drift can silently change rankings and makes CI non-deterministic.
- Test/correction: add a named benchmark CLI, frozen representative response fixtures, offline integration regression, and separate live smoke tests.

## F-05 - Candidate-set drift changes the nominal leader

- Severity/category: High - Data/schema / Reproducibility.
- What/where: the historical report uses Jinko, First Solar, and LONGi, while the current default master adds REC and selects all candidates.
- Why it matters/winner impact: Yes. REC becomes the nominal leader in the current default set.
- Test/correction: freeze candidate IDs in benchmark metadata and report the candidate-set hash; never imply the old result is the current all-default result.

## F-06 - Resource residual exceeds module separation

- Severity/category: High - Climate/resource.
- What/where: annual NASA->pvlib POA is 5.138% lower than PVGIS, while candidate gaps are about 1-2%.
- Why it matters/winner impact: A common resource bias does not necessarily reorder modules, but time-distribution differences can interact with temperature/IAM and alter gaps.
- Test/correction: produce monthly GHI/DNI/DHI/POA residuals, preserve both sources, document horizon/model differences, and do not calibrate one to the other.

## F-07 - No measured IEC or non-c-Si validation evidence

- Severity/category: High - Module model / Evidence provenance.
- What/where: `external_validation/` is empty and the IEC CSV is a blank template. First Solar uses a CEC-style exploratory fallback.
- Why it matters/winner impact: Yes. Cross-technology rank separation cannot be decision-grade.
- Test/correction: retain `decision_eligible=False`; require a module-specific measured matrix or a validated CdTe-appropriate model and blind holdout metrics. Gate remains PENDING.

## F-08 - CEC STC residuals are not delivered

- Severity/category: High - Numerical / Module model.
- What/where: datasheet consistency is checked, but fitted STC Pmp/Voc/Isc/Vmp/Imp residuals are not exported.
- Why it matters/winner impact: Poor fits could bias energy and ordering.
- Test/correction: independently evaluate the fitted CEC model at 1000 W/m2 and 25 C and write all five absolute/relative residuals.

## F-09 - Thermal evidence is fallback-class, not module-specific

- Severity/category: Medium - Physics / Evidence provenance.
- What/where: absent U0/U1 values select SAPM glass/glass or glass/polymer construction-class parameters.
- Why it matters/winner impact: Yes, differing construction labels can change cell temperature and energy. Exposure-hour differences are not degradation predictions.
- Test/correction: expose thermal evidence level, test module/cell temperature separation, and require product-specific coefficients before claiming product-specific thermal validation.

## F-10 - Input normalization is incomplete for localized headers and ambiguous decimal CSVs

- Severity/category: Medium - Data/schema.
- What/where: headers are trimmed/lowercased, but spaces are not normalized to underscores. `sep=None` can mis-detect semicolon files containing unquoted decimal commas.
- Why it matters/winner impact: Candidate ingestion can fail or misparse values; malformed rows must never be silently accepted.
- Test/correction: normalize header whitespace to underscores, add explicit delimiter/decimal-comma tests, and retain fail-closed numeric validation.

## F-11 - Dependency reproducibility is incomplete

- Severity/category: Medium - Runtime/software.
- What/where: `requirements.txt` is not an exact resolved lock and README's "50 passed" claim does not hold on this Windows baseline.
- Why it matters/winner impact: Dependency changes can alter pvlib numerics and rankings.
- Test/correction: record the environment, add a constraints/lock artifact, and freeze numerical tolerances.

## F-12 - Economics is correctly disabled without quotes but lacks an explicit independent hand-check artifact

- Severity/category: Medium - Economics / Testing.
- What/where: the engine rejects missing baseline price and labels the output as a switching threshold, but the requested independent manual-equation test/report is absent.
- Why it matters/winner impact: Yes when quotes are supplied; sign errors could reverse a procurement preference.
- Test/correction: add a hand-calculated two-candidate test covering energy-value and area-BOS terms. Historical EPC validation remains PENDING without real quotes.

## F-13 - No complete decision-input provenance table

- Severity/category: High - Evidence/provenance.
- What/where: several source maps exist, but no row-level `DATA_PROVENANCE.csv` covers every module parameter and decision constant.
- Why it matters/winner impact: Undocumented values can influence the ranking without a reviewable chain of custody.
- Test/correction: generate provenance rows, distinguish manufacturer/user/assumption/software sources, and flag commercial use.

## F-14 - No bankability, P50/P90, or calibrated degradation basis

- Severity/category: High - Evidence/provenance.
- What/where: no uncertainty propagation, measured field degradation calibration, or financing/AC-loss stack exists.
- Why it matters/winner impact: It limits claim scope rather than identifying a coding error.
- Test/correction: keep bankability NOT CLAIMED; common degradation as scenario, warranty as sensitivity, stress as diagnostic, and switching economics distinct from LCOE.
