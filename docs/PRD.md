# SOLARYN PoC Product Requirements Document
## Codex Build Specification — v4.1
**Date:** 15 September 2026  
**Status:** Build-ready PoC specification  
**Audience:** Founder, scientific reviewers, software engineers, OpenAI Codex  
**Product type:** Physics-driven, climate-aware PV technology decision intelligence  
**Primary objective:** Build a defensible, reproducible PoC that compares real PV candidates for a selected site and explains how climate, candidate physics, lifetime assumptions, and commercial inputs affect the decision.

---

# 0. One sentence Codex must remember

**SOLARYN must recommend the best available candidate whenever the minimum required inputs are valid. It must rank the feasible candidates by the declared objective, return a Top 3, and separately communicate how strong, stable, and evidence-backed that recommendation is. It may return `CANNOT_RECOMMEND` only when the available data are insufficient to calculate a fair comparison at all.**

---

# 1. Product vision

SOLARYN is the decision-intelligence layer between PV resource data, module evidence, engineering models, reliability evidence, and project economics.

The long-term platform connects:

**Site → Climate → Environmental stress → Materials/device architecture → Module/SKU → Real-world performance → Degradation/reliability → System yield → Lifetime economics → Procurement decision → Field learning**

The PoC implements only the first defensible vertical slice:

**Coordinate → Hourly climate → Candidate models → Hourly performance → Annual/lifetime comparison → Evidence gate → Top candidates → Δ€/W when commercial inputs exist → Explainable result**

SOLARYN is not:
- a generic solar yield calculator;
- a replacement for PVsyst/PVcase;
- a procurement marketplace;
- a black-box AI recommender;
- a technology-family scorecard;
- a guarantee of 25–30 year field performance.

---

# 2. PoC problem statement

PV modules are commonly compared using STC/nameplate values and commercial price, but real projects operate across varying irradiance, module temperature, incidence angle, humidity, wind, soiling, snow, spectrum, and other environmental conditions.

The PoC must answer:

> For this site and these actual candidate modules, which candidate has the strongest modeled technical and economic case, what physical effects produce the difference, how strong is the evidence, and under what assumptions could the decision change?

The PoC must normally return a recommendation:

1. **Recommended — strong**: #1 remains clearly preferred under the configured sensitivity/evidence checks.
2. **Recommended — moderate**: #1 is preferred, but one or more uncertainties materially reduce separation.
3. **Recommended — marginal**: #1 has the highest modeled objective, but #2 is close or the ordering is sensitive to reasonable assumptions.
4. **Cannot recommend**: used only when a fair numerical comparison cannot be calculated because critical inputs/evidence are missing or invalid.

The system always returns the modeled Top 3 whenever at least three feasible candidates can be calculated. A marginal recommendation is still a recommendation.

Before external measured validation passes, the recommendation must be labeled **model-based / provisional**, not externally validated or bankable.

---

# 3. Scientific principles — non-negotiable

## SCI-001 — Technology labels are metadata, not algorithms
No code such as:

```python
if climate == "hot":
    choose("HJT")
if climate == "desert":
    choose("CdTe")
```

No technology-family bonuses.

No brand bonuses.

No manually tuned site corrections intended to make winners vary.

## SCI-002 — Candidate order must not affect results
Reordering candidates must leave every candidate metric and decision unchanged within numerical tolerance.

## SCI-003 — Same evidence means same physics
If two candidates have identical physical inputs, their physics outputs must be identical regardless of name, brand, row position, or technology label.

## SCI-004 — Missing evidence cannot become a favorable default
If a candidate lacks a decision-relevant parameter:
- use an explicitly approved fallback model;
- increase uncertainty / lower evidence level;
- or mark the candidate ineligible for that decision claim.

Never silently invent a value.

## SCI-005 — Common losses are not candidate differentiators
If the same soiling, DC loss, degradation assumption, or resource series is applied to all candidates, it may change absolute yield but must not be presented as a reason one candidate wins.

## SCI-006 — The LLM does not calculate science
All numeric outputs are deterministic and versioned.
An LLM may later summarize immutable result JSON, but it cannot alter physics, rankings, economics, evidence status, or decision state.

---

# 4. Users

## Primary PoC user
PV developer / EPC technology or procurement engineer evaluating multiple module options before final procurement.

## Secondary users
- project developer;
- technical advisor;
- asset owner;
- investor/lender technical reviewer;
- module manufacturer;
- SOLARYN scientific reviewer.

---

# 5. PoC user journey

## Step 1 — Create project
Required:
- project name;
- application: utility / rooftop / other;
- project life in years;
- target DC capacity or normalization basis;
- mounting: fixed tilt initially;
- tilt;
- azimuth;
- monofacial/bifacial flag.

Optional:
- energy price;
- discount rate;
- O&M assumptions;
- land/area constraints;
- user-defined common soiling;
- user-defined project losses.

## Step 2 — Select any coordinate on the world map
The PoC must be globally coordinate-driven. It must not contain a predefined city list, city benchmark, city-specific scientific constant, city-specific winner expectation, or city-specific recommendation rule.

User may:
- click any valid land or supported coordinate on the world map; or
- enter latitude and longitude directly.

Valid ranges:
- latitude: -90 to +90;
- longitude: -180 to +180.

The system stores the exact coordinate and retrieves the environmental/resource data for that coordinate.

A place name may optionally be reverse-geocoded for UI convenience, but:
- location display names are display metadata only;
- the physics engine receives coordinates and environmental time series, not a city label;
- a location name must never affect the recommendation.

If the selected coordinate is unsupported by a provider, the system reports that provider limitation honestly and does not substitute another preselected location.

## Step 3 — Build climate snapshot
System retrieves and freezes hourly data from the primary provider.
At minimum:
- timestamp UTC;
- irradiance components required for POA;
- air temperature;
- wind speed.

If available:
- relative humidity;
- precipitation;
- pressure;
- other documented variables.

No climate variable may be fabricated.

## Step 4 — Cross-check resource
Retrieve an independent resource dataset where available.
Compare annual resource metrics under harmonized geometry.
Display discrepancy rather than hiding it.

## Step 5 — Add candidate modules
At least 2 candidates; UI designed for 3–10.

Candidates are imported from a structured CSV/JSON or created from a form.
Real module values require source provenance.

## Step 6 — Run deterministic analysis
For every candidate, use exactly the same:
- climate snapshot;
- geometry;
- timestamps;
- project assumptions;
- common losses.

Candidate differences may enter only through candidate-specific evidence.

