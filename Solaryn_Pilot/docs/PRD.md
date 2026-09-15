SOLARYN
Product Requirements Document v2.0
Codex Build Baseline
Physics-driven • Climate-aware • Evidence-gated • Explainable
11 September 2026Build-ready / scientific-validation constrainedCONFIDENTIAL — INTERNAL PRODUCT & ENGINEERING DOCUMENT

Status: Build-ready / scientific-validation constrained  
Date: 11 September 2026  
Primary audience: SOLARYN founders, engineering team, scientific reviewers, OpenAI Codex  
Primary build objective: Create a production-shaped MVP that preserves the full SOLARYN vision while implementing only the first defensible decision wedge.  
Product principle: Scientific defensibility, evidence, reproducibility and honest uncertainty take precedence over always producing a winner.

0. How Codex must use this PRD
Codex must not attempt to build the whole platform in one task. It should read this document and AGENTS.md, produce an implementation plan, then execute small issue-sized changes with tests. The first implementation goal is a thin vertical slice: project → site → climate snapshot → candidate set → deterministic physics run → evidence gate → decision status → result page → export.
Every implementation task must include: requirement IDs, affected paths, inputs/outputs/units, acceptance criteria, tests, migration/API changes, scientific implications, and explicit non-goals.
Non-negotiable rules for generated code:
The UI and LLM layers must never calculate scientific or financial outputs.
Numerical outputs must come from deterministic, versioned services.
Never invent prices, degradation rates, IEC measurements, supplier data or missing module parameters.
Never force different technologies to win in different climates.
Never turn a technology-class heuristic into decision-grade evidence without an explicit approved evidence rule.
A passing unit test is not the same thing as a scientific validation gate passing.
A recommendation may legitimately be “effectively tied” or “insufficient evidence”.
Completed runs, source snapshots, published model releases and published parameter releases are immutable.

1. Executive summary
SOLARYN is a physics-driven, climate-aware photovoltaic technology intelligence platform. It addresses a decision that sits upstream of detailed PV design: which photovoltaic technology or module is the best fit for a specific site and project, what is the evidence for that conclusion, and what is the economic value of choosing it?
The long-term SOLARYN intelligence chain is:
materials → devices → PV technologies → commercial modules → systems → climate/site → lifetime performance → degradation/risk → economics → project decisions → portfolios → field feedback → future PV innovation
The first product wedge is intentionally narrower: compare candidate PV technologies/modules for a real project under common site and project assumptions, quantify their modeled performance and lifetime implications, gate the result by evidence quality, and translate defensible differences into a module switching threshold (Δ€/W) where commercial inputs are sufficient.
SOLARYN is not a generic solar yield calculator. It is not a CAD/layout tool. It is not a procurement marketplace. It is not a black-box AI recommender. Its product value is the decision layer connecting technology physics, climate, exact module evidence, uncertainty and commercial consequences.
1.1 Product promise
Given a location, project configuration, candidate technologies/modules and available commercial evidence, SOLARYN will return one of four scientifically honest outcomes:
1. Robust advantage — one candidate has a defensible modeled advantage under declared evidence and guardrails.
2. Provisional leader — a numerical leader exists, but separation/evidence/resource confidence is not strong enough for a robust claim.
3. Effectively tied — modeled differences are within the declared decision guardrail or sensitivities reverse the order.
4. Insufficient evidence — the requested comparison cannot be supported with the available technology/model evidence.
The platform must explain why it returned that status and show what evidence would be required to strengthen the decision.

2. The problem SOLARYN targets
PV module nameplate power and standard qualification do not answer the whole site-specific lifetime decision. IEC 61215 qualification is not a quantitative lifetime forecast; useful life depends on design, environment and operating conditions. IEA PVPS Task 13 likewise emphasizes climate-specific stressors, degradation and tailored design choices across harsh climates.
The industry workflow is fragmented:
materials/device tools understand optical and electrical behavior;
weather/resource systems describe the environment;
engineering tools design layouts and systems;
procurement platforms compare products, pricing and supply-chain constraints;
financial models calculate project economics;
reliability evidence sits in separate test reports, field datasets and expert workflows.
SOLARYN’s thesis is that a meaningful technology decision requires these layers to be connected while preserving the evidence quality and validity limits of each layer.

