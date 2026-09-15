# Solaryn Physics V2 Model Equations

This version upgrades Solaryn from a resilience-only score into a simplified TCAD-inspired PV performance model.

## 1. Optical absorption

Optical penetration depth:

```text
optical_penetration_depth_um = 10000 / absorption_coefficient_cm-1
```

Beer-Lambert absorption proxy:

```text
A = 1 - exp(-alpha * thickness_cm)
```

## 2. Carrier transport

Einstein relation:

```text
D = mobility * kT/q
```

Diffusion length:

```text
L = sqrt(D * tau)
```

where tau is carrier lifetime.

## 3. Recombination proxy

```text
recombination_factor = defect_density / carrier_lifetime_ns
```

Lower values are better.

## 4. Voltage loss

```text
Voc_loss = bandgap_eV - voc_typical_V
```

This is a simplified voltage-loss proxy, not a full diode equation.

## 5. Cell temperature and temperature loss

Operating cell temperature is estimated from site temperature, GHI and wind:

```text
cell_temperature_C = 0.65 * avg_temp_C + 0.35 * max_temp_C + irradiance_heat_rise - wind_cooling
```

Site-adjusted efficiency:

```text
eta_site = eta_STC * (1 + temp_coefficient_pct_C/100 * (cell_temperature_C - 25))
```

## 6. Soiling and moisture losses

```text
soiling_loss_pct = soiling_stress * (1 - soiling_resilience/5) * 0.08
moisture_loss_pct = moisture_stress * (1 - humidity_resilience/5) * 0.03
```

## 7. Climate-adjusted degradation

```text
adjusted_degradation = baseline_degradation
                     + 0.0035 * climate_severity
                     + 0.0020 * heat_stress * (1 - heat_resilience/5)
                     + 0.0020 * moisture_stress * (1 - humidity_resilience/5)
```

## 8. Energy yield index

```text
performance_ratio = 0.82 * (1 - soiling_loss_pct/100) * (1 - moisture_loss_pct/100)
energy_yield_index = eta_site * performance_ratio * GHI_kWh_m2_year
```

## 9. 25-year lifetime energy index

```text
lifetime_factor_25y = average((1 - degradation/100)^(year-1)) for years 1..25
lifetime_energy_index_25y = energy_yield_index * lifetime_factor_25y
```

## 10. Final suitability score

For commercial rooftop-like projects:

```text
score = 0.30*lifetime_energy_score
      + 0.18*efficiency_score
      + 0.17*degradation_score
      + 0.15*cost_score
      + 0.10*maturity_score
      + 0.07*bankability_score
      + 0.03*physics_quality_score
```

For utility projects:

```text
score = 0.32*lifetime_energy_score
      + 0.08*efficiency_score
      + 0.18*degradation_score
      + 0.22*cost_score
      + 0.10*maturity_score
      + 0.07*bankability_score
      + 0.03*physics_quality_score
```

## 11. Important limitation

This is not a full Silvaco/SCAPS numerical solver. It is a startup-level physics engine inspired by TCAD inputs:

- bandgap
- absorption coefficient
- mobility
- lifetime
- defect density
- layer thickness
- temperature coefficient
- degradation behavior
- cost and maturity constraints

A full TCAD version would require layer-by-layer meshing, Poisson equation, carrier continuity equations, boundary conditions, contact work functions, interface states and recombination models.
