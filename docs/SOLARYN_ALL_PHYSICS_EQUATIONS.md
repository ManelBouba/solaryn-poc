# SOLARYN all physics equations — climate, material, device, degradation

This file documents the equations implemented in the SOLARYN physics-first MVP.

## 1. NASA climate inputs

SOLARYN downloads daily NASA POWER renewable-energy climate parameters from the selected map coordinate:

- `ALLSKY_SFC_SW_DWN`: daily all-sky global horizontal irradiance, kWh/m²/day
- `T2M`: average 2 m air temperature, °C
- `T2M_MAX`: daily maximum 2 m air temperature, °C
- `T2M_MIN`: daily minimum 2 m air temperature, °C
- `RH2M`: 2 m relative humidity, %
- `WS2M`: 2 m wind speed, m/s
- `PRECTOTCORR`: corrected precipitation, mm/day
- `AOD_55`: aerosol optical depth at 550 nm, optional if available

## 2. Solar geometry

Solar declination:

```text
δ = 23.45° sin[360°(284+n)/365]
```

Hour angle:

```text
ω = 15°(t_solar - 12)
```

Solar zenith:

```text
cosθz = sinφ sinδ + cosφ cosδ cosω
```

Extraterrestrial correction:

```text
E0 = 1 + 0.033 cos(360° n / 365)
```

Extraterrestrial horizontal irradiance:

```text
I0h = I_sc E0 cosθz
```

Relative air mass:

```text
AM = 1 / [cosθz + 0.50572(96.07995 - θz)^(-1.6364)]
```

## 3. Daily-to-hourly irradiance downscaling

NASA daily GHI is distributed into daylight hours using solar geometry weights:

```text
w_h = cosθz^1.25
GHI_h = GHI_day × 1000 × w_h / Σw_h
```

## 4. GHI to POA irradiance

Clearness index:

```text
K_t = GHI / I0h
```

Erbs-type diffuse fraction:

```text
F_d = 1 - 0.09K_t,                         K_t ≤ 0.22
F_d = 0.9511 - 0.1604K_t + 4.388K_t² - 16.638K_t³ + 12.336K_t⁴, 0.22 < K_t ≤ 0.80
F_d = 0.165,                               K_t > 0.80
```

Diffuse and direct irradiance:

```text
DHI = F_d GHI
DNI = (GHI - DHI) / cosθz
```

Plane-of-array irradiance, isotropic sky approximation:

```text
G_POA = DNI cosθ + DHI(1 + cosβ)/2 + GHIρ(1 - cosβ)/2
```

where β is tilt and ρ is ground albedo.

## 5. Cell temperature models

Sandia module temperature:

```text
T_module = G_POA exp(a + b WS) + T_air
```

Sandia cell temperature:

```text
T_cell = T_module + (G_POA / 1000) ΔT
```

Faiman module/cell temperature alternative:

```text
T_cell = T_air + G_POA / (U0 + U1 WS)
```

## 6. PVWatts-style DC power

For POA irradiance above 125 W/m²:

```text
P_dc = P_stc (G_POA / 1000) [1 + γ(T_cell - 25)]
```

For very low irradiance, SOLARYN uses a quadratic low-light correction:

```text
P_dc = P_stc [0.008 G_POA² / 1000] [1 + γ(T_cell - 25)]
```

## 7. Optical absorption and generation

Beer-Lambert law:

```text
I(x) = I0 exp(-αx)
```

Absorbed fraction:

```text
A = 1 - exp(-αd)
```

Optical penetration depth:

```text
δ_opt = 1/α
δ_opt(µm) = 10000 / α(cm⁻¹)
```

Approximate short-circuit current chain:

```text
Jsc ≈ q ∫ Φ(λ) A(λ) CE(λ) dλ
```

## 8. Carrier transport

Einstein relation:

```text
D = μkT/q
```

Diffusion length:

```text
L = sqrt(Dτ)
```

Collection efficiency proxy:

```text
CE = 1 - exp[-3(L/d)]
```

Mobility-lifetime product:

```text
μτ = μ × τ
```

## 9. Recombination proxies

Defect-driven recombination proxy:

```text
R_proxy = Nt / τ
```

Open-circuit voltage loss:

```text
Voc_loss = Eg - Voc
```

Solar-cell diode relation:

```text
Voc = (nkT/q) ln(Jsc/J0 + 1)
```

## 10. Soiling physics

Soiling ratio / optical transmittance:

```text
SR = P_soiled / P_clean
SR = exp(-k_soil dry_days)
```

Aerosol-corrected dry deposition proxy:

```text
SR = exp[-k_soil dry_days (1 + AOD_55)]
```

Rain cleaning:

```text
if rainfall ≥ threshold:
    SR_new = SR_old + cleaning_efficiency(1 - SR_old)
```

## 11. Temperature and humidity degradation

Arrhenius acceleration:

```text
AF_T = exp[(Ea/kB)(1/T_ref - 1/T_cell)]
```

Peck humidity-temperature acceleration:

```text
AF_TH = (RH/RH_ref)^n AF_T
```

Site degradation:

```text
degradation_site = degradation_STC × AF_climate × UV_factor × salt_factor
```

## 12. Lifetime energy and ranking

Annual energy:

```text
E_year1 = Σ P_dc,h × SR_h × Δt
```

25-year lifetime energy:

```text
E_25y = Σ_y=1^25 E_year1 (1 - degradation_site)^(y-1)
```

LCOE proxy:

```text
LCOE_proxy = module_cost / E_25y
```

Final SOLARYN ranking uses simulated lifetime energy, LCOE proxy, degradation, maturity, and physics-quality terms. The model does **not** apply arbitrary technology boosts by country or climate zone.