3. Differentiation and strategic positioning
3.1 Differentiation that must exist in the product, not only in the pitch
D-01 — Materials-to-value intelligence chain
SOLARYN’s data model must be able to relate material/device attributes to technology behavior, module evidence, site climate, project outcomes and lifetime economics. The MVP does not simulate every material property, but the schema and model registry must support this chain without a future rewrite.
D-02 — Climate-conditioned technology choice
Recommendations are site-specific. Climate is not a decorative dashboard. The decision engine must consume the actual resource/meteorological snapshot used for the run and expose its provenance and discrepancies.
D-03 — Exact-module evidence hierarchy
SOLARYN distinguishes technology family knowledge from exact commercial SKU evidence. Exact IEC 61853 matrices, measured spectral response, IAM curves, thermal coefficients and validated electrical models outrank generic technology-class proxies.
D-04 — Fail-closed scientific decisioning
If evidence is insufficient, a candidate or comparison becomes exploratory/ineligible rather than being silently assigned a convincing score. This is a core product feature.
D-05 — Decision status separate from numerical leader
The product always separates “highest modeled value” from “robust validated winner”. The headline scientific status appears before the nominal leader.
D-06 — Physics-to-procurement switching threshold
SOLARYN translates defensible lifetime advantage into a commercial decision boundary: the maximum additional module premium, Δ€/W, that remains economically justified under the stated assumptions.
D-07 — Reproducibility and provenance as first-class UX
Every number used in a decision carries source, unit, evidence level, version and whether it is decision-relevant. A result can be regenerated from immutable inputs and versions.
D-08 — Validation by measured data plus real decisions
SOLARYN has two independent gates: scientific validation against measured PV behavior and decision validation through historical EPC/project replays. Neither gate substitutes for the other.
D-09 — Field-learning roadmap
Later releases compare predicted versus measured behavior from operating assets, enabling the platform to learn technology × climate × project relationships rather than remaining a static calculator.
D-10 — R&D feedback loop
The long-term architecture supports propagation from absorber/device changes to project value, enabling manufacturer and R&D intelligence rather than stopping at commercial module procurement.
3.2 Competitive boundary
SOLARYN must be positioned precisely, because adjacent products are strong.
Adjacent category
What it does well
SOLARYN boundary/difference
SunSolve / PV Lighthouse
Deep optical/electrical modeling of cells/modules; materials, spectra, ray tracing, EQE, IV behavior
SOLARYN consumes/links deep physics evidence into site-specific technology choice, lifetime project consequences and decision evidence. It is not trying to replace a device solver.
PVsyst / pvlib
PV system performance modeling and energy simulation
SOLARYN uses validated models/adapters as calculation components but owns the cross-technology evidence gate, decision status, switching threshold and provenance chain.
PVcase
Site selection, layout, design, yield and engineering workflows
SOLARYN answers which technology/module deserves to enter detailed design and why, before or alongside layout optimization.
RatedPower
Utility-scale siting, PV/BESS design, yield, CAPEX/LCOE and engineering iteration
SOLARYN is not a plant CAD/engineering replacement; it focuses on evidence-gated technology/module intelligence and upstream technology choice.
Anza
Solar/BESS equipment data, supplier/pricing intelligence, lifetime-value product ranking and procurement services
Anza is the closest procurement-side overlap. SOLARYN must differentiate through deeper climate/physics/evidence traceability, multi-technology scientific validation, global/site modeling and the materials-to-field learning chain rather than claiming lifetime-value ranking alone.
Strategic warning: “lifetime value” or “module ranking” alone is not a defensible differentiation claim because adjacent platforms already offer these. SOLARYN’s defensibility must come from the physics + climate + exact evidence + validation + explainable switching threshold + field-learning chain.

4. Users and jobs to be done
4.1 Primary initial persona — EPC/developer decision engineer
Job: Before detailed engineering or procurement lock-in, compare credible module/technology options under one project’s real conditions and understand whether one option has enough technical/economic advantage to justify selection or a price premium.
Needs:
fast project/site setup;
exact candidate modules and supplier quotes when available;
clear separation between measured, manufacturer, modeled and proxy evidence;
comparable annual and lifetime outputs;
transparent assumptions and limitations;
defensible report for internal/project review.
4.2 Secondary future personas
Developer/IPP: lifetime technology value and portfolio comparison.
Asset owner/investor: technical assumptions, downside and bankability evidence.
Manufacturer: where a technology creates site/segment advantage and what premium that advantage supports.
R&D/materials team: how device/material changes propagate into field/project value.
Research/independent engineer: model comparison, validation and evidence gaps.

5. Product vision and release stages
Stage 1 — Technology intelligence — build now
Which PV technology/module is technically favored for this project, with what evidence and confidence boundary?
Stage 2 — Module & procurement intelligence — partial in MVP; expand next
Which exact module/supplier offer creates the strongest value, and what is the Δ€/W switching threshold?
Stage 3 — Project & bankability intelligence
Lifetime yield, uncertainty distributions, P50/P90 where statistically valid, degradation evidence, CAPEX/OPEX, LCOE and bankability indicators.
Stage 4 — Lifecycle intelligence
Predicted vs measured field behavior, degradation monitoring and model updates.
Stage 5 — Portfolio intelligence
Cross-project, cross-climate, supplier and technology comparisons.
Stage 6 — Manufacturer intelligence
Climate advantage maps, price-premium support, product positioning and degradation-risk segments.
Stage 7 — Materials & R&D intelligence
Model changes to absorber, thickness, bandgap, interfaces, transport, recombination, device architecture and encapsulation, then propagate them toward module/site/project economics.

6. MVP scope and non-goals
6.1 MVP must support
workspace/project creation;
project decision context: utility, C&I, rooftop/research-ready extension;
site selection by map click, location search and coordinates;
fixed-tilt and tracker-ready geometry abstraction, with fixed tilt implemented first;
climate/resource retrieval from NASA POWER and PVGIS adapters;
immutable climate snapshots with source request metadata;
climate/resource comparison and discrepancy diagnostics;
commercial module candidate library with versioned evidence;
candidate upload by CSV using strict schema validation;
at least two candidates per comparison;
c-Si electrical modeling through validated model adapters;
exact IEC 61853 matrix model when available;
exploratory/non-decision-grade models for candidates lacking adequate evidence;
temperature, AOI/IAM, soiling, spectral sensitivity, annual energy and lifetime scenario calculations;
decision eligibility and evidence gates;
robust/provisional/tie/insufficient-evidence decision states;
module switching threshold when economic inputs are sufficient;
deterministic report and versioned JSON export;
grounded narrative explanation over immutable results;
scientific validation dashboard/gate table for internal/admin use.
6.2 Explicit MVP non-goals
full plant CAD, stringing, cable, substation or interconnection design;
bankable P50/P90 unless a statistically defensible uncertainty model has been implemented and validated;
claim that environmental stress metrics directly predict module-specific degradation;
automatic product recommendation based on incomplete vendor/SKU evidence;
unreviewed web scraping into production parameter tables;
procurement-market data business comparable to Anza in the first release;
replacing PVsyst, RatedPower, PVcase or an independent engineer;
using an LLM to choose the technology;
forcing a winner for demo quality.