## Step 7 — Display result
Result page shows:
- site/climate fingerprint;
- top 3 candidate ranking;
- annual specific energy;
- relative gap;
- lifetime energy under declared degradation model;
- maximum justified price premium Δ€/W if commercial inputs are sufficient;
- evidence status;
- model path used;
- warnings;
- why the ranking occurred;
- sensitivity / conditions that could change the order.

---

# 6. PoC technical scope

## Must implement
1. Map coordinate selection
2. Hourly climate/resource retrieval
3. Immutable climate snapshots
4. PV solar position and plane-of-array irradiance
5. Module/cell temperature
6. Candidate-specific electrical performance
7. AOI/IAM handling
8. Soiling as an explicit input/model
9. Candidate evidence and provenance
10. Annual energy integration
11. Lifetime energy scenario
12. Candidate ranking
13. Evidence/eligibility gates
14. Δ€/W switching threshold
15. Top-3 UI
16. Contribution/explanation view
17. Arbitrary-coordinate regression and smoke-test suite
18. Measured-data validation runner
19. RMSE / MAE / MBE / nRMSE / R² reporting
20. Exportable JSON result and validation report

## Architecture-ready but not required for first vertical slice
- candidate-specific spectral mismatch from EQE/SR;
- detailed bifacial rear irradiance;
- degradation mechanism models;
- probabilistic Monte Carlo;
- P50/P90;
- portfolio analytics;
- SCADA feedback;
- supplier quote parsing;
- AI narrative assistant.

These may have interfaces and schemas, but must not be faked.

---

# 7. Recommended implementation stack

## Backend
- Python 3.12
- FastAPI
- Pydantic v2
- pandas / numpy
- pvlib
- scipy
- httpx
- SQLAlchemy or SQLModel
- SQLite for local PoC, with DB abstraction compatible with PostgreSQL later

## Frontend
- React + TypeScript + Vite
- Leaflet or MapLibre map
- Plotly or ECharts for interactive charts
- no scientific calculations in browser

## Test/tooling
- pytest
- pytest-cov
- Ruff
- mypy or pyright
- pre-commit
- Docker optional but recommended
- GitHub Actions CI

Do not make the PoC depend on an LLM.

---

# 8. Repository structure

```text
solaryn/
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  ├─ schemas/
│  │  ├─ persistence/
│  │  └─ services/
│  └─ tests/
├─ solaryn_core/
│  ├─ units/
│  ├─ climate/
│  │  ├─ providers/
│  │  │  ├─ pvgis.py
│  │  │  └─ nasa_power.py
│  │  ├─ normalization.py
│  │  └─ fingerprint.py
│  ├─ solar/
│  │  ├─ position.py
│  │  └─ poa.py
│  ├─ thermal/
│  ├─ optics/
│  ├─ electrical/
│  │  ├─ interfaces.py
│  │  ├─ iec61853_matrix.py
│  │  └─ datasheet_fallback.py
│  ├─ lifetime/
│  ├─ economics/
│  ├─ decision/
│  ├─ evidence/
│  ├─ validation/
│  └─ results/
├─ frontend/
│  └─ src/
├─ data/
│  ├─ fixtures/
│  ├─ candidate_templates/
│  └─ validation/
├─ docs/
│  ├─ PRD.md
│  ├─ ARCHITECTURE.md
│  ├─ DATA_DICTIONARY.md
│  ├─ EQUATIONS.md
│  ├─ VALIDATION.md
│  └─ model_cards/
└─ scripts/
   ├─ run_four_climates.py
   └─ run_validation.py
```

---

# 9. Canonical units

Internally use SI or explicitly documented engineering units.

Mandatory canonical columns:

```text
timestamp_utc
ghi_w_m2
dni_w_m2
dhi_w_m2
poa_global_w_m2
air_temperature_c
wind_speed_m_s
cell_temperature_c
effective_irradiance_w_m2
dc_power_w
ac_power_w          # only when AC layer is enabled
```

Never mix:
- W and kW;
- Wh and kWh;
- W/m² and kW/m²;
- °C and K;
- percent and fractions.

Every external provider adapter must convert to canonical units before physics code sees the data.

---

# 10. Climate/resource subsystem

## CLIM-001 — Primary provider
Implement JRC PVGIS hourly/series API adapter.

Store with every snapshot:
- provider;
- API/tool version when available;
- requested coordinates;
- returned coordinates/elevation when provided;
- radiation database;
- requested year/range;
- geometry;
- raw response hash;
- retrieval timestamp.

## CLIM-002 — Independent cross-check
Implement NASA POWER hourly adapter.

Cross-check resource under harmonized time basis and geometry as far as technically possible.

Do not average providers into one “truth” automatically.

Display:
- primary annual GHI/POA;
- cross-check annual GHI/POA where comparable;
- relative discrepancy;
- status: normal / warning / unavailable;
- limitations.

## CLIM-003 — Time handling
- store everything in UTC;
- explicitly parse provider time conventions;
- handle leap years;
- no duplicate timestamps;
- no missing-hour interpolation unless the policy explicitly allows it and logs it.

## CLIM-004 — Environmental fingerprint
Calculate descriptive metrics only; these metrics do not choose the technology.

Examples:
- annual GHI;
- annual POA;
- mean / P95 / max air temperature;
- mean / P95 modeled cell temperature;
- hours above configurable cell-temperature thresholds;
- humidity statistics if available;
- wind statistics;
- seasonal irradiance distribution.

Do not label a site “desert” and then use that label in the decision algorithm.

---

# 11. Solar geometry and POA

Use pvlib for:
- solar position;
- extraterrestrial radiation where needed;
- DNI/DHI decomposition only when justified;
- transposition to plane of array;
- AOI.

Do not reimplement established solar geometry without a reason.

For fixed tilt:
- required: tilt_deg and azimuth_deg;
- use a documented transposition model;
- model choice must be versioned.

Output an hourly POA series shared by all candidates.

---

# 12. Optical/effective irradiance layer

Conceptual chain:

```text
POA irradiance
→ AOI/IAM adjustment
→ candidate-specific spectral adjustment if evidence exists
→ soiling adjustment
→ effective irradiance
```

## AOI/IAM
Priority:
1. candidate-specific measured IAM / IEC 61853-2 evidence;
2. candidate-specific validated coefficient model;
3. common documented glass/default model for absolute yield only.

If the same IAM model is applied to all candidates, do not attribute ranking separation to IAM.

