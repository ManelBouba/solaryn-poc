# SOLARYN V9 Bias-Correction Engineering Note

## Purpose

V9 corrects a structural failure mode in earlier SOLARYN prototypes: a technology could win because a small set of technology-family attributes and objective weights were structurally favorable, even when the site changed. The correction is architectural, not a retuning of weights.

The commercial decision path now follows this rule:

> **No technology score is allowed to create a procurement winner. A candidate can win only through project-common climate/geometry, module-specific or explicitly qualified electrical evidence, transparent lifetime/economic assumptions, and a visible uncertainty/evidence gate.**

The 30-technology/material research database remains intact, but its weighted screening is isolated from the production decision path.

## Scientific basis extracted from IEA PVPS Task 13 / IEC 61853

The IEA PVPS Task 13 report *Climatic Rating of Photovoltaic Modules: Different Technologies for Various Operating Conditions* makes several points that directly change the SOLARYN design:

1. Energy rating depends on low-irradiance behavior, temperature behavior, spectral response and angular response, all of which interact with climate and location.
2. IEC 61853-1 characterizes module power over an irradiance-temperature (G-T) matrix rather than only at STC.
3. Low-irradiance behavior can vary strongly between module designs and is not safely represented by a technology-family score.
4. Spectral response can vary inside the same technology because of cell quality, coatings, encapsulation and front glass; technology-wide spectral constants should not be treated as exact module behavior.
5. One full year of hourly conditions is used for repeatable climate-specific energy rating; short hand-picked periods can favor a technology.
6. Model-form accuracy is not identical across device technologies. The report documents a study in which an I-V interpolation approach worked well for crystalline silicon but failed for CdTe because the model assumptions did not describe all devices equally well.
7. Energy-rating uncertainty is material. The report discusses final CSER uncertainty around the ~2% scale in one analysis and emphasizes uncertainty in irradiance, thermal parameters and module measurements.
8. Annex 1 provides exactly the type of validation evidence SOLARYN should target: module G-T electrical characterization, spectral response, angular loss, U0/U1 thermal coefficients, plus one year of 5-minute outdoor electrical and meteorological data.

Primary references:
- IEA PVPS Task 13 report (2020): https://iea-pvps.org/key-topics/climatic-rating-of-photovoltaic-modules/
- Sandia PVPMC module datasets: https://pvpmc.sandia.gov/datasets/
- IEA PVPS Task 13 module validation dataset: https://pvpmc.sandia.gov/datasets/iea-pvps-task-13-module-validation-dataset/

## V8.2 failure reproduced before correction

The legacy research-ranking engine was run over the ten built-in sites using the commercial candidate universe. It produced:

| Objective | Winner across 10/10 sites |
|---|---|
| Lifetime energy | HJT |
| Balanced project fit | HJT |
| Lowest climate risk | HJT |
| Area-constrained project | HJT |
| Economic value | CdTe Thin Film |

This does **not** prove that those technologies cannot genuinely win many sites. It proves that the legacy weighted architecture is not a trustworthy way to establish that result, because the objective itself strongly determines the winner.

Raw audit: `outputs/V8_LEGACY_HEURISTIC_BIAS_AUDIT.csv`.

## V9 architecture

```text
PROJECT / PRODUCT ELIGIBILITY
  location, segment, geometry, real offers
                  |
                  v
FULL-YEAR HOURLY RESOURCE
  NASA POWER GHI/DNI/DHI/Tair/wind/RH/pressure
                  |
                  v
POA / OPTICS
  solar position -> Perez-Driesse POA -> common IAM fallback
                  |
                  v
THERMAL EVIDENCE HIERARCHY
  module-specific Faiman U0/U1 if available
  else explicit SAPM construction-class fallback
                  |
                  v
ELECTRICAL EVIDENCE HIERARCHY
  1) module-specific IEC-61853-style G-T matrix [preferred]
  2) c-Si datasheet-fitted CEC single diode [qualified fallback]
  3) non-c-Si generic CEC [exploratory only; cannot decide winner]
                  |
                  v
YEAR-1 SPECIFIC DC ENERGY
  broadband primary
  technology-class spectral proxy = sensitivity only
                  |
                  v
LIFETIME
  common degradation sensitivity = primary comparison
  manufacturer warranty = separate sensitivity only
                  |
                  v
EVIDENCE + UNCERTAINTY GATE
  all selected candidates model-eligible?
  same primary/common-lifetime leader?
  gap >= max(user threshold, uncertainty guardrail)?
                  |
         yes -----+----- no
          |               |
          v               v
 ROBUST SCREENING      NO ROBUST WINNER /
 LEADER               INCOMPLETE EVIDENCE
                  |
                  v
ECONOMIC SWITCHING
  only if underlying energy model is decision-eligible
  real quote + common degradation + area-sensitive BOS
  warranty threshold shown separately
```

## Line-by-line class of corrections

### 1. `src/iec61853_engine.py` — new