7. End-to-end user flow
1. Create project — name, segment, development stage, primary objective, capacity, operating life.
2. Select site — click map/search/coordinates; persist latitude, longitude, timezone, elevation where available.
3. Define system geometry — fixed tilt/tracker, tilt, azimuth, monofacial/bifacial flag, surface context.
4. Retrieve resource data — request NASA POWER and PVGIS, store immutable raw/normalized snapshots.
5. Review climate/resource fingerprint — GHI/DNI/DHI where available, POA, temperature, RH, wind and diagnostic stress indicators.
6. Choose/import candidates — exact module SKUs with technology labels and evidence status.
7. Review candidate evidence — datasheet completeness, electrical model eligibility, IEC matrix, spectral/IAM/thermal evidence, quote availability.
8. Run analysis — deterministic pipeline only.
9. View scientific decision status — robust/provisional/tied/insufficient evidence.
10. Compare candidates — annual specific energy, lifetime scenario energy, temperature behavior, stress diagnostics, evidence quality and sensitivity.
11. Review economics — switching threshold and quote comparison only if required inputs exist.
12. Inspect evidence & limitations — every decision-relevant parameter and model version.
13. Export — deterministic report + JSON result.
14. Ask explanation assistant — generated text may explain immutable results but cannot recalculate or override them.

8. Project and site input requirements
FR-PROJ-01 — Project core
Fields: project_name, segment, development_stage, objective, capacity_kwp/mwp, target_lifetime_years, currency, optional budget context.
Acceptance: canonical capacity units; lifetime > 0; project belongs to workspace; revision history preserved.
FR-SITE-01 — Interactive site
Fields: latitude, longitude, timezone, elevation_m, country, display_name, optional polygon reference.
Acceptance: map click and coordinate edit remain synchronized; invalid coordinate ranges rejected; site used by analysis is immutable within a completed run.
FR-SYS-01 — Geometry
Fields: geometry_type, tilt_deg, azimuth_deg, tracker settings if enabled, bifacial flag, surface_context, albedo assumption and source.
Acceptance: all geometry assumptions visible in result/export; candidate comparison uses common geometry unless an explicit candidate-specific scenario is created.

9. Climate and solar-resource layer
9.1 Provider adapters
Create provider interfaces so external services can be added without changing domain logic.
Initial adapters:
NASAPowerHourlyProvider
PVGISProvider
Each request stores: provider, endpoint/version, request parameters, coordinates, year/period, time standard, retrieval timestamp, raw snapshot checksum, parsed row count, units, missingness and warnings.
9.2 Time handling
Time standards must be explicit. NASA POWER can return UTC or Local Solar Time; the adapter must never infer/convert silently. Internal time-series indices must be timezone-aware or explicitly represent solar time. Leap years, missing hours and duplicated timestamps must be tested.
9.3 Resource calculations
Pipeline must support:
solar position;
GHI/DNI/DHI handling;
transposition to plane of array;
horizon assumption metadata;
albedo;
AOI;
annual/monthly aggregation.
9.4 Resource cross-check
NASA-derived SOLARYN POA and PVGIS POA must remain separate. Do not force or average them simply to make results agree.
Create ResourceBenchmark with monthly:
month, nasa_ghi, nasa_dni, nasa_dhi, solaryn_poa, pvgis_poa, absolute_difference, percentage_difference.
Decision engine receives a resource_confidence_status: adequate, warning, or insufficient_for_robust_claim based on a versioned rule. The current ~5% Riyadh discrepancy is a known validation issue and must remain visible until resolved.
9.5 Climate fingerprint
Show descriptive diagnostics, not false degradation predictions:
annual GHI/POA;
ambient temperature distribution;
relative humidity where available;
wind distribution;
hot-hour count;
humidity exposure proxy;
thermal cycling proxy;
soiling assumption/data;
spectral-variation indicator where defensible.
Stress indicators must be labeled diagnostics unless calibrated to a specific degradation model.

10. Technology and module knowledge model
10.1 Technology entity
Represents family-level knowledge: PERC, TOPCon, HJT/SHJ, IBC, CdTe, CIGS, perovskite, tandem, etc.
Fields include: technology_id, label, absorber family, device architecture, commercial maturity, applicable electrical models, known validity boundaries, default evidence notes and future material/device links.
10.2 Commercial module/SKU entity
Required fields:
module_id — stable unique ID
technology_id
manufacturer
model
technology_label
cec_celltype/model family where applicable
pmax_w
vmp_v
imp_a
voc_v
isc_a
alpha_isc_pct_c
beta_voc_pct_c
gamma_pmax_pct_c
cells_in_series
cells_in_series_basis
module_area_m2
module_efficiency_pct
noct_c/NMOT when available
thermal_construction
first_year_retention_pct
annual_warranty_degradation_pct_year
warranty_years
quote_currency_w / quote_usd_w / quote_eur_w as normalized commercial quote field
source_url
evidence_status
source_note
iec61853_matrix_file/reference
spectral_evidence_level
thermal_u0_w_m2k
thermal_u1_w_s_m3k
bom_evidence_status
project_segment applicability
spectral_response_file/reference
spectral_irradiance_source
iam_curve_file/reference
thermal_evidence_source
electrical_model_validation_reference
bom_source_reference
10.3 Parameter provenance
Every decision-relevant input must resolve to a provenance record:
parameter, value, unit, source, source_type, evidence_level, date/version, reviewer, decision_relevant_yes_no, validity_scope.
No undocumented constant may silently influence a commercial decision.
10.4 Evidence levels
Suggested ordered taxonomy:
1. exact_measured_module — exact SKU measured dataset, e.g. IEC 61853 / IV / field validation.
2. exact_manufacturer_verified — exact SKU datasheet/warranty/technical evidence.
3. validated_model_family — model scientifically valid for this device family and within domain.
4. technology_class_proxy — representative proxy for sensitivity/diagnostics.
5. literature_heuristic — general heuristic; not decision-grade by default.
6. user_assumption — explicit scenario assumption.
7. missing — unavailable.
Decision policy must define which evidence levels are eligible for each calculation and claim.