## Spectral effect
Decision-grade spectral differentiation is allowed only if candidate-specific spectral response/EQE or another approved evidence-backed model exists.

If not:
- set candidate spectral multiplier to neutral/common;
- label `spectral_differentiation = unavailable`;
- do not use a family-specific “spectral bonus”.

## Soiling
PoC options:
- user-supplied constant loss;
- user-supplied monthly profile;
- future provider plugin.

Soiling is common unless candidate-specific coating/response evidence is provided.

Increasing soiling must never increase yield.

---

# 13. Thermal model

The thermal layer computes module/cell temperature from:
- POA;
- air temperature;
- wind speed;
- mounting configuration.

Use a supported pvlib model such as Faiman or SAPM, chosen through configuration.

Requirements:
- model name/version stored in run result;
- candidate-specific thermal parameters only when sourced;
- otherwise use a common documented mounting thermal model;
- if common thermal parameters are used, climate still changes operating temperature but thermal-parameter differences do not differentiate candidates.

Invariant:
At equal irradiance and other conditions, increasing cell temperature must reduce Pmp for a module with a negative Pmp temperature coefficient.

---

# 14. Commercial technology and module catalog

The PoC must provide a market-facing candidate catalog rather than requiring the user to type technology names manually.

The catalog is **not** an algorithm. Technology family and subtype fields are metadata used for filtering, reporting, evidence organization, and model routing only.

## 14.1 Supported commercial technology families

The initial 2026 catalog must support these commercially available technology families/architectures where real module evidence can be obtained:

| Family | Technology / subtype examples | PoC catalog status |
|---|---|---|
| Crystalline silicon | p-type mono PERC / PERC+ | Supported — commercial/legacy-current |
| Crystalline silicon | n-type TOPCon | Supported — mainstream/current |
| Crystalline silicon | n-type HJT / SHJ / HIT-type heterojunction | Supported — commercial/current |
| Crystalline silicon | Back-contact architectures: IBC, HPBC, ABC and other documented BC variants | Supported — commercial/current |
| Thin film | CdTe | Supported — commercial/current |
| Thin film | CIGS | Supported when a currently market-available module with adequate data is imported; often application/niche specific |

Do **not** create a physics branch such as `if technology_family == "TOPCon"` to assign a winner, gain, degradation rate, thermal bonus, or spectral bonus.

Technology labels may only:
- group candidates;
- describe architecture;
- determine which evidence fields are expected;
- route to a model **only when the model is parameterized by actual candidate evidence**.

## 14.2 Emerging technologies

Create catalog status values:

```text
COMMERCIAL
LIMITED_COMMERCIAL
EMERGING
RESEARCH
RETIRED
UNKNOWN
```

Examples such as perovskite-silicon tandem may exist in the ontology but must not be activated as a normal procurement candidate unless a real commercially offered module/SKU and sufficient decision-relevant evidence are available.

Do not turn laboratory champion cells, announced prototypes, pilot modules, or future roadmaps into a market candidate.

## 14.3 Market catalog files

Create:

```text
data/catalog/
  technology_families.yaml
  commercial_modules.csv
  commercial_modules_sources.yaml
```

`technology_families.yaml` contains taxonomy only.

`commercial_modules.csv` contains actual module/SKU records.

`commercial_modules_sources.yaml` contains the provenance and verification metadata for every seeded SKU.

Minimum module catalog fields:

```text
module_id
manufacturer
model
technology_family
technology_subtype
cell_type
commercial_status
target_application
market_region_if_restricted
datasheet_url
datasheet_revision
source_checked_at
pmp_w
vmp_v
imp_a
voc_v
isc_a
efficiency_pct
gamma_pmp_pct_per_c
bifacial
bifaciality_pct
length_mm
width_mm
module_area_m2
glass_configuration
warranty_years
warranted_degradation_text
iec61853_data_available
iam_data_available
spectral_data_available
independent_field_data_available
decision_evidence_status
```

Unknown fields remain null.

## 14.4 Market availability rules

A seeded module is `COMMERCIAL` only if there is current evidence that it is offered or shipped as a product.

A product announcement alone is not sufficient if commercial delivery has not begun.

Where a product is market-restricted, store that restriction explicitly. Do not present a region-specific product as universally procurable.

Every catalog record must include:
- official manufacturer source;
- source date/revision;
- date checked;
- optional independent evidence;
- status.

The catalog is versioned. A market refresh creates a new catalog release; it does not overwrite historical analysis runs.

## 14.5 User candidate selection

The UI must allow:

1. **Browse market modules**
   - filter by technology family;
   - manufacturer;
   - application;
   - monofacial/bifacial;
   - commercial status;
   - available evidence.

2. **Compare technology families**
   - select representative real modules from multiple families;
   - clearly state that the result compares the selected modules, not all products belonging to those families.

3. **Import a real module**
   - CSV/JSON/form;
   - attach datasheet/source;
   - run integrity and evidence checks.

4. **Create an exploratory candidate**
   - allowed only for research/testing;
   - visibly labeled non-commercial or insufficiently verified;
   - cannot silently enter a procurement-grade recommendation.

## 14.6 Initial market technology evidence

The seed catalog should contain at least one verified, currently commercial example with sufficient datasheet inputs from as many supported families as practical.

Do not block the entire PoC if one technology family lacks adequate public data. Mark that family/candidate as unavailable or evidence-limited.

The system must remain extensible: adding a new commercial technology or module should require adding data/evidence, not adding a new winner rule in Python.

---

# 15. Candidate data model

Each real candidate must have:

```yaml
module_id:
manufacturer:
model:
technology_label:
source_type:
source_reference:
source_date:
stc:
  pmp_w:
  vmp_v:
  imp_a:
  voc_v:
  isc_a:
  efficiency_pct:
  gamma_pmp_pct_per_c:
dimensions:
  area_m2:
module_construction:
  bifacial: false
  glass_glass: null
  encapsulant: null
evidence:
  iec61853_matrix: null
  iam: null
  spectral_response: null
  thermal_parameters: null
  degradation: null
commercial:
  quote_eur_per_w: null
```

Unknown fields remain null.
Never fill nulls by guessing.

Input integrity:
- `Pmp ≈ Vmp × Imp` within configurable tolerance;
- `Vmp < Voc`;
- `Imp < Isc`;
- positive dimensions;
- physically valid coefficients;
- no duplicate module IDs.

---

# 16. Electrical performance model

This is the most important PoC modeling rule.

## Model-path priority

### Path A — Measured P(G,T) / IEC 61853 matrix
Preferred.

