# Sources and Assumptions

Solaryn Physics V2 uses approximate, literature-inspired values for a first startup MVP. Every row should later be replaced or calibrated using traceable source values.

Recommended source hierarchy:

1. NREL Best Research-Cell Efficiency Chart for record efficiencies and technology classes.
2. Fraunhofer ISE Photovoltaics Report for commercial module efficiency, technology context and market maturity.
3. PV Education for PV equations such as optical absorption, diffusion, IV-curve concepts, and temperature/module concepts.
4. Peer-reviewed papers for mobility, lifetime, defect density, band offsets, and degradation by technology.
5. Manufacturer datasheets for commercial efficiency, temperature coefficient, module cost proxy, warranty and degradation guarantees.

Important assumptions in this PoC:

- The `technology_master.csv` values are approximate seed values.
- The model uses a simplified optical/transport/recombination proxy, not a full drift-diffusion solver.
- Cost is represented by module cost USD/W, not full system CAPEX.
- Degradation is climate-adjusted using stress proxies, not measured field degradation.
- III-V technologies are penalized for normal utility/commercial use because they are specialty/space/concentrator technologies despite excellent physics.
- Low-TRL technologies are penalized for bankable deployment but kept in the table for future/R&D scenarios.

Next data-improvement step:

Create `data/raw/technology_sources.csv` with one row per parameter:

```csv
technology_id,parameter_name,value,unit,source_url_or_doi,source_type,confidence_score,notes
```