11. Scientific model architecture
Implement models behind explicit strategy interfaces. A candidate can use different strategies depending on available evidence.
11.1 Model selection precedence
1. Exact validated IEC 61853 / measured model for exact module.
2. Exact validated electrical model parameters for exact module.
3. Validated family model within applicability domain.
4. Datasheet fallback where scientifically allowed (e.g., c-Si CEC/single-diode path).
5. Exploratory proxy — results displayed but candidate is not decision-eligible for unsupported cross-technology claims.
Never apply a convenient c-Si model to a thin-film/device family merely to make all candidates rankable.
11.2 Electrical sanity checks
On import/publish:
Pmax ≈ Vmp × Imp within defined tolerance;
Vmp < Voc;
Imp < Isc;
sign/unit validation for temperature coefficients;
physically plausible ranges;
STC model check at 1000 W/m² and 25 °C against datasheet Pmp/Voc/Isc/Vmp/Imp.
Persist residuals. Poor fits remain visible.
11.3 Hourly calculation pipeline
For each timestamp/candidate:
1. resolve solar/resource inputs;
2. compute POA and AOI;
3. apply IAM only through approved model/evidence;
4. compute cell/module temperature using chosen thermal model and wind/POA inputs;
5. compute electrical output through chosen candidate model;
6. apply common soiling scenario/data;
7. apply only approved optical/spectral correction in the primary path;
8. record diagnostics and model-domain flags;
9. integrate specific energy.
11.4 Spectral treatment
Class-level spectral corrections are sensitivity only unless module-specific measured evidence or a reviewed validated pathway exists. Spectral sensitivity may show whether candidate ordering changes, but may not secretly determine the procurement winner.
11.5 Temperature treatment
Store whether temperature is ambient, back-of-module or cell temperature. Record thermal model ID and parameters. Wind speed use, mounting assumptions and POA units must be explicit.
11.6 IAM/AOI treatment
Module-specific IAM curve is preferred. Generic IAM model may be used only when policy allows; applicability and evidence level must be visible.
11.7 Soiling
Common soiling may be a declared scenario applied consistently. Candidate-specific soiling advantage requires evidence. Increasing soiling loss must never increase energy.
11.8 Degradation
The MVP primary lifetime degradation model is a declared scenario, not a claim that SOLARYN predicts exact module-specific climate-driven degradation.
Keep separate:
common degradation scenario;
manufacturer warranty sensitivity;
environmental stress diagnostics;
future calibrated degradation model.
Never translate hot hours/humidity/thermal cycling directly into % degradation/year without calibrated module/BOM evidence.
11.9 Lifetime energy
Generate annual arrays using the selected degradation scenario. Store first-year energy and annual retention separately from warranty sensitivity. Lifetime leader and annual leader can differ; the decision engine must detect that.

12. IEC 61853 and measured-data engine
FR-IEC-01 — Matrix ingestion
Support exact module G–T Pmax matrices with schema validation for irradiance/temperature axes, units, missing points and source metadata.
FR-IEC-02 — Interpolation behavior
Record interpolation method, interpolation fraction, extrapolation fraction and out-of-domain events. Extrapolation must be bounded by policy and visible.
FR-IEC-03 — Blind validation
When a measured dataset exists, separate calibration/training and holdout data. Do not tune against holdout.
Metrics:
MBE
MAE
RMSE
normalized RMSE
maximum absolute residual
interpolation fraction
extrapolation fraction
A gate is PENDING if the required measured data are not available.

13. Decision eligibility and deterministic decision logic
This section replaces the old generic weighted-ranking-first logic.
13.1 Candidate eligibility
Each candidate returns:
simulation_status
decision_eligible boolean
eligibility_reasons[]
electrical_evidence_level
spectral_evidence_level
thermal_evidence_level
resource_status
economics_status
A candidate may still be simulated and displayed even when decision_eligible=false.
13.2 Core comparison metrics
Primary current metrics:
annual specific energy (kWh/kWp/year);
lifetime energy under declared common degradation scenario;
warranty sensitivity lifetime energy;
optional spectral sensitivity;
temperature/exposure diagnostics;
area/efficiency/BOS-relevant quantities;
economic switching threshold when enabled.
13.3 Required decision states
ROBUST_MODELED_ADVANTAGE
Only if:
same eligible leader under annual and required lifetime metric(s);
leader is decision-eligible;
required candidate evidence is complete for the claim;
modeled separation exceeds the declared decision/resource guardrails;
declared sensitivities do not reverse the result;
resource confidence is adequate.
PROVISIONAL_TECHNICAL_LEADER
A numerical leader exists but at least one robustness condition is not met, such as separation below guardrail or resource uncertainty.
EFFECTIVELY_TIED
Differences are within guardrail or relevant sensitivity/scenario changes reverse the leader. Product should recommend deciding on price/risk/constraints or collecting better evidence, not inventing a tie-break score.
INSUFFICIENT_EVIDENCE
Cross-technology claim is not scientifically supportable because a candidate/model/evidence path is inadequate.
13.4 Decision guardrail
The current PoC uses a 2% separation guardrail. Store it as a versioned PoC decision/validation guardrail, not as 95% confidence, P90 or a statistical confidence interval. The default can remain 2.0% until empirical uncertainty analysis replaces it.
required_decision_gap_pct = max(minimum_separation_policy_pct, energy_rating_uncertainty_guardrail_pct)
13.5 Headline rule
The UI/report headline must state scientific status before nominal leader.
Good:
No robust cross-technology winner. Candidate A has the highest provisional modeled annual specific energy, but the lead is below the current decision guardrail and one candidate lacks decision-grade evidence.
Bad:
Candidate A is the winner.