Input:
- candidate-specific measured power at multiple irradiance and temperature points.

Method:
- clean/validate matrix;
- interpolate within characterized domain;
- explicitly flag extrapolation;
- integrate hourly site conditions.

This is the preferred cross-technology comparison route because the candidate response is measured rather than inferred from a technology label.

### Path B — Candidate-specific validated model coefficients
Use a known model such as CEC/Sandia/single-diode when appropriate and supported by candidate-specific parameters.

### Path C — Datasheet fallback
For exploratory/provisional comparison only.

A simple datasheet model may approximate:

`Pdc ≈ Pstc × (Geff / 1000) × [1 + gamma_pmp × (Tcell - 25°C)]`

but this path:
- is not decision-grade across technologies by itself;
- must be visibly labeled;
- must not receive fake low-light or spectral bonuses;
- must widen uncertainty / lower evidence status.

## Model routing output
Every candidate result must expose:
- model path;
- input evidence level;
- interpolation fraction;
- extrapolation fraction;
- warnings.

---

# 17. Bifacial handling

Bifacial gain must never be a fixed technology bonus.

If rear-side irradiance geometry is not implemented:
- rear irradiance = 0;
- no bifacial gain;
- mark bifacial differentiation unavailable.

If implemented later:
- calculate rear irradiance from geometry/albedo;
- use actual candidate bifaciality;
- document assumptions.

---

# 18. System losses

PoC supports:
- DC wiring;
- mismatch;
- availability;
- inverter/AC layer if configured;
- transformer/auxiliary losses if configured.

Rules:
- common project losses apply identically to candidates unless there is explicit candidate-specific evidence;
- do not let common losses create a ranking explanation;
- all loss factors are stored in result provenance.

---

# 19. Annual energy

For each hourly timestep:

```text
P_candidate(t) = electrical_model(
    effective_irradiance(t),
    cell_temperature(t),
    candidate_parameters
)
```

Annual energy:

```text
E_year = Σ P(t) × Δt
```

Specific yield:

```text
Y_specific = E_year_kWh / installed_kWp
```

Compare candidates on the same normalization basis.

Output:
- annual kWh/kWp;
- annual MWh for project size;
- relative difference to reference;
- monthly energy;
- temperature-related contribution where separable;
- other modeled candidate-specific contribution terms.

---

# 20. Lifetime layer

The PoC must separate **lifetime scenario** from **validated degradation prediction**.

## Mode A — Common degradation scenario
Default safe PoC mode.

User/project policy supplies the same annual degradation assumption to all candidates.

Purpose:
- show lifetime energy / finance mechanics;
- does not differentiate candidates by degradation.

## Mode B — Candidate-specific degradation
Allowed only when evidence exists and is linked to:
- actual SKU/BOM; or
- an explicitly approved calibrated model with documented validity.

Do not:
- infer measured degradation from warranty;
- assign fixed PERC/TOPCon/HJT/CdTe degradation rates as physical truth;
- claim precise 30-year degradation from IEC qualification alone.

Simple scenario equation when a constant annual degradation rate `d` is used:

```text
E_y = E_1 × (1 - d)^(y - 1)
```

Lifetime energy:

```text
E_lifetime = Σ E_y
```

Every lifetime output must state the degradation model/evidence source.

---

# 21. Economics and Δ€/W

Commercial calculation is enabled only when required inputs are present.

## Core PoC metric — switching threshold

For candidate A relative to reference B:

```text
ΔValue_PV =
PV(net energy/revenue advantage of A vs B)
- PV(candidate-specific incremental O&M/replacement/BOS costs)
```

Maximum justified module price premium:

```text
Δ€/W_max = ΔValue_PV / installed_DC_W
```

If actual quote premium is available:

```text
Net procurement headroom =
Δ€/W_max - actual_price_premium_€/W
```

Interpretation:
- positive: modeled lifetime advantage can support the quoted premium under declared assumptions;
- zero: economic indifference;
- negative: premium exceeds modeled benefit.

Do not call this full LCOE unless the full LCOE boundary is implemented.

Required provenance:
- energy price / value model;
- discount rate;
- project life;
- quote;
- candidate-specific incremental costs;
- currency.

Missing real commercial input must disable that portion cleanly, not invent a price.

---

# 22. Decision engine

The decision engine has two separate responsibilities:

1. **Ranking** — determine the best available candidate for the declared objective.
2. **Recommendation strength** — communicate how robust and evidence-backed that ranking is.

These must never be conflated.

## 22.1 Ranking rule

For all feasible candidates, compute the selected objective using the same site, project assumptions, resource realization, and decision boundary.

Examples of objective:
- year-1 specific energy;
- lifetime energy under declared degradation assumptions;
- project value / NPV when full commercial inputs exist;
- Δ€/W procurement headroom.

Sort feasible candidates deterministically from best to worst.

If at least one feasible candidate exists, SOLARYN must return:

```text
recommended_candidate = rank #1
```

If at least three feasible candidates exist, return Top 3.

A small difference does **not** erase the recommendation. It changes the recommendation strength.

## 22.2 Recommendation-strength outputs

### `RECOMMENDED_STRONG`
Use when:
- #1 has the best modeled objective;
- the lead is material under the configured decision-resolution policy;
- ranking remains stable across declared sensitivity tests;
- decision-relevant evidence quality is adequate.

### `RECOMMENDED_MODERATE`
Use when:
- #1 remains preferred;
- but separation, evidence quality, extrapolation, resource disagreement, or sensitivity reduces robustness.

### `RECOMMENDED_MARGINAL`
Use when:
- #1 has the highest modeled objective;
- but #2 is close, or plausible sensitivity assumptions can reverse the order.

The UI must still say:

> Recommended: Candidate A

and directly below:

> Recommendation strength: Marginal  
> Candidate B is within X% and may become preferable if [decision-changing condition].

### `CANNOT_RECOMMEND`
Use only when a fair comparison cannot be calculated.

Examples:
- no feasible candidate has the minimum electrical inputs;
- candidate evidence cannot support a common comparison boundary;
- resource data required for the run are unavailable/corrupt;
- all candidates fail integrity checks.

Do **not** use `CANNOT_RECOMMEND` merely because:
- the top two candidates are close;
- external validation is still pending;
- evidence is imperfect but sufficient for a provisional comparison;
- multiple candidates perform similarly.

## 22.3 Validation status is separate

Every recommendation also has a separate scientific status:

```text
MODEL_BASED_UNVALIDATED
MODEL_BASED_PARTIALLY_VALIDATED
EXTERNALLY_VALIDATED_FOR_SCOPE
```

and separate evidence quality fields.

Therefore the product may truthfully return:

```text
Recommended candidate: A
Recommendation strength: Marginal
Scientific status: Model-based / partially validated
Gap to #2: +0.7%
Main decision changer: module price premium
```

This is preferable to returning “no winner.”

## 22.4 Recommended vs proven

SOLARYN recommends the best available decision **under the declared model and evidence**.

It does not claim that:
- the recommendation is universally best;
- the technology family always wins that environment;
- future field performance is guaranteed;
- a provisional PoC recommendation is bankable.

This distinction must be explicit in the UI and report.

## 22.5 Economics can change the recommendation

The technical-energy leader does not automatically have to be the commercial recommendation.

Example:

```text
Technical leader: Candidate A
Commercial recommendation: Candidate B
Reason: A's price premium exceeds its modeled lifetime value advantage.
```

The selected optimization objective must always be shown.

---

# 23. Why-this-result decomposition

The result page must answer:

> Why is Candidate A above Candidate B?

Show only real computed contributions.

Possible rows:
- P(G,T) response;
- temperature-related difference;
- low-irradiance response if measured/modelled;
- AOI/IAM difference if candidate-specific;
- spectral difference if candidate-specific;
- bifacial difference if actually modeled;
- degradation difference if evidence-backed;
- commercial price difference.

Common factors should be shown separately as project assumptions, not ranking drivers.

No arbitrary weighted score.

---

# 24. Evidence model

Evidence levels:

```text
E0 = missing / unsupported
E1 = generic/family proxy
E2 = manufacturer datasheet or documented candidate parameter
E3 = candidate-specific independent/laboratory characterization
E4 = candidate-specific field evidence / high-quality independent validation
```

The exact numeric label is less important than transparent provenance.

Every decision-relevant parameter stores:
- value;
- unit;
- source;
- source type;
- date/version;
- candidate applicability;
- validity domain;
- reviewer status;
- evidence level.

---

# 25. Result contract

Example:

```json
{
  "schema_version": "4.0",
  "run_id": "uuid",
  "status": "completed",
  "site": {
    "latitude": 0.0,
    "longitude": 0.0
  },
  "versions": {
    "code_commit": "git-sha",
    "model_release": "poc-4.0.0",
    "decision_policy": "poc-4.0",
    "data_release": "2026.09"
  },
  "resource": {
    "primary_provider": "PVGIS",
    "crosscheck_provider": "NASA_POWER",
    "annual_poa_primary_kwh_m2": 0,
    "annual_poa_crosscheck_kwh_m2": 0,
    "difference_pct": null,
    "status": "pending"
  },
  "candidates": [
    {
      "module_id": "candidate-id",
      "model_path": "iec61853_matrix",
      "decision_eligible": true,
      "annual_specific_energy_kwh_kwp": 0,
      "lifetime_energy_kwh_kwp": 0,
      "evidence_level": "E3",
      "extrapolated_energy_fraction": 0,
      "warnings": []
    }
  ],
  "decision": {
    "status": "RECOMMENDED_MARGINAL",
    "recommended_candidate_module_id": "candidate-id",
    "gap_to_second_pct": 0,
    "recommendation_strength": "MARGINAL",
    "scientific_status": "MODEL_BASED_UNVALIDATED",
    "reasons": [],
    "decision_changers": []
  },
  "economics": {
    "status": "disabled_missing_inputs",
    "switching_threshold_eur_per_w": null
  },
  "validation_gates": {},
  "limitations": [],
  "created_at": "ISO-8601"
}
```

Numbers in UI/report must come from this immutable result object.

---

# 26. Arbitrary-coordinate validation suite

The PoC must not rely on named cities, fixed benchmark locations, or expected location-specific winners.

The test strategy must prove that **any supported coordinate selected from the map** can flow through the same pipeline.

## 26.1 Coordinate-domain tests

Generate deterministic coordinate fixtures programmatically across the provider-supported globe.

The test set must include a spread of:
- northern and southern latitudes;
- low, middle, and high latitudes;
- low and high annual irradiance;
- cool and hot temperature distributions;
- low and high humidity where the provider supplies humidity;
- different seasonal profiles.

Fixtures are identified only by anonymous IDs such as:

```text
SITE_FIXTURE_001
SITE_FIXTURE_002
SITE_FIXTURE_003
SITE_FIXTURE_004
```

Store coordinates in fixture data, not in decision code.

No fixture has an expected commercial technology winner.

## 26.2 Map-coordinate acceptance

For any coordinate accepted by the UI and supported by the configured climate provider:

```text
coordinate
→ resource retrieval
→ normalized hourly climate
→ solar position
→ POA
→ thermal model
→ candidate electrical response
→ annual energy
→ lifetime scenario
→ decision
```

must execute without city-specific code.

## 26.3 Randomized coordinate smoke tests

Provide a script:

```text
scripts/test_random_coordinates.py
```

It must:
1. sample N valid coordinates from a deterministic seed;
2. attempt provider retrieval;
3. skip only documented provider-invalid/ocean/unavailable cases according to policy;
4. run the scientific pipeline for accepted coordinates;
5. verify finite/physical outputs;
6. record failures with coordinate + provider reason;
7. never change candidate parameters based on the coordinate identity.

Live randomized tests are separate from normal CI so external APIs do not make CI flaky.

## 26.4 Offline anonymous regression fixtures

Normal CI must use recorded, anonymous climate fixtures rather than named locations.

Required assertions:
1. climate fingerprints differ when environmental time series differ;
2. all candidates in one run use the same resource realization;
3. candidate-order permutation does not change output;
4. brand/name substitution does not change output;
5. identical candidates remain identical;
6. relative candidate energy can change with operating-condition distributions when candidate physics differs;
7. the same candidate may legitimately remain the leader across many or all fixtures;
8. no code path can look up a city, country, region, climate-class label, or coordinate range to assign a technology advantage.

## 26.5 Coordinate neutrality audit

Add a repository test that searches decision/physics code for forbidden patterns such as:
- location name lookup tables;
- `best_technology_by_location`;
- `technology_by_climate_zone`;
- latitude/longitude thresholds that directly modify a candidate score;
- market-region fields used as physics coefficients.

Coordinates are allowed to influence the result **only by producing environmental/solar geometry inputs** or application constraints explicitly entered by the user.

# 27. Synthetic crossover physics test

