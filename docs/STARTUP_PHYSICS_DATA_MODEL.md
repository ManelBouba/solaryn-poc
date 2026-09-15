
# SOLARYN Startup + Physics Data Model V3

This version upgrades SOLARYN from a simple climate score into a TCAD-inspired startup model.

## Data split

- `01_pv_technology_master.csv`: one row per PV technology.
- `02_material_physics.csv`: material/device physics parameters used by the physics engine.
- `03_site_climate.csv`: site-level climate inputs.
- `04_cost_market.csv`: cost, bankability, supply-chain, recyclability and LCOE proxy inputs.
- `05_layer_stack.csv`: TCAD-inspired layer stack for each technology.
- `06_defects_contacts.csv`: series/shunt/contact/interface-defect parameters.
- `technology_master.csv`: backward-compatible master file used by the current Streamlit/ranking pipeline.

## Physics features added

Bandgap, electron affinity, ionization energy, conduction/valence band positions, absorption coefficient, optical penetration depth, refractive index, extinction coefficient, Urbach energy, electron/hole mobility, carrier lifetime, defect density, diffusion length, mobility-lifetime product, Voc loss, recombination factor, thermal conductivity, moisture sensitivity, UV stability, ion migration, phase stability, carbon footprint, recyclability and supply-chain risk.

## Model logic

1. Compute optical absorption using Beer-Lambert proxy.
2. Compute diffusivity using Einstein relation.
3. Compute diffusion length from mobility and lifetime.
4. Estimate recombination risk from defect density / lifetime.
5. Correct efficiency using operating cell temperature and temperature coefficient.
6. Adjust degradation using climate, moisture, UV and ion-migration sensitivities.
7. Rank technologies using lifetime-energy, stability, cost, maturity and physics quality.

## Important note

This is not a full numerical TCAD solver. It is a startup-ready, TCAD-inspired physics engine that approximates the physical drivers before ranking technologies.

## Source anchors

- NREL PV efficiency benchmarks: https://www.nrel.gov/pv/cell-efficiency.html
- PV Education equations and solar-cell fundamentals: https://www.pveducation.org/
- Fraunhofer ISE Photovoltaics Report: https://www.ise.fraunhofer.de/en/publications/studies/photovoltaics-report.html
