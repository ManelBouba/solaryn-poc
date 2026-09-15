# Solaryn Database Science Audit — V8.1

This revision preserves the original Solaryn database and product concept. It corrects how database fields are allowed to influence the commercial PoC.

## Database retained
- 30 technology records in `technology_master.csv` / `01_pv_technology_master.csv`
- material physics in `02_material_physics.csv`
- layer stacks in `05_layer_stack.csv`
- defects and contacts in `06_defects_contacts.csv`
- cost/market table in `04_cost_market.csv`
- paper/evidence table and site/climate data

## Allowed to drive commercial energy screening
- hourly climate / irradiance
- POA irradiance and cell temperature
- Pmax temperature coefficient from the Solaryn technology record
- pvlib technology-class spectral mismatch where a documented default class exists
- one common site-level soiling process for all technologies
- database baseline degradation as a scenario for the 25-year projection

## Preserved but not allowed to force the commercial winner yet
- `physics_quality_score` and its mobility/lifetime/defect aggregate
- technology-specific soiling resilience score
- heat/humidity resilience scores
- generic `confidence_score` values
- Arrhenius/Peck stress as an annual field degradation multiplier

## Why
Those fields remain scientifically useful for the long-term material/device intelligence vision, but the current database does not yet provide parameter-specific validation/provenance sufficient to convert them into a bankability-grade commercial ranking.

## Important database limitation
Many technology records are tagged `source_quality = literature_range`, share generic source URLs, and share the same `confidence_score = 0.75`. V8.1 does not delete these records; it prevents those generic metadata values from masquerading as quantified uncertainty.

## Fair-comparison defaults
The corrected commercial PoC uses a common project degradation scenario and a common project soiling-loss assumption across all candidate technologies. The original technology-specific database degradation and resilience fields are preserved and displayed, but they do not determine the default commercial winner until they are validated at module/offer level.