14. Economics and Δ€/W switching threshold
14.1 Economic boundary
Do not invent supplier prices. If a quote is absent, physics analysis remains available and real procurement economics is disabled.
14.2 Switching threshold
For candidate A relative to baseline B, a simplified module/area-BOS threshold can be computed from the modeled lifetime value difference and declared BOS/financial assumptions.
Conceptually:
Δ€/W = NPV(lifetime advantage of A over B) / installed module watts
and/or for the current narrower implementation:
allowable_price_A = price_B + energy_value_difference_per_W + area_BOS_difference_per_W
The result must be labeled module switching threshold or module + area-BOS economic threshold unless a complete validated LCOE model is actually being used.
14.3 Procurement interpretation
If actual quote A is available:
quote_A < allowable_price_A → A is economically supportable under stated assumptions;
quote_A > allowable_price_A → B is economically preferable under stated assumptions;
evidence/uncertainty warnings remain visible and can prevent a robust procurement claim.
14.4 Financial assumptions
Every financial input is user-visible and versioned: project lifetime, discount rate, energy value/revenue assumption, currency/base date, BOS area cost, OPEX differences, replacement assumptions. No silent market defaults.

15. Optional scores and visual summaries
Scores may exist for navigation/visualization, but they are not allowed to manufacture the scientific winner.
Allowed:
display evidence completeness score;
display climate stress indicators;
display normalized visual comparison of raw metrics;
user-selected business preference profile after deterministic scientific state is known.
Not allowed:
mixing arbitrary energy/resilience/maturity weights into a 0–100 number that overrides a tie or insufficient-evidence state;
assigning fabricated numerical penalties to missing evidence;
using maturity/material heuristics to force a technology ordering.

16. Explainability and AI boundary
FR-XAI-01 — Grounded explanation
LLM input is limited to immutable result JSON, evidence records and approved explanatory content. It may summarize, compare and translate technical findings.
It must not:
calculate energy, degradation, Δ€/W or confidence;
alter candidate eligibility;
invent citations or properties;
override deterministic status;
create hidden scenario changes.
Every explanation should reference result/evidence IDs. Add automated numerical-consistency tests that extract numbers from generated answers and compare against the immutable run where feasible.

17. Result dashboard and UX requirements
17.1 Navigation
Primary workflow:
Project → Site & Climate → Candidates → Evidence Review → Analysis → Decision → Economics → Evidence/Report
17.2 Decision page hierarchy
1. Scientific status banner — robust/provisional/tie/insufficient evidence.
2. Provisional modeled leader if one exists.
3. Why this status — gap vs guardrail, evidence gaps, resource warnings.
4. Candidate comparison — annual/lifetime metrics and eligibility.
5. Δ€/W panel — enabled/disabled with reason.
6. Evidence drill-down — source/evidence model path per candidate.
7. Sensitivity — warranty/spectral/resource scenario changes.
8. Limitations — explicit, not buried.
17.3 Climate screen
Show map, coordinates, annual GHI, temperature, RH, wind and resource/source badges. Include NASA vs PVGIS resource comparison and warnings.
17.4 Candidate screen
For each SKU show manufacturer/model, technology, STC specs, temperature coefficient, module area/efficiency, evidence badges, model path and quote state. Ineligible candidates remain visible with reasons.
17.5 Report
Deterministic report includes:
run ID/checksum;
site/project inputs;
climate provider requests and resource comparison;
candidate evidence table;
model versions;
annual/lifetime results;
decision status and guardrails;
economics availability and switching threshold;
sensitivity results;
limitations;
validation gate status;
sources.

18. Architecture
18.1 Recommended MVP architecture
Use a modular monolith with separate frontend and async worker:
Web: Next.js + React + TypeScript
API: Python 3.12+ + FastAPI + Pydantic v2
Scientific: NumPy, pandas, SciPy, pvlib; optional PySAM adapters where justified
Database: PostgreSQL + PostGIS + SQLAlchemy/Alembic
Jobs/cache: Redis + task queue or managed queue
Object storage: S3-compatible / Azure Blob for immutable snapshots, reports and measured datasets
Observability: OpenTelemetry + structured logs + error tracking
CI/CD: GitHub Actions; deterministic fixtures; scheduled live connector smoke tests
Keep external provider/cloud services behind adapters.
18.2 Domain packages
solaryn/  apps/    web/    api/    worker/  packages/    domain/    climate/    resource_validation/    technology_data/    pv_models/    measured_validation/    degradation/    economics/    decision/    provenance/    reports/    explanations/    observability/  db/    migrations/    seeds/  tests/    unit/    physics/    fixtures/providers/    regression/    measured_validation/    integration/    e2e/  docs/    PRD.md    architecture/    model_cards/    data_dictionary/    validation/    runbooks/  .github/  AGENTS.md  docker-compose.yml
18.3 Domain ownership
climate: providers, snapshots, normalization; no technology decisions.
pv_models: physics only; no UI or LLM.
technology_data: parameter/evidence/version governance; no project-specific outcome.
decision: eligibility, guardrail status and deterministic comparison; no external API calls.
economics: switching threshold and financial calculations; no invented data.
reports: render immutable result; never recalculate.
explanations: narrative only over immutable results.