Because real modules may legitimately keep the same ranking across all four sites, add a **synthetic test only** that proves the engine can produce a climate-dependent crossover without heuristic weights.

Create two anonymous synthetic candidates:

- Candidate X: stronger hot-temperature response, otherwise controlled;
- Candidate Y: weaker hot-temperature response but controlled reference response.

Use physically plausible test coefficients solely as software fixtures and mark them synthetic.

Run one hot hourly distribution and one cold hourly distribution.

Expected:
- the relative X/Y energy ratio changes in the physically expected direction;
- if fixture coefficients are deliberately constructed to cross, ranking crosses;
- deleting the coefficient difference removes the crossover.

This test validates algorithmic climate sensitivity. It is **not evidence that any commercial technology wins a real climate**.

---

# 28. Anti-bias tests

Required automated tests:

## Permutation invariance
Shuffle candidate input order 100 times.
Results unchanged.

## Brand/name invariance
Replace manufacturer/model labels with anonymous IDs.
Results unchanged.

## Identical-candidate symmetry
Duplicate all numerical/evidence inputs.
Outputs identical.

## Evidence-width behavior
Changing evidence quality must affect eligibility/uncertainty/status, not secretly improve the candidate mean.

## Spectral-neutral test
Without candidate-specific spectral evidence, spectral stage cannot create a ranking gap.

## No-rear test
With rear irradiance zero/unavailable, bifaciality cannot create gain.

## Common-loss invariance
Apply identical loss/degradation to all candidates.
Relative ranking only changes if another legitimate objective such as area/BOS makes it relevant.

## Temperature-neutral test
Give candidates identical temperature/P(G,T) response.
Thermal stage cannot create candidate separation.

## Extrapolation guard
Operating points outside characterized domain must be counted and flagged.

---

# 29. Measured-data validation

Implement a validation runner independent from the production ranking code.

## Input
Candidate-specific measured points:
- irradiance;
- module/cell temperature;
- measured Pmp or IV-derived Pmp;
- measurement ID;
- uncertainty when available.

## Protocol
1. preserve untouched holdout data;
2. calibrate only on training subset if calibration is required;
3. freeze model;
4. predict holdout;
5. compute metrics;
6. save residuals and plots;
7. never tune on holdout after viewing result without creating a new validation version.

## Metrics
- RMSE
- nRMSE
- MAE
- MBE
- R²
- cumulative energy bias when time-series data exist

Equations:

```text
error_i = prediction_i - measurement_i

RMSE = sqrt(mean(error_i²))
MAE  = mean(abs(error_i))
MBE  = mean(error_i)

nRMSE = RMSE / normalization_value
```

The normalization value must be explicitly documented.

Do not invent universal pass thresholds.
Store thresholds in `validation_policy.yaml`.
Until scientifically approved, validation status may be `PENDING` while metrics are reported.

---

# 30. Validation gates

Store independently:

```text
software_runtime            PASS / FAIL
numerical_invariants        PASS / FAIL
resource_crosscheck         PASS / WARNING / FAIL / PENDING
candidate_input_integrity   PASS / FAIL
electrical_measured_model   PASS / FAIL / PENDING
cross_technology_rank       PASS / FAIL / PENDING
lifetime_model              PASS / FAIL / PENDING
economics_math              PASS / FAIL / PENDING
historical_decision_replay  PASS / FAIL / PENDING
bankability                 NOT_CLAIMED
```

A green software test suite does not imply scientific validation.

---

# 31. UI requirements

## Screen 1 — Project
Minimal form for geometry, lifetime and economics.

## Screen 2 — Map
Large map.
Click or search coordinate.
Show selected lat/lon.

## Screen 3 — Climate
Show:
- annual resource;
- temperature profile;
- wind;
- humidity if available;
- monthly resource chart;
- provider/source;
- resource cross-check warning.

## Screen 4 — Candidates
Table:
- manufacturer/model;
- technology label;
- Pmp;
- efficiency;
- gamma Pmp;
- model path available;
- evidence completeness;
- quote €/W if supplied.

## Screen 5 — Results
Hero output:
- decision status;
- modeled #1 candidate;
- #2 and #3;
- annual specific yield;
- relative gap;
- lifetime energy;
- Δ€/W when enabled;
- confidence/evidence wording;
- no fake probability unless probabilistic calibration exists.

## Screen 6 — Why?
Waterfall or contribution table.
Every displayed contribution must map to deterministic stored values.

## Screen 7 — Evidence & validation
Show:
- source data;
- model paths;
- warnings;
- validation gates;
- extrapolation fraction;
- known limitations.

No sidebar-heavy engineering UI.
Product should be understandable by a non-specialist while allowing technical drill-down.

---

# 32. API endpoints

Minimum:

```text
POST /api/v1/projects
GET  /api/v1/projects/{id}

POST /api/v1/sites
POST /api/v1/sites/{id}/climate-snapshot
GET  /api/v1/sites/{id}/climate-snapshot
GET  /api/v1/sites/{id}/resource-crosscheck

GET  /api/v1/technology-families
GET  /api/v1/modules
GET  /api/v1/modules?commercial_status=COMMERCIAL
POST /api/v1/modules
POST /api/v1/modules/import
GET  /api/v1/modules/{id}/evidence

POST /api/v1/analyses
GET  /api/v1/analyses/{id}
GET  /api/v1/analyses/{id}/candidates
GET  /api/v1/analyses/{id}/decision
GET  /api/v1/analyses/{id}/provenance

POST /api/v1/validation/electrical
GET  /api/v1/validation/{id}
```

OpenAPI schema must be generated and committed/tested.

---

# 33. Persistence and reproducibility

For every completed run store:
- exact project inputs;
- exact candidate revision IDs;
- climate snapshot IDs;
- raw provider hashes;
- code git commit;
- model release;
- decision policy;
- evidence release;
- timestamp;
- warnings;
- result JSON.

Completed runs are immutable.
A changed input creates a new run.

The same frozen input/version set must reproduce the same result within declared numerical tolerance.

---

# 34. Failure behavior

The app must fail honestly.

Examples:
- PVGIS unavailable → show provider error; allow cached fixture only if clearly labeled.
- NASA cross-check unavailable → analysis can continue with cross-check status unavailable.
- candidate has invalid electrical values → reject candidate import.
- candidate lacks decision-grade model → allow exploratory fallback only if policy permits.
- no commercial quote → disable Δ€/W quote comparison while keeping technical analysis.
- missing spectral evidence → neutral spectral differentiation, not invented proxy.
- large extrapolation fraction → warning / ineligibility depending policy.