- Reads a module-specific G-T Pmax matrix.
- Rejects missing/non-numeric/negative values.
- Rejects duplicate G/T coordinates.
- Requires a minimum reduced matrix size and useful irradiance/temperature span.
- Checks an available 1000 W/m², 25 °C anchor against module nameplate Pmax; >3% mismatch is rejected pending evidence review.
- Uses 2-D linear interpolation inside the measured hull.
- Explicitly counts hours outside the measured irradiance/temperature envelope.
- Uses nearest-neighbor only as a declared fallback for holes/non-convex edges and reports the fraction.
- Never inserts a technology-specific bonus.
- Explicitly states that this PoC interpolation is **not a claim of exact IEC 61853-3 conformity**.

### 2. `src/evidence_policy.py` — new

Electrical model selection is evidence-driven:

- Module-specific G-T file exists -> decision-eligible measured-matrix path.
- c-Si family without matrix -> CEC single-diode datasheet fit is allowed as a fallback, with an uncertainty warning.
- CdTe/CIGS/other non-c-Si without module-specific/validated model evidence -> exploratory only and cannot create a robust cross-technology winner.

Spectral evidence deliberately fails closed:

- The current executable spectral calculation is a technology-class proxy.
- Even a database label saying “module-specific EQE” does not activate spectral decision use, because EQE must be coupled to time-resolved spectral irradiance or another validated module-specific correction engine.
- Therefore V9 spectral output is sensitivity-only.

Thermal model selection:

- Prefer module-specific Faiman U0/U1.
- Otherwise expose a construction-class SAPM proxy rather than pretending it is module-specific.

### 3. `src/module_iv_engine.py` — rewritten decision physics

- Keeps strict datasheet consistency validation.
- Removes all legacy resilience/quality scores from the EPC path.
- Separates **module temperature** from **cell temperature**:
  - IEC-style matrix lookup uses module/device temperature.
  - CEC single-diode calculation uses cell temperature.
- Uses AOI-corrected broadband POA for the thermal driver; spectral proxy does not secretly change temperature.
- Primary annual energy is broadband unless a future implemented module-specific spectral engine is validated.
- Technology-class spectral output is retained in a separate sensitivity column.
- Electrical model, evidence level, model warning, thermal evidence and matrix extrapolation diagnostics are written into results.

### 4. `src/pvlib_pipeline.py` — climate/POA corrections

- Uses one full hourly reference year.
- Uses NASA POWER hourly GHI/DNI/DHI when available; DNI/DHI fallback source is explicitly flagged.
- Changes tilted-surface diffuse transposition from isotropic to Perez-Driesse to reduce systematic differences caused by very different diffuse fractions across climates.
- Applies one common physical front-glass IAM fallback so optical assumptions cannot manufacture technology differences.
- Corrects the NASA POWER surface-pressure unit guard. POWER PS is handled as kPa; guarded hPa/Pa branches prevent the old magnitude rule from misreading ~1000 hPa as 1000 kPa.

### 5. `src/lifetime_engine.py` — warranty bias removed

Primary lifetime comparison uses the **same declared degradation sensitivity** for all modules. This is not a claim that all products degrade identically; it is a bias-control measure until module/BOM-specific field degradation is calibrated.

Manufacturer warranty slopes are still shown, but only as a separate sensitivity. A generous warranty can no longer manufacture the primary lifetime-energy winner.

### 6. `src/economics_engine.py` — price-switching bias controlled

- Primary energy value uses common degradation.
- Warranty-derived price threshold is a separate sensitivity.
- Real baseline $/W quote is mandatory; seed prices remain blank.
- Area-sensitive BOS is explicit and is not called full LCOE.
- A candidate whose energy model is decision-ineligible receives **no economic switching threshold**. Economics cannot revive a winner rejected by physics evidence.

### 7. `src/epc_decision.py` — fail-closed decision gate

A robust screening leader is returned only when:

1. every selected candidate has decision-eligible electrical model evidence;
2. broadband/primary annual and common-degradation lifetime leaders agree;
3. the leader gap exceeds both the user separation policy and the declared energy-rating uncertainty guardrail.

Otherwise SOLARYN returns either:

- `incomplete_cross_technology_model_evidence`,
- `no_robust_winner_under_declared_scenarios`, or
- `no_robust_winner_under_uncertainty_guardrail`.

### 8. Application/UI

- Commercial comparison explicitly identifies V9 bias-control rules.
- Research-screening mode is visibly labeled heuristic/research-only.
- Project segment is a first-class filter.
- Module model evidence is displayed beside energy results.
- Common-degradation and warranty lifetime outcomes are shown separately.
- Economic thresholds show model eligibility.
- Downloaded HTML report reproduces the same scientific boundaries instead of reverting to V8 language.

## What is deliberately NOT “corrected” by inventing numbers

V9 does not invent:

- technology-specific low-light scores;
- humidity/heat/soiling penalties;
- climate-specific degradation %/year;
- module-specific spectral gains without an executable evidence chain;
- live module prices;
- full BOS/LCOE;
- probabilistic confidence scores;
- P50/P90 distributions;
- bifacial rear-side gain;
- bankability conclusions.

## Why this is a stronger correction than retuning weights

A different winner is no longer the goal. A **defensible mechanism** is the goal. If one module genuinely leads Brussels, Algiers and Riyadh after a common, evidence-controlled calculation and the gap is larger than uncertainty, SOLARYN should be allowed to return the same winner. Conversely, if the difference is too small or one candidate has weak model evidence, SOLARYN should refuse to rank them conclusively.