19. Core data model
Required entities:
workspace
user_membership
project
site
system_scenario
climate_request
climate_snapshot
resource_benchmark
technology
module_sku
parameter_value
source_record
evidence_artifact
model_release
analysis_run
candidate_simulation_result
candidate_evidence_status
decision_result
sensitivity_result
economics_input
switching_threshold_result
validation_gate
measured_validation_run
report_artifact
explanation_artifact
audit_event
Completed run entities and source snapshots are immutable. Corrections create new versions.

20. API requirements
Base: /api/v1 or /v1; consistent OpenAPI contract.
Core endpoints:
POST   /projectsGET    /projectsPOST   /projects/{project_id}/sitesPOST   /sites/{site_id}/climate-snapshotsGET    /sites/{site_id}/resource-benchmarkGET    /modulesPOST   /modules/importGET    /modules/{module_id}/evidencePOST   /scenariosPOST   /analysesGET    /analyses/{analysis_id}GET    /analyses/{analysis_id}/candidatesGET    /analyses/{analysis_id}/decisionGET    /analyses/{analysis_id}/provenancePOST   /analyses/{analysis_id}/reportsPOST   /analyses/{analysis_id}/explanationsPOST   /validation/iec61853GET    /admin/validation-gatesGET    /admin/source-health
All mutable write endpoints enforce workspace authorization and schema validation. Analysis creation is idempotent.

21. Result JSON contract
{  "schema_version": "2.0",  "run_id": "uuid",  "status": "completed",  "site": {    "latitude": 24.7136,    "longitude": 46.6753,    "timezone": "Asia/Riyadh"  },  "versions": {    "code_commit": "git-sha",    "model_release": "2.0.0",    "decision_policy": "poc-guardrails-2.0",    "technology_release": "2026.09"  },  "resource": {    "primary_snapshot_id": "uuid",    "crosscheck_snapshot_id": "uuid",    "status": "warning",    "annual_poa_primary_kwh_m2": 2346.8,    "annual_poa_crosscheck_kwh_m2": 2473.9,    "difference_pct": 5.14  },  "candidates": [    {      "module_id": "MOD_TOPCON_EXAMPLE",      "technology": "TOPCon",      "model_path": "cec_sdm_datasheet_fallback",      "decision_eligible": true,      "evidence": {        "electrical": "exact_manufacturer_verified",        "iec61853": "missing",        "spectral": "technology_class_proxy",        "thermal": "manufacturer_or_default"      },      "metrics": {        "annual_specific_energy_kwh_kwp": 2073.4,        "lifetime_common_degradation_kwh_kwp": 0.0      },      "warnings": []    }  ],  "decision": {    "status": "PROVISIONAL_TECHNICAL_LEADER",    "provisional_leader_module_id": "MOD_TOPCON_EXAMPLE",    "annual_lead_over_second_pct": 1.21,    "required_decision_gap_pct": 2.0,    "robust_winner_module_id": null,    "reasons": [      "annual lead is below decision guardrail",      "resource cross-check discrepancy remains material"    ]  },  "economics": {    "status": "disabled_missing_real_quotes",    "switching_threshold": null  },  "validation_gates": {},  "limitations": [],  "created_at": "ISO-8601"}
Never represent the 2% guardrail as statistical confidence.

22. Validation gates
Store each gate independently:
Gate
Allowed status
Software/runtime
PASS / FAIL
Numerical implementation
PASS / FAIL
Climate/resource validation
PASS / FAIL / PENDING
c-Si module-model validation
PASS / FAIL / PENDING
Cross-technology validation
PASS / FAIL / PENDING
IEC measured-data validation
PASS / FAIL / PENDING
Decision logic
PASS / FAIL
Economics
PASS / FAIL / PENDING
Historical EPC decision replay
PASS / FAIL / PENDING
Bankability
NOT_CLAIMED until a separate validated scope exists
A system can be software-PASS while cross-technology validation remains PENDING.

23. Testing requirements
23.1 Unit tests
Equations, parsers, schema validation, decision state transitions, switching-threshold math, unit conversion and financial precision.
23.2 Physics invariants
higher cell temperature at fixed irradiance must reduce Pmp for negative gamma modules;
lower irradiance at fixed temperature reduces Pmp;
nighttime power is zero/physically handled;
IAM stays within physically valid bounds;
increasing soiling cannot increase energy;
hourly integration matches annual total;
system-size scaling is consistent;
invalid datasheet relationships are rejected/warned.
23.3 Data robustness
Test empty/header-only CSV, one candidate, two candidates, missing quote, optional columns, required missing physics field, duplicate module IDs, comma decimals, semicolon separators, Unicode minus, header spaces, capitalization differences, reordered/extra columns and malformed numerics.
23.4 Regression sites
Freeze representative cases:
Riyadh;
Brussels;
Algiers or comparable warm Mediterranean site;
cold/high-irradiance site when dataset available.
Do not force different winners. If a model upgrade moves a benchmark materially, fail and investigate before updating fixtures.
23.5 External API tests
Normal CI uses recorded provider fixtures. Separate scheduled smoke tests hit live NASA POWER and PVGIS and report service-specific status.
23.6 Measured validation
Use PVPMC/Sandia/IEA PVPS public module-characterization and field datasets where licensing permits. Publish validation metrics and failure cases.

