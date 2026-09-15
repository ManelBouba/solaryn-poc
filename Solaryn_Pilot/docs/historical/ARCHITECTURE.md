# Solaryn architecture

## Product path

`site/project inputs -> hard feasibility -> shared site physics -> candidate response -> system energy -> lifetime scenario -> uncertainty -> economics -> recommendation -> client report`

The architecture intentionally separates four ideas that are easy to conflate:

- **Technical leader** — highest expected annual delivered energy under the declared system model.
- **Lifetime leader** — highest modeled lifetime energy under the declared lifetime evidence/scenario.
- **Commercial leader** — highest project value when actual project costs and revenues are available.
- **Final recommendation** — the option that remains acceptable after evidence gates and uncertainty.

A technical leader is always visible for comparison, but Solaryn does not automatically promote it to a final recommendation.

## Core modules

| Component | Responsibility |
|---|---|
| `src/module_offer_io.py` | Candidate input contract and offer-table parsing |
| `src/data_quality.py` | Dataset and physical consistency checks |
| `src/pvlib_pipeline.py` | Solar-resource/plane-of-array modeling path |
| `src/module_iv_engine.py` | Candidate electrical response and evidence routing |
| `src/system_physics.py` | DC/system behavior and loss accounting |
| `src/lifetime_engine.py` | Declared common degradation and warranty sensitivity paths |
| `src/uncertainty_engine.py` | Shared-resource and candidate-specific uncertainty propagation |
| `src/economics_engine.py` | NPV, LCOE helpers and switching-value sensitivity |
| `src/epc_decision.py` | Decision status, technical/lifetime leaders, P(best) and regret |
| `src/epc_report.py` | Self-contained client HTML report |
| `app/epc_module_mode.py` | Main interactive module-recommendation workflow |

## Evidence routing

The engine does not add a technology-family bonus. Model evidence controls **which model is permitted** and **how wide candidate-specific uncertainty should be**. Missing evidence cannot silently create an advantage.

Electrical route, strongest to weakest:

1. Candidate-specific measured IEC 61853 performance surface.
2. Independently validated device-specific model.
3. Candidate datasheet fit for an applicable model class.
4. Broad family proxy for screening only.

Thermal, spectral, IAM, bifacial and lifetime evidence follow the same principle: measured or candidate-specific evidence has precedence; generic fallbacks remain visible and carry wider uncertainty.

## Decision behavior

`recommendation_decision()` uses one shared resource realization per Monte Carlo sample for all co-located candidates, while candidate-model residuals remain candidate-specific. It reports:

- probability of best annual energy,
- expected regret,
- P50/P90 values,
- technical and lifetime leaders,
- evidence completeness,
- a next-evidence request when the result is fragile.

The Robust/Probable thresholds are configurable product-risk policy, not physical constants.

## UI information architecture

The application is intentionally compact for a high-level demonstration:

1. **Overview** — product promise, current site, evidence and value flow.
2. **Module Recommendation** — candidate comparison, result, uncertainty and export.
3. **Technology Library** — research-screening intelligence; explicitly non-procurement.
4. **Downloads** — client report/results.
5. **Method & Evidence** — measured validation scope and model-routing explanation.
