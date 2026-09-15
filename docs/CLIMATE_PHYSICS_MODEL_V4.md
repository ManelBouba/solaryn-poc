# SOLARYN Climate Physics Model V4

This version removes the old direct mapping:

```text
climate_zone -> static score -> technology recommendation
```

and replaces it with a physical climate-to-device chain:

```text
site latitude/longitude + annual climate
-> representative hourly POA irradiance from solar geometry
-> Sandia module/cell temperature
-> PVWatts DC power temperature correction
-> dynamic soiling optical transmittance with rainfall cleaning
-> Arrhenius/Peck degradation acceleration
-> annual kWh/kWp and 25-year lifetime energy index
-> LCOE proxy and recommendation ranking
```

## Implemented files

- `src/climate_physics.py`
- `src/physics_model.py`
- `src/recommendation_engine.py`
- `data/raw/sites.csv` now includes Algeria, Saudi Arabia, and Egypt desert examples.

## Main physical equations

### Solar geometry

Approximate declination:

```text
delta = 23.45 deg * sin(360 * (284 + n) / 365)
```

Solar zenith:

```text
cos(theta_z) = sin(phi)sin(delta) + cos(phi)cos(delta)cos(omega)
```

This is used to create a representative 12-month x 24-hour irradiance profile.

### Sandia module and cell temperature

```text
T_module = E_POA * exp(a + b * WS) + T_air
T_cell = T_module + (E_POA / 1000) * DeltaT
```

### PVWatts DC power correction

```text
P_dc = P_stc * (E_POA / 1000) * [1 + gamma * (T_cell - 25)]
```

For very low irradiance, the PVWatts low-light quadratic correction is used.

### Soiling optical loss

```text
SR_t = exp(-k_soil * dry_days)
P_soiled = P_clean * SR_t
```

Rainfall partially resets the soiling ratio.

### Arrhenius thermal degradation acceleration

```text
AF_T = exp((Ea / kB) * (1/T_ref - 1/T_cell))
```

### Peck humidity acceleration

```text
AF_H = (RH/RH_ref)^n * AF_T
```

### Lifetime energy index

```text
lifetime_energy = annual_yield * mean((1 - degradation_rate)^year), year=0..24
```

## Important limitation

This is not full TCAD. Full TCAD solves Poisson + drift-diffusion + recombination equations numerically across the device mesh. This SOLARYN version is a startup-ready physics digital twin approximation designed to make the recommendation depend on real climate/device coupling rather than static climate labels.