24. Current baseline regression that Codex must preserve initially
The current Riyadh benchmark is an important regression fixture, not proof of universal validity.
Approximate configuration:
Riyadh: 24.7136, 46.6753
year: 2020
project: 100 MWp utility
fixed tilt 25°
azimuth 180°
monofacial
common soiling: 2%
common degradation sensitivity: 0.5%/year
PoC decision guardrail: 2%
Current documented three-candidate behavior:
Jinko TOPCon is nominal/provisional modeled annual leader at about 2073 kWh/kWp/year;
First Solar Series 7 CdTe is exploratory / not decision-grade in the current path;
LONGi Mono PERC is below the Jinko modeled annual result;
lead over second is about 1.21%, below the 2% guardrail;
therefore no robust validated cross-technology winner;
NASA→pvlib versus PVGIS annual POA differs by roughly 5.1%, which remains a resource-validation warning.
Codex must reproduce the accepted fixture before intentionally changing scientific constants/model logic. Any intentional change requires a documented model version bump and regression explanation.

25. Scientific provenance and model governance
Every model release requires:
semantic version;
code commit;
owner/reviewer;
equations/method description;
required inputs and units;
validity domain;
evidence references;
regression metrics;
measured validation status;
known failure modes;
change log.
Every parameter release requires source records and reviewer state. Production publishing fails when mandatory decision-relevant parameters lack provenance.

26. Security, privacy and data governance
server-side workspace isolation and RBAC;
secrets only through secret manager/environment injection;
TLS in transit and managed encryption at rest;
signed/time-limited artifact URLs;
strict file/schema validation;
dependency and secret scanning;
append-only audit events for model/parameter publication and exports;
EU/privacy review for customer/project data and any LLM provider;
do not send confidential project data to narrative AI unless configured policy permits it;
retain raw prompt/question text only if explicitly needed and governed.

27. Non-functional requirements
Reproducibility: 100% of completed runs identify inputs, data snapshots, code/model versions and parameter releases.
Reliability: idempotent analysis jobs; safe retry; partial external failure cannot corrupt completed runs.
Performance: cached completed result loads quickly; external source retrieval is asynchronous.
Accessibility: WCAG-oriented core flows; charts have tables/text alternatives.
Portability: local container setup and cloud adapters.
Observability: trace ID spans API → worker → provider → model pipeline.
Maintainability: typed Python/TypeScript, migrations, ADRs, model cards and tests.

28. Codex implementation roadmap
M0 — Repository & governance foundation
monorepo skeleton;
FastAPI + Next.js health slice;
PostgreSQL/PostGIS + migrations;
auth/workspace abstraction;
canonical units;
AGENTS.md, ADRs, CI, test layout.
Exit: one-command local startup; CI green; workspace-isolated sample resource.
M1 — Site, climate and resource validation
project/site CRUD;
map/coordinates;
NASA POWER adapter + fixtures;
PVGIS adapter + fixtures;
immutable climate snapshot;
POA pipeline;
resource benchmark/discrepancy.
Exit: Riyadh/Brussels/Algiers fixtures reproduce resource outputs with visible provenance.
M2 — Module evidence and physics
module SKU schema/import;
provenance records;
c-Si datasheet model adapter;
IEC 61853 matrix adapter;
thermal/AOI/IAM/soiling layers;
exploratory model state;
physics invariants.
Exit: candidate outputs reproducible; exact model path/evidence visible.
M3 — Decision engine
candidate eligibility;
annual/lifetime comparison;
robust/provisional/tie/insufficient states;
guardrail policy;
sensitivity stability;
immutable result JSON.
Exit: Riyadh regression returns provisional/no robust cross-technology winner under current evidence.
M4 — Economics and reports
quote inputs;
switching-threshold calculation;
area-BOS economics;
deterministic report;
JSON export;
scenario revision.
Exit: missing quote disables procurement economics cleanly; hand-calculation fixture matches threshold.
M5 — Measured validation and pilot hardening
IEC/PVPMC blind validation runner;
metrics/gate dashboard;
historical EPC replay data model;
grounded explanation assistant;
security/accessibility/observability hardening.
Exit: published validation artifacts; pilot can reproduce result and inspect evidence.