Never hide a failed candidate because it makes the result prettier.

---

# 35. Performance requirements

PoC target:
- cached result page < 2 seconds;
- local annual analysis for 3–10 candidates should be practical on a normal laptop;
- climate API responses cached by coordinate/year/provider/geometry key;
- vectorize hourly calculations;
- no premature distributed-compute architecture.

Correctness and reproducibility are more important than micro-optimization.

---

# 36. Security boundaries for PoC

- secrets in environment variables only;
- no API key in repo;
- strict input validation;
- file upload size/type controls;
- sanitize filenames;
- no arbitrary code execution from uploaded files;
- dependency lockfile;
- audit log for imported candidate evidence and completed runs.

Authentication can be minimal/local in the first PoC but architecture must not mix user input with executable code.

---

# 37. Milestones for Codex

## M0 — Repository and contracts
Deliver:
- repo structure;
- Python package;
- FastAPI health endpoint;
- frontend shell;
- canonical schemas/units;
- AGENTS.md;
- CI;
- tests.

Exit:
- one-command local start;
- lint/type/test green.

## M1 — Site + climate
Deliver:
- map;
- site persistence;
- PVGIS adapter;
- NASA POWER adapter;
- immutable snapshots;
- climate fingerprint;
- anonymous coordinate fixtures.

Exit:
- anonymous coordinate fixtures load and produce valid climate summaries;
- provenance visible.

## M2 — Solar/thermal core
Deliver:
- solar position;
- POA;
- AOI;
- module/cell temperature;
- common soiling;
- physics invariants.

Exit:
- hourly series generated and tested.

## M3 — Market catalog + candidate models
Deliver:
- commercial technology taxonomy;
- versioned commercial module catalog with provenance;
- module browse/filter API and UI;
- module import;
- evidence schema;
- IEC 61853 matrix model;
- datasheet fallback;
- model routing;
- extrapolation accounting.

Exit:
- at least 3 candidates can run through identical site conditions.

## M4 — Decision engine
Deliver:
- ranking;
- top 3;
- recommendation-strength states;
- anti-bias suite;
- why-result decomposition.

Exit:
- permutation/name/identical-candidate tests pass;
- no technology-label branch exists in decision code.

## M5 — Lifetime + economics
Deliver:
- common degradation scenario;
- candidate-specific degradation interface;
- lifetime energy;
- Δ€/W;
- sensitivity inputs.

Exit:
- hand-calculated economics fixtures pass.

## M6 — Validation
Deliver:
- measured-data importer;
- holdout runner;
- RMSE/MAE/MBE/nRMSE/R²;
- residual table/plots;
- validation gate screen.

Exit:
- validation run is reproducible and exports report.

## M7 — Product polish
Deliver:
- clean map-first flow;
- result charts;
- evidence drawer;
- JSON/CSV export;
- demo data setup;
- error states;
- documentation.

Exit:
- a non-technical evaluator can complete site → candidates → result without reading source code.

---

# 38. Codex issue backlog

```text
FOUND-001  Initialize monorepo and tooling
FOUND-002  Add canonical units and schemas
FOUND-003  Create AGENTS.md and architecture docs
SITE-001   Implement map coordinate selection
CLIM-001   Implement PVGIS hourly provider
CLIM-002   Implement NASA POWER hourly provider
CLIM-003   Normalize timestamps/units
CLIM-004   Implement immutable climate snapshots
CLIM-005   Implement climate fingerprint
SOL-001    Solar position
SOL-002    POA transposition
OPT-001    AOI/IAM layer
OPT-002    Soiling layer
THM-001    Thermal model
MOD-001    Candidate schema
MOD-002    CSV/JSON importer
EVD-001    Provenance/evidence store
ELEC-001   IEC 61853 matrix model
ELEC-002   Datasheet fallback
ELEC-003   Model router and extrapolation accounting
SYS-001    Common project losses
LIFE-001   Common degradation scenario
LIFE-002   Candidate degradation evidence interface
ECO-001    Commercial input schema
ECO-002    Δ€/W calculator
DEC-001    Ranking engine
DEC-002    Decision-state machine
DEC-003    Explanation/contribution engine
VAL-001    Arbitrary-coordinate regression/smoke-test suite
VAL-002    Anti-bias tests
VAL-003    Synthetic crossover test
VAL-004    Measured-data validation runner
UI-001     Project flow
UI-002     Climate screen
UI-003     Candidate screen
UI-004     Results/top-3 screen
UI-005     Evidence/validation screen
EXP-001    Immutable JSON export
DOC-001    Model cards and validation docs
```

---

# 39. Definition of done for every Codex task

A task is complete only when:
- requirement ID is cited in the PR/commit summary;
- input/output types and units are explicit;
- happy-path tests pass;
- edge/error tests pass;
- scientific invariants are preserved;
- no undocumented constant is introduced;
- new decision-relevant parameters have provenance hooks;
- OpenAPI/types are updated when needed;
- docs/model card updated when behavior changes;
- lint/type/test commands pass;
- result does not depend on candidate ordering or naming;
- Codex reports exactly what it changed and which tests it ran.

---

# 40. PoC acceptance criteria

The PoC is ready for scientific/customer demonstration when all of the following are true:

1. A user can click any supported map coordinate.
2. The app freezes an hourly climate snapshot with provenance.
3. A second provider can be used as resource cross-check where available.
4. The UI exposes a versioned market catalog covering the supported commercial technology families when verified module data are available.
5. At least 3 real candidate SKUs from the catalog/import path can be compared without hard-coded brand logic.
6. Every candidate exposes the exact physics model path used.
7. IEC 61853/P(G,T) evidence is preferred when available.
8. Missing candidate evidence is visible and cannot silently become favorable.
9. Hourly energy is integrated reproducibly.
10. Anonymous contrasting climate fixtures execute successfully.
11. Relative candidate behavior responds to environmental time series and candidate physics, not location or climate labels.
12. The same candidate is allowed to lead in multiple climates.
13. Synthetic crossover test proves the engine can change relative ordering when underlying physics supports it.
14. Permutation, name, and identical-candidate invariance tests pass.
15. Top 3 results, a recommended #1 candidate, recommendation strength, and scientific validation status are displayed.
16. Lifetime energy is explicitly tied to the declared degradation model.
17. Candidate-specific degradation is disabled without adequate evidence.
18. Δ€/W matches independent hand calculations.
19. Measured validation runner reports RMSE, MAE, MBE, nRMSE and R².
20. Validation status is separate from software test status.
21. No output is described as bankable before a separate bankability validation scope.
22. UI numbers exactly match immutable result JSON.
23. Every completed result records model/data/code versions and can be reproduced.
---

# 41. Absolute “do not do” list

Codex must never:
- hard-code “best technology by climate”;
- add desert/tropical/cold bonuses;
- tune coefficients because results “look wrong”;
- tune constants simply to make four sites show different winners;
- use a brand/model name in a scientific branch;
- fabricate IEC or field data;
- fabricate module prices;
- infer actual degradation from warranty;
- treat a technology-family degradation rate as product truth without evidence;
- create spectral gains without candidate-specific evidence;
- add fixed bifacial gain without rear irradiance;
- hide candidates with weak evidence;
- call a model guardrail “confidence”;
- call deterministic scenarios P50/P90;
- allow the frontend/LLM to recalculate results;
- overwrite a completed scientific run.

---

# 42. What the first demo must show

A five-minute demonstration should be:

1. Click a site on the world map.
2. SOLARYN loads climate and shows the environmental profile.
3. Select/import 3 candidate modules.
4. Run analysis.
5. See top 3 expected annual/lifetime outcomes.
6. Open “Why?” and see physical drivers.
7. See evidence quality and limitations.
8. Click a different coordinate anywhere supported on the world map.
9. Re-run and show how the new environmental time series affect candidate behavior, without promising that a different technology must win.
10. Add commercial quotes and show the Δ€/W indifference threshold.

The key demo statement:

> **SOLARYN does not say “this technology is always best.” It calculates how actual candidate evidence interacts with the actual site, and tells you whether the difference is large and credible enough to matter.**

---

# 43. Future platform hooks — do not build now

The architecture must leave space for:
- BOM/material-level representation;
- EQE/spectral engine;
- advanced bifacial/ray tracing;
- mechanism-aware degradation;
- uncertainty propagation and calibrated P(best);
- P50/P90;
- real supplier tender upload;
- OCR/parser for datasheets;
- PVsyst/PAN imports;
- SCADA ingestion;
- portfolio learning;
- field model recalibration;
- manufacturer R&D/material optimization;
- project collaboration and RBAC.

These are roadmap capabilities, not PoC acceptance requirements.

---

# 44. External scientific basis

The following sources should be linked from `docs/REFERENCES.md` and cited in model cards:

1. **IEC 61215 series** — design qualification; do not treat qualification as a quantitative lifetime prediction.
   https://webstore.iec.ch/

2. **IEC 61853 series** — module energy-rating/performance characterization across irradiance, temperature, spectral and angular behavior.
   https://webstore.iec.ch/

3. **IEA PVPS Task 13 — Optimisation of Photovoltaic Systems for Different Climates (2025)**.
   https://iea-pvps.org/key-topics/t13-optimisation-pv-systems-different-climates-2025/

4. **Sandia PV Performance Modeling Collaborative (PVPMC)** — modeling guidance and validation datasets.
   https://pvpmc.sandia.gov/

5. **JRC PVGIS API** — site-specific hourly radiation/resource data.
   https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en

6. **NASA POWER Hourly API** — hourly meteorological/solar data for independent resource context/cross-check.
   https://power.larc.nasa.gov/docs/services/api/temporal/hourly/

7. **pvlib-python** — established open-source PV modeling library used as physics infrastructure, not as the SOLARYN decision logic.
   https://pvlib-python.readthedocs.io/

8. **Fraunhofer ISE Photovoltaics Report (2026)** — current market/technology context; crystalline silicon and n-type TOPCon dominate the current PV market.
   https://www.ise.fraunhofer.de/en/publications/studies/photovoltaics-report.html

9. **Commercial technology evidence examples used to define catalog support (not to define winners)**:
   - n-type TOPCon: current commercial/module procurement evidence from major suppliers;
   - HJT: mass-produced commercial HJT modules;
   - back-contact: commercially shipped IBC/HPBC/ABC module families;
   - CdTe: commercial utility-scale thin-film modules;
   - CIGS: commercially produced/niche module evidence where currently available.

The repository must store exact product-level source URLs and datasheet revisions in the catalog provenance files. Manufacturer marketing claims may populate descriptive/product fields but may not automatically become scientific model coefficients without evidence review.

---

# 45. Codex execution protocol

Codex must not implement this PRD as one giant task.

At repository start:

1. Read `docs/PRD.md`.
2. Create/read `AGENTS.md`.
3. Create `PLAN.md` mapping milestones M0–M7.
4. Identify scientific assumptions before coding.
5. Implement one issue-sized vertical change at a time.
6. Run tests after every issue.
7. Never “fix” unexpected scientific results by tuning coefficients.
8. Stop and mark a scientific question as `PENDING_REVIEW` when evidence is missing.
9. Keep a changelog of model-behavior changes.
10. Before each milestone exit, run regression + anti-bias tests.

---

# 46. First instruction to give Codex

Use the prompt below after placing this file at `docs/PRD.md`:

```text
Read docs/PRD.md completely and treat it as the product/scientific source of truth.

First inspect the repository. Do not change scientific constants or existing model behavior yet.

Then:
1. create or update AGENTS.md with concise repository rules;
2. create PLAN.md mapping the existing code to PRD milestones M0–M7;
3. identify what can be reused, what must be refactored, and what is missing;
3a. remove any predefined city/location benchmark or location-specific recommendation logic;
4. identify any existing hard-coded technology/climate winner logic, hidden weights, undocumented defaults, missing-evidence fallbacks, or candidate-order dependencies;
5. run the existing test suite and report the baseline;
6. implement M0 only unless M0 already fully exists;
7. add tests before modifying scientific behavior;
8. keep numerical science in deterministic backend/core services;
8a. when at least one feasible candidate can be fairly calculated, always return the best-ranked candidate as the recommendation and separately report recommendation strength;
9. do not force different winners across coordinates or environmental profiles;
9a. the product must accept any climate-provider-supported coordinate from the world map;
10. finish with changed files, commands run, test results, open scientific questions, and the next recommended issue.

Do not fabricate module parameters, prices, IEC measurements, degradation rates, spectral gains, bifacial gains, or validation thresholds.
```

---

# 47. Final product principle

**The PoC succeeds when it gives the user a useful best-available recommendation while remaining reproducible, neutral, evidence-aware, climate-sensitive, and falsifiable. Uncertainty must qualify the recommendation, not automatically suppress it.**
