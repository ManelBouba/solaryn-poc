# SOLARYN V8.2 — Validation Protocol Before EPC Pilot

## Objective

Validate that Solaryn's module-level result is traceable to accepted PV physics and actual module inputs, rather than static technology scores.

## Benchmark modules

Start with the four sourced seed records, then repeat with the actual EPC offers:

- PERC — LONGi LR5-72HPH-550M
- TOPCon — JinkoSolar JKM575N-72HL4-V
- HJT — REC Alpha Pure-RX 470
- CdTe — First Solar Series 7 TR1 530

## Benchmark climates

Minimum initial portfolio:

1. Hamburg / northern Germany — cool, diffuse
2. Brussels — temperate
3. Phoenix — hot and high irradiance
4. Dubai / Abu Dhabi — hot, arid, dusty context
5. Jeddah — hot/humid/coastal context
6. Algiers — Mediterranean / semi-arid
7. high-altitude or cold sunny location — low-temperature contrast

## Test A — Input integrity

For every module verify against the manufacturer datasheet:

- Pmax ≈ Vmp × Imp;
- Vmp < Voc;
- Imp < Isc;
- alpha Isc units;
- beta Voc units;
- gamma Pmax units;
- electrical series-cell count;
- module dimensions/area;
- construction type;
- warranty endpoint and duration;
- source URL and source version/date.

A failed or uncertain critical field blocks EPC mode; do not impute a convenient value.

## Test B — STC reproduction

After CEC fitting, run 1000 W/m² and 25 °C and verify the solved IV curve reproduces the datasheet MPP closely. Store residuals for Pmp, Voc and Isc.

Suggested PoC acceptance target: Pmp within ±1% of datasheet after fitting; investigate any larger residual.

## Test C — Directional physics

For each module independently:

- raising cell temperature at fixed effective irradiance should reduce Pmp according to the fitted response;
- reducing irradiance should produce a nonlinear IV response rather than a static efficiency lookup;
- IAM should reduce effective irradiance at high AOI;
- spectral correction should alter effective irradiance, not raw POA;
- common soiling should affect all candidates consistently.

## Test D — Resource benchmark

Use identical location, year, tilt and azimuth.

Compare:

- NASA POWER → pvlib annual POA;
- PVGIS hourly in-plane irradiation.

A difference is not automatically an error because the resource datasets differ. Investigate >10% before presenting the result, and document the reason rather than auto-calibrating Solaryn.

## Test E — PVsyst benchmark

For at least Phoenix, Dubai and Hamburg:

1. use the same module model or closest validated module input;
2. use the same fixed tilt/azimuth;
3. disable or harmonize shading, mismatch, wiring, availability and other losses so the compared boundary is equivalent;
4. compare monthly and annual DC energy, not only final AC yield;
5. compare cell-temperature and spectral/optical effects where the external model exposes them.

Do not expect exact equality between different resource/model stacks. The goal is traceability and explainable residuals.

## Test F — Ranking robustness

For each site, record:

- annual DC specific-energy leader;
- warranty-derived lifetime-scenario leader;
- gap to second place;
- source/fit warnings;
- PVGIS resource delta.

If the leader changes between annual and lifetime scenarios, Solaryn must return **No robust winner**.

If the lead is below the declared decision-separation threshold, Solaryn must return **No robust winner**.

## Test G — Procurement switching point

Insert actual EPC quotes and a documented area-sensitive BOS assumption.

Check the threshold manually:

`candidate indifference price = baseline quote + ΔNPV energy value + Δarea-BOS advantage`

Do not label this LCOE.

## Test H — Degradation/reliability discipline

Do not convert the current heat/RH/UV/cycling exposures into `%/year` degradation. Use them to identify where BOM/reliability evidence is needed.

For a real EPC pilot, collect:

- IEC/PVEL or equivalent reliability evidence where legally/contractually available;
- encapsulant/backsheet/glass/BOM details;
- warranty terms;
- field history or independent test evidence;
- known PID/LeTID/UV/damp-heat/corrosion sensitivities relevant to the exact product.

## Definition of done for first EPC pilot

The PoC is ready to test on a real EPC project only when:

- all selected modules pass input and CEC-fit checks;
- hourly DC outputs are physically plausible;
- resource cross-check is reviewed;
- at least three climate benchmarks have been compared with an accepted external engineering model;
- the output can legitimately say either a stable leader or no robust winner;
- every commercial input used in the conclusion has a traceable source or explicit user-supplied assumption.
