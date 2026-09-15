# SOLARYN V9 Validation Report

## Validation status

**Build:** V9 Bias Corrected — IEC-61853 evidence hierarchy

**Internal software verification:** PASS

**External physical accuracy validation:** PENDING / NOT CLAIMED

**Bankability-grade validation:** NO

## 1. Baseline reproduced

Before V9, the V8.2 codebase had 19 passing automated tests. The legacy research-ranking path nevertheless showed a structural bias pattern across the 10 built-in sites: HJT won all 10 for four objectives, while CdTe won all 10 for “Economic value”. See `outputs/V8_LEGACY_HEURISTIC_BIAS_AUDIT.csv`.

This establishes the need for architecture correction; it does not establish which technology should have won those sites physically.

## 2. V9 automated suite

Final V9 suite at packaging time: **38/38 PASS**.

The suite covers the original regression checks plus V9-specific tests for:

- IEC-style G-T matrix geometry and STC anchor validation;
- duplicate/bad matrix rejection;
- exact recovery of measured/interpolation anchor points;
- site-distribution-dependent leader switching from physical performance surfaces without weights;
- c-Si CEC fallback evidence policy;
- non-c-Si fail-closed model policy;
- module-specific matrix overriding generic model class;
- spectral proxy sensitivity-only policy;
- EQE-label fail-closed behavior until time-resolved spectral coupling exists;
- common-degradation primary vs warranty sensitivity separation;
- uncertainty guardrail blocking small numerical advantages;
- cross-technology decision blocked when one candidate is model-ineligible;
- spectral sensitivity leader flip reported without becoming the primary winner;
- primary economic switching independent of warranty slope;
- economic threshold blocked for decision-ineligible candidates;
- project-segment compatibility filtering;
- absence of the legacy recommendation engine and resilience scores from the EPC production path;
- NASA POWER pressure kPa/hPa unit guard.

## 3. Synthetic anti-bias behavior test

A deliberately synthetic test was created to verify the **software architecture**, not real PV performance.

Two equal-500-W-STC performance surfaces were generated:

- Synthetic A: stronger low-light behavior, larger temperature sensitivity.
- Synthetic B: weaker low-light behavior, smaller temperature sensitivity.

They were evaluated with the same G-T interpolation code under two synthetic operating distributions.

| Fixture | Leader | Gap |
|---|---|---:|
| Cool/diffuse-like | Synthetic A | 6.18% |
| Hot/arid-like | Synthetic B | 6.14% |

There are **no technology weights** in this test. The winner flips only because the hourly operating distribution samples different regions of the two module performance surfaces.

Raw results: `outputs/V9_SYNTHETIC_BIAS_TEST.csv`.

This proves that the new architecture is capable of climate-dependent differentiation without heuristic score bias. It does **not** validate any real HJT/TOPCon/CdTe/CIGS yield.

## 4. Evidence-based external validation target

The user-supplied IEA PVPS Task 13 report Annex 1 describes an open validation data set containing:

- Pmax, Isc and Voc matrix;
- temperature coefficients;
- spectral response;
- angular loss;
- U0/U1 thermal coefficients;
- one year of real outdoor 5-minute Pmax/Isc/Voc, module temperature, POA/horizontal/diffuse irradiance, ambient temperature and wind.

Sandia PVPMC also exposes IEC 61853-1 matrix data and PAN files for multiple modules. These are the correct next validation targets.

## 5. External validation that could NOT be executed in this environment

The current execution environment does not contain `pvlib` or `NREL-PySAM`, and outbound Python-package installation is unavailable. Therefore this audit does **not** claim to have executed:

- live NASA POWER -> pvlib -> Perez-Driesse -> IAM -> thermal -> CEC single-diode runs;
- CEC parameter fitting through PySAM on the seeded modules;
- live PVGIS cross-check;
- measured Annex-1/PVPMC field-data residual analysis;
- PVsyst/SAM benchmark.

The code compiles and its dependency-independent logic is tested, but the live numerical pipeline must be executed in the intended environment after `pip install -r requirements.txt`.

## 6. Required next physical validation sequence

### Gate A — module characterization reproduction

Use the IEA/Sandia IEC 61853 data and verify that SOLARYN reproduces measured Pmax over G-T coordinates. Report RMSE, MBE and maximum error by irradiance and temperature bin.

### Gate B — one-year measured outdoor reproduction

For the Annex 1 module, use the supplied 5-minute weather/temperature data. Compare predicted and measured Pmax/energy by month and year. Report uncertainty and missing-data policy.

### Gate C — independent climate/resource cross-check

For at least Brussels/temperate, Algiers/hot-dry and one hot-humid site, compare the resource/POA chain against PVGIS or another authoritative source using identical geometry.

### Gate D — product/model-form comparison

For c-Si, compare datasheet CEC fallback against IEC-matrix-derived or PAN/PVsyst representation. For CdTe/CIGS, do not enable a robust cross-technology decision until a suitable validated module-specific model/evidence set is present.

### Gate E — economics

Enter real, date-stamped supplier quotes and project-specific area/BOS assumptions. Only then evaluate switching prices. Full LCOE remains a later stage.

## 7. Acceptance criteria proposed for the next release

These are engineering gates for review, not claimed standards:

- no silent fallback from missing module data to a technology score;
- 100% of decision-driving parameters traceable to source/assumption/model;
- no cross-technology winner if model evidence is incomplete;
- no primary winner if gap is below declared uncertainty/separation policy;
- spectral/warranty sensitivities cannot silently change primary energy;
- all matrix interpolation/extrapolation fractions reported;
- live external validation residuals published alongside the POC.

## Final assessment

V9 is a materially better **bias-controlled validation POC architecture** than V8.2. Its software decision logic now behaves as intended, including a physically driven synthetic leader flip and fail-closed evidence gates. It is **not yet a validated predictive PV product** until the live pvlib/PySAM pipeline and measured external datasets are executed and benchmarked.
