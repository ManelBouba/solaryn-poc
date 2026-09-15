# Procurement model and equations

Version procurement-1.0.0. The attached concept informed this implementation; proposed infrastructure is not a statement of deployed capability.

## System boundary

The existing Module Recommendation service remains the hourly DC electrical simulation path. The new Procurement Workspace accepts candidate-specific **net AC** specific yield from a consistent external study or manually declared scenario. It does not silently convert the old DC result to AC. The synthetic offers are examples, not measured products. All offers must use the same resource period, geometry, installed DC capacity, DC/AC ratio and loss boundary; this version records the source but cannot independently verify that consistency.

## Physical layer

The independent interval calculator estimates module temperature using Faiman: Tm = Ta + G/(U0 + U1 v). Cell temperature is Tc = Tm + deltaT G/1000. Defaults U0=25 W/(m² K), U1=6.84 W s/(m³ K) and deltaT=3 K are illustrative and require mounting-specific calibration. Module temperature and cell temperature are distinct.

DC specific power is max(0, G/1000 × [1 + gamma(Tc−25)]) in kW/kWp, using gamma=−0.0035/K. AC specific power is min(Pdc × (1−loss) × eta, 1/DCAC); defaults loss=10%, eta=97%, DCAC=1.3. Interval energy equals AC power times interval hours (default 1). The linear approximation is not the full PVWatts implementation: no low-light branch, spectral response, bifacial model, transposition or inverter efficiency curve. It must not be used as annual yield from a single representative interval.

Sources: [Sandia Faiman model](https://pvpmc.sandia.gov/modeling-guide/2-dc-module-iv/module-temperature/faiman-module-temperature-model/), [Sandia cell-temperature model](https://pvpmc.sandia.gov/modeling-guide/2-dc-module-iv/cell-temperature/sandia-cell-temperature-model/), [PVWatts model description](https://pvpmc.sandia.gov/modeling-guide/2-dc-module-iv/point-value-models/pvwatts/).

## Lifecycle layer

For year y=1…N, E_y = C_MWp × Y_AC × (1−L0) × (1−d)^(y−1) × (1−La) × (1−f_y D_y/365), in MWh. The conversion follows 1 MWp × 1 kWh/kWp = 1 MWh. Y_AC is pre-additional-scenario-loss net AC yield. L0 is optional extra early loss, d annual compounded degradation, La optional extra loss. Set L0/La to zero when already included in imported yield. This convention applies early loss at start of year 1 and degradation between years.

The event fraction f_y is nonzero only in the declared event year; downtime D is a full-project-energy-equivalent number of days. Uniform energy over the year is an explicit approximation. Replaced modules conservatively follow the original aging curve afterward. Event replacement cost = C_MWp × 10^6 × f × replacement_EUR/W. Assumed warranty recovery is a fraction of that cost in the same year; no legal entitlement, timing certainty or failure likelihood is inferred.

Climate stressors generate qualitative evidence requests only. They do not change d or generate failure probabilities. The downside sliders apply d'=d+delta_d and Y'=Y(1−haircut). These are deterministic scenarios, **not P50 or P90**. Statistical P90 would require a validated joint uncertainty model, temporal correlations and the 10th percentile of the specified energy distribution; lifetime and one-year P90 are different quantities.

## Financial layer

All amounts are constant EUR, unlevered and pre-tax. r is a real discount rate; cash arrives at year end. CAPEX = C_MWp × 10^6 × (module_quote + common_BOS). O_y = C_MWp × 1000 × (annual_OM + annual_cleaning) + replacement − recovery. Revenue R_y = E_y × PPA_EUR/MWh.

- NPV = −CAPEX + sum[(R_y−O_y)/(1+r)^y].
- LCOE = [CAPEX + sum O_y/(1+r)^y] / [sum E_y/(1+r)^y], EUR/MWh.
- IRR is the rate making NPV zero. It is returned only for a cash-flow sequence with one sign change and a root in the numerical search interval (−99% to approximately 1,000,000); ambiguous or unbracketed cases are null.
- DSCR proxy = (R_y−O_y)/constant annual debt service. Debt service is excluded from unlevered NPV. This is not tax-adjusted CFADS or a debt-sizing model.
- Justified module premium B versus first input A = [PV(operating cash B)−PV(operating cash A)] / installed Wp. Common BOS cancels. Break-even quote B = quote A + justified premium. This is the total justified premium, not additional headroom above B's current quote. NPV difference / installed Wp gives that headroom.

The discounted cost/energy convention follows [NREL comparative PV LCOE documentation](https://www.nlr.gov/pv/lcoe-calculator/documentation). Taxes, inflation, escalation, financing structure, salvage, decommissioning and grid constraints beyond the imported net AC boundary are excluded. Add them explicitly before using this as a complete investment model.

## Evidence and reproducibility

Claims record candidate, model, BOM, field, exact value string, classification, source, page/section, status, reviewer and review date. Quote, net AC yield, degradation and BOM require matching reviewed records for the minimum checklist. Unknown BOM never passes. This minimum gate is not full engineering due diligence. Review status is self-declared, not authenticated. Even complete records produce a provisional scenario leader, never automatic procurement approval. NPV ties within EUR 0.01 have no unique leader.

Saved snapshots contain all candidate inputs, scenario, claims, climate checklist, model version and annual results. SQLite writes new UUID snapshots, which the application does not overwrite. SHA-256 detects accidental payload alteration but is not a signature or tamper-proof audit trail. An operator with filesystem access can modify both data and hashes.

## SaaS implementation boundary

Implemented: project inputs, editable/importable normalized JSON offers, manual evidence register, qualitative climate checklist, scenario comparison, lifecycle charts, NPV/LCOE/IRR, event costs and recovery, price premium, annual cash flows, JSON/Markdown exports and persistent decision history.

This is a runnable **local SaaS workflow prototype**, not a production multi-tenant service. Not implemented: authenticated organizations, RBAC/SSO, immutable audit infrastructure, document storage/OCR/AI extraction, automated certificate reconciliation, native PVsyst/SAM file parsing, PDF/Excel reports, billing, cloud deployment or reviewer approval workflow. These require separate integration and deployment work; no connected external accounts were assumed.

Production design: extract these deterministic functions into a versioned API; enforce authenticated organization membership server-side for every project/document/run; store metadata in PostgreSQL with tenant policies and documents in private object storage; queue extraction with citations for human review; bind approvals to immutable input/result hashes; add migrations, backups, secrets management, upload scanning and integration tests proving cross-tenant access denial. Deploy only after those controls and scientific validations pass.
