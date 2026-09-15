> **Historical donor-branch note:** this document describes the Step-1 branch before the merge. The merged app keeps the modern three-objective decision engine instead of the old single V6 ranking.

# SOLARYN V7 PoC — Step 1 Technical Note

## Goal

Replace the V6 daily-to-hourly climate approximation with a real hourly modelling chain before changing the recommendation engine.

## Data chain

1. User selects latitude/longitude on the map.
2. SOLARYN requests NASA POWER hourly data in UTC.
3. Requested variables:
   - `ALLSKY_SFC_SW_DWN` — global horizontal solar irradiance (GHI)
   - `ALLSKY_SFC_SW_DNI` — direct normal irradiance (DNI), when available through the selected POWER service configuration
   - `ALLSKY_SFC_SW_DIFF` — diffuse horizontal irradiance (DHI), when available
   - `T2M` — air temperature
   - `RH2M` — relative humidity
   - `WS10M` — 10 m wind speed
   - `PRECTOTCORR` — precipitation
4. If direct/diffuse irradiance is unavailable, SOLARYN retains NASA's true hourly GHI and derives only DNI/DHI with pvlib Erbs decomposition.
5. pvlib calculates solar position from UTC timestamps and coordinates.
6. pvlib transposes GHI/DNI/DHI to plane-of-array irradiance.
7. pvlib Sandia Array Performance Model estimates cell temperature.
8. Each PV technology's temperature coefficient is applied through pvlib PVWatts DC power.

## Fixed-tilt PoC assumption

Until project geometry becomes a formal decision input, the PoC uses an equator-facing fixed surface:

- tilt = `clip(abs(latitude), 5°, 35°)`
- azimuth = 180° in the northern hemisphere, 0° in the southern hemisphere
- albedo = 0.20
- isotropic diffuse transposition

These are explicit assumptions and must later become project/system inputs or optimization variables.

## Sandia temperature model

The PoC uses pvlib's `open_rack_glass_polymer` SAPM parameter set:

- `a = -3.56`
- `b = -0.075`
- `ΔT = 3 °C`

Wind input is NASA POWER `WS10M`, consistent with the model's 10 m wind-speed input definition.

## DC power

pvlib's PVWatts DC model is used with:

- `Pdc0 = 1000 W` per 1 kWp normalized system
- effective irradiance = plane-of-array irradiance after dynamic soiling transmittance
- technology-specific `gamma_pdc = temp_coefficient_pct_c / 100`

This means technology differences due to temperature coefficient are applied to the same hourly site conditions rather than through arbitrary climate scoring.

## What Step 1 deliberately does not claim

- The existing technology database is not fully source-validated yet.
- The current ranking weights are still the V6 decision layer.
- The degradation activation energies are still PoC proxies and need evidence/calibration.
- Spectral response is not yet explicitly modelled.
- Material/device architecture is not yet driving full I-V behaviour.
- No uncertainty propagation or P50/P90 engine is implemented yet.
- No field-validation accuracy is claimed.

## Next PoC block

Build the source-traceable SOLARYN technology/material/device schema so the physics layer distinguishes real architecture and absorber configurations rather than treating a technology name as a single universal object.