29. Suggested issue backlog for Codex
1. FOUND-001 Initialize monorepo and local Docker services.
2. FOUND-002 Add canonical units and scientific result types.
3. AUTH-001 Workspace/RBAC skeleton.
4. SITE-001 Project/site persistence and map contract.
5. CLIM-001 NASA POWER provider with frozen fixture.
6. CLIM-002 PVGIS provider with frozen fixture.
7. CLIM-003 Time normalization and leap-year tests.
8. CLIM-004 Solar position + POA pipeline.
9. CLIM-005 Resource benchmark and discrepancy status.
10. MOD-001 Module SKU schema and CSV importer.
11. MOD-002 Parameter provenance/evidence records.
12. MOD-003 Datasheet sanity/STC validation.
13. PHY-001 c-Si CEC/single-diode adapter.
14. PHY-002 IEC 61853 matrix ingestion/interpolation.
15. PHY-003 Thermal model adapter.
16. PHY-004 IAM/AOI and soiling layers.
17. PHY-005 Spectral sensitivity gate.
18. LIFE-001 Common degradation/warranty-sensitivity models.
19. DEC-001 Candidate decision eligibility.
20. DEC-002 Leader/gap calculation.
21. DEC-003 Robust/provisional/tie/insufficient state machine.
22. DEC-004 Guardrail policy and sensitivity stability.
23. ECO-001 Commercial quote schema.
24. ECO-002 Switching-threshold calculator + hand fixture.
25. RUN-001 Async immutable analysis orchestration.
26. UI-001 Project/site/climate workflow.
27. UI-002 Candidate evidence review.
28. UI-003 Decision result hierarchy and limitations.
29. RPT-001 Deterministic report.
30. VAL-001 IEC/PVPMC validation runner and gate table.
31. EPC-001 Historical decision replay schema.
32. XAI-001 Grounded explanation adapter with numeric consistency tests.

30. Definition of done for every Codex task
A task is not done until:
requirement/acceptance criteria are met;
tests cover happy path and key errors;
scientific changes include unit/provenance/model-version impact;
migrations are safe;
OpenAPI/types are updated;
authorization is tested for new resources;
structured logs/metrics are added where relevant;
no secrets/private data leak;
relevant regression tests pass;
documentation/model card/ADR is updated when behavior changes.

31. Absolute “do not do” list
Codex must not:
rewrite the scientific core merely because outputs look unintuitive;
tune constants to make technologies separate more strongly;
force different winners by climate for demonstration;
fabricate IEC datasets or module measurements;
fabricate supplier/EPC prices;
infer degradation from warranty as measured field degradation;
turn environmental exposure proxies directly into module-specific degradation without calibration;
call a deterministic scenario P50/P90;
call the 2% guardrail statistical confidence;
call the current switching threshold full LCOE unless full LCOE is implemented;
hide failed/ineligible candidates;
suppress validation discrepancies;
let narrative AI alter numerical decisions;
replace missing evidence with undocumented defaults.

32. Acceptance criteria for SOLARYN MVP
The MVP is acceptable for a technical pilot when all are true:
a user can select any supported coordinate and create an immutable site/climate snapshot;
NASA/PVGIS data provenance and discrepancy are visible;
at least two exact module SKUs can be compared under identical project assumptions;
the model path and evidence level for every candidate are visible;
candidate ineligibility does not crash or disappear;
deterministic engine can return all four decision states;
the current Riyadh regression is reproduced or a versioned scientific change explains why not;
measured IEC/PVPMC validation can be executed and outputs RMSE/MBE/MAE/nRMSE where data exist;
missing real quote leaves physics available and commercial decision disabled;
Δ€/W switching threshold passes an independent hand-calculation fixture;
report numbers match immutable result JSON;
LLM explanation cannot alter numbers/status;
completed run is reproducible by version/input IDs;
validation gate table is shown and bankability remains NOT_CLAIMED until a separate validated scope exists.

33. Reference sources
SOLARYN internal project sources
SOLARYN — Story & Executive Summary — full vision, first wedge, EPC validation strategy, Δ€/W concept and roadmap.
SOLARYN V9.2.1 Audit and Validation Prompt — scientific guardrails, evidence hierarchy, validation phases, decision states, economics boundary and testing.
SOLARYN_POC_FINAL_VALIDATION_Technical_Dictionary_Equations — module CSV/evidence schema and technical dictionary.
Current epc_decision.py behavior and documented frozen Riyadh regression.
SOLARYN_PLATFORM_OVERVIEW.md and current UI/UX briefs — frontend/backend workflow and map-first interaction.
External scientific and product references
1. IEC 61215-1-1:2021 — design qualification does not quantitatively predict module lifetime: https://webstore.iec.ch/en/publication/61346
2. IEA PVPS Task 13 — Optimisation of Photovoltaic Systems for Different Climates (2025): https://iea-pvps.org/key-topics/t13-optimisation-pv-systems-different-climates-2025/
3. IEC 61853-1 — irradiance and temperature performance measurements: https://webstore.iec.ch/en/publication/6035
4. IEC 61853-2:2026 — spectral responsivity, incidence angle and module operating temperature measurements: https://webstore.iec.ch/en/publication/86013
5. Sandia PVPMC datasets, including IEC 61853 module characterization and field datasets: https://pvpmc.sandia.gov/datasets/
6. Sandia/IEA PVPS Task 13 module validation dataset: https://pvpmc.sandia.gov/datasets/iea-pvps-task-13-module-validation-dataset/
7. NASA POWER Hourly API: https://power.larc.nasa.gov/docs/services/api/temporal/hourly/
8. European Commission JRC PVGIS non-interactive API: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en
9. pvlib ModelChain documentation: https://pvlib-python.readthedocs.io/en/stable/
10. PVcase product/help documentation: https://help.pvcase.com/
11. RatedPower platform: https://ratedpower.com/platform/
12. Anza renewable equipment intelligence: https://www.anzarenewables.com/
13. SunSolve / PV Lighthouse documentation: https://docs.sunsolve.com/en/power/introduction/what-is-sunsolve-power/
14. OpenAI guidance on using Codex, including persistent AGENTS.md context and issue-sized tasks: https://openai.com/business/guides-and-resources/how-openai-uses-codex/

34. One sentence Codex should remember
SOLARYN is not built to always choose a winner; it is built to determine whether the available physics, climate, module evidence and commercial data are sufficient to make a defensible decision — and to quantify the value of that decision when they are.