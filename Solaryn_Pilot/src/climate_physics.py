from __future__ import annotations

import math
from typing import Dict

import numpy as np
import pandas as pd
try:
    import pvlib
except ImportError:  # lets non-pvlib unit tests run; app requirements still include pvlib
    pvlib = None

KB_EV = 8.617333262e-5
Q_C = 1.602176634e-19
DAYS_IN_MONTH = np.array([31,28,31,30,31,30,31,31,30,31,30,31], dtype=float)
MID_MONTH_DOY = np.array([15,46,74,105,135,166,196,227,258,288,319,349], dtype=float)
SOLAR_CONSTANT_W_M2 = 1367.0


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


# -----------------------------------------------------------------------------
# SOLAR GEOMETRY AND IRRADIANCE TRANSPOSITION
# -----------------------------------------------------------------------------

def solar_declination_rad(day_of_year: float) -> float:
    """Cooper declination approximation: delta = 23.45 sin(360(284+n)/365)."""
    return math.radians(23.45) * math.sin(math.radians(360.0 * (284.0 + day_of_year) / 365.0))


def inverse_relative_earth_sun_distance(day_of_year: float) -> float:
    """E0 correction for extraterrestrial irradiance."""
    return 1.0 + 0.033 * math.cos(math.radians(360.0 * day_of_year / 365.0))


def cos_solar_zenith(latitude_deg: float, day_of_year: float, solar_hour: float) -> float:
    lat = math.radians(latitude_deg)
    dec = solar_declination_rad(day_of_year)
    hour_angle = math.radians(15.0 * (solar_hour - 12.0))
    cosz = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(hour_angle)
    return max(0.0, cosz)


def air_mass_kasten_young(cos_zenith: float) -> float:
    """Relative air mass approximation, valid for sun above horizon."""
    if cos_zenith <= 0:
        return np.inf
    zenith_deg = math.degrees(math.acos(_clip(cos_zenith, 0, 1)))
    return 1.0 / (cos_zenith + 0.50572 * ((96.07995 - zenith_deg) ** -1.6364))


def cos_incidence_fixed_tilt(latitude_deg: float, day_of_year: float, solar_hour: float, tilt_deg: float | None = None) -> float:
    """Equator-facing fixed-tilt incidence approximation."""
    lat = math.radians(latitude_deg)
    beta = math.radians(abs(latitude_deg) if tilt_deg is None else tilt_deg)
    beta = min(max(beta, math.radians(5)), math.radians(35))
    dec = solar_declination_rad(day_of_year)
    hour_angle = math.radians(15.0 * (solar_hour - 12.0))
    effective_lat = lat - math.copysign(beta, lat if lat != 0 else 1)
    cost = math.sin(dec) * math.sin(effective_lat) + math.cos(dec) * math.cos(effective_lat) * math.cos(hour_angle)
    return max(0.0, cost)


def erbs_diffuse_fraction_hourly(clearness_index: float) -> float:
    """Erbs-style diffuse fraction approximation from clearness index."""
    kt = _clip(clearness_index, 0.0, 1.2)
    if kt <= 0.22:
        return 1.0 - 0.09 * kt
    if kt <= 0.80:
        return 0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4
    return 0.165


def poa_isotropic_transposition(ghi_w_m2: float, latitude_deg: float, day_of_year: float, solar_hour: float,
                                tilt_deg: float | None = None, albedo: float = 0.2) -> Dict[str, float]:
    """
    Convert GHI to POA using a simple isotropic sky model:
    G_POA = DNI*cos(theta) + DHI*(1+cos(beta))/2 + GHI*rho*(1-cos(beta))/2
    DNI and DHI are estimated from clearness/diffuse fraction when NASA DNI is not downloaded.
    """
    ghi = max(float(ghi_w_m2), 0.0)
    beta_deg = min(max(abs(latitude_deg), 5.0), 35.0) if tilt_deg is None else float(tilt_deg)
    beta = math.radians(beta_deg)
    cosz = cos_solar_zenith(latitude_deg, day_of_year, solar_hour)
    cost = cos_incidence_fixed_tilt(latitude_deg, day_of_year, solar_hour, beta_deg)
    if cosz <= 0 or ghi <= 0:
        return {"poa_w_m2": 0.0, "dni_w_m2": 0.0, "dhi_w_m2": 0.0, "cos_zenith": cosz, "air_mass": np.inf}

    i0h = SOLAR_CONSTANT_W_M2 * inverse_relative_earth_sun_distance(day_of_year) * cosz
    kt = ghi / max(i0h, 1e-9)
    fd = _clip(erbs_diffuse_fraction_hourly(kt), 0.05, 0.95)
    dhi = ghi * fd
    dni = max((ghi - dhi) / max(cosz, 0.05), 0.0)
    beam = dni * cost
    sky = dhi * (1.0 + math.cos(beta)) / 2.0
    ground = ghi * albedo * (1.0 - math.cos(beta)) / 2.0
    poa = max(0.0, beam + sky + ground)
    return {"poa_w_m2": poa, "dni_w_m2": dni, "dhi_w_m2": dhi, "cos_zenith": cosz, "air_mass": air_mass_kasten_young(cosz)}


# -----------------------------------------------------------------------------
# NASA DAILY DATA TO REPRESENTATIVE HOURLY WEATHER
# -----------------------------------------------------------------------------

def nasa_daily_to_hourly_weather(nasa_daily: pd.DataFrame, latitude: float, longitude: float,
                                 tilt_deg: float | None = None, albedo: float = 0.2) -> pd.DataFrame:
    """
    Convert NASA POWER daily climate into hourly rows for the physics engine.

    NASA daily GHI is distributed through daylight hours using solar geometry weights.
    This is not a forecast; it is a physics-based downscaling from daily resource to hourly
    operating conditions for a startup MVP.
    """
    df = nasa_daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    rows = []
    for _, d in df.iterrows():
        date = d["date"]
        doy = int(date.dayofyear)
        ghi_kwh_day = max(float(d.get("ALLSKY_SFC_SW_DWN", 0.0) or 0.0), 0.0)
        t_mean = float(d.get("T2M", 25.0) if pd.notna(d.get("T2M", pd.NA)) else 25.0)
        t_max = float(d.get("T2M_MAX", t_mean + 8.0) if pd.notna(d.get("T2M_MAX", pd.NA)) else t_mean + 8.0)
        t_min = float(d.get("T2M_MIN", t_mean - 8.0) if pd.notna(d.get("T2M_MIN", pd.NA)) else t_mean - 8.0)
        rh = _clip(float(d.get("RH2M", 50.0) if pd.notna(d.get("RH2M", pd.NA)) else 50.0) / 100.0, 0.01, 1.0)
        wind = max(float(d.get("WS2M", 2.0) if pd.notna(d.get("WS2M", pd.NA)) else 2.0), 0.1)
        rain = max(float(d.get("PRECTOTCORR", 0.0) if pd.notna(d.get("PRECTOTCORR", pd.NA)) else 0.0), 0.0)
        aod = d.get("AOD_55", pd.NA)
        aod_value = float(aod) if pd.notna(aod) else np.nan

        weights = []
        for h in range(24):
            cosz = cos_solar_zenith(latitude, doy, h + 0.5)
            weights.append(cosz ** 1.25 if cosz > 0 else 0.0)
        weight_sum = max(sum(weights), 1e-12)

        for h, w in enumerate(weights):
            ghi_wh_m2_h = ghi_kwh_day * 1000.0 * (w / weight_sum)
            ghi_w_m2 = ghi_wh_m2_h  # 1-hour interval, Wh/m2 ≈ W/m2 average over hour.
            poa = poa_isotropic_transposition(ghi_w_m2, latitude, doy, h + 0.5, tilt_deg, albedo)
            # Diurnal temperature: minimum near sunrise, maximum mid-afternoon.
            t_air = t_mean + ((t_max - t_min) / 2.0) * math.sin(2.0 * math.pi * (h - 8.0) / 24.0)
            t_air = min(max(t_air, t_min - 2.0), t_max + 2.0)
            rows.append({
                "date": date,
                "month": int(date.month),
                "day_of_year": doy,
                "hour": h,
                "days_weight": 1.0,
                "ghi_w_m2": ghi_w_m2,
                "poa_w_m2": poa["poa_w_m2"],
                "dni_w_m2": poa["dni_w_m2"],
                "dhi_w_m2": poa["dhi_w_m2"],
                "cos_zenith": poa["cos_zenith"],
                "air_mass": poa["air_mass"],
                "temp_air_c": t_air,
                "wind_speed_m_s": wind,
                "relative_humidity": rh,
                "rainfall_mm_day": rain,
                "aod_55": aod_value,
                "uv_index_proxy": max(0.0, poa["poa_w_m2"] / 1000.0) * (1.0 + 0.08 * max(0.0, 2.0 - poa["air_mass"] if np.isfinite(poa["air_mass"]) else 0.0)),
            })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# FALLBACK REPRESENTATIVE WEATHER WHEN USER DOES NOT DOWNLOAD NASA DATA
# -----------------------------------------------------------------------------

def _monthly_temperature_mean(avg_temp_c: float, max_temp_c: float, latitude: float, month_index: int) -> float:
    amp = max(3.0, (max_temp_c - avg_temp_c) * 0.45)
    phase = 6 if latitude >= 0 else 0
    return avg_temp_c + amp * math.cos(2 * math.pi * (month_index - phase) / 12.0)


def _hourly_air_temperature(monthly_mean_c: float, daily_amp_c: float, hour: int) -> float:
    return monthly_mean_c + daily_amp_c * math.sin(2 * math.pi * (hour - 8) / 24.0)


def generate_representative_weather(site: pd.Series) -> pd.DataFrame:
    """Fallback 12-month x 24-hour representative year when NASA POWER is not used."""
    lat = float(site.get("latitude", 0.0))
    annual_ghi = float(site.get("ghi_kwh_m2_year", 1600.0))
    avg_temp = float(site.get("avg_temp_c", 25.0))
    max_temp = float(site.get("max_temp_c", avg_temp + 15.0))
    wind = max(float(site.get("wind_speed_m_s", 2.0)), 0.1)
    humidity = _clip(float(site.get("humidity_pct", 50.0)) / 100.0, 0.01, 1.0)
    rainfall_year = max(float(site.get("rainfall_mm_year", 300.0)), 0.0)

    rows = []
    raw_sum = 0.0
    for m, (doy, ndays) in enumerate(zip(MID_MONTH_DOY, DAYS_IN_MONTH), start=1):
        m_mean = _monthly_temperature_mean(avg_temp, max_temp, lat, m - 1)
        daily_amp = max(4.0, (max_temp - avg_temp) * 0.35)
        rain_month = rainfall_year * (1.0 + 0.35 * math.cos(2 * math.pi * (m - 1) / 12.0)) / 12.0
        for hour in range(24):
            cosz = cos_solar_zenith(lat, doy, hour + 0.5)
            raw = cosz ** 1.25 if cosz > 0 else 0.0
            raw_sum += raw * ndays
            rows.append({
                "month": m,
                "day_of_year": int(doy),
                "hour": hour,
                "days_weight": ndays,
                "raw_ghi": raw,
                "temp_air_c": _hourly_air_temperature(m_mean, daily_amp, hour),
                "wind_speed_m_s": wind,
                "relative_humidity": humidity,
                "rainfall_mm_day": rain_month / max(ndays, 1.0),
                "aod_55": np.nan,
            })
    df = pd.DataFrame(rows)
    scale = (annual_ghi * 1000.0) / max(raw_sum, 1e-9)
    df["ghi_w_m2"] = (df["raw_ghi"] * scale).clip(0, 1200)
    poa_rows = []
    for _, r in df.iterrows():
        poa = poa_isotropic_transposition(float(r["ghi_w_m2"]), lat, float(r["day_of_year"]), float(r["hour"]) + 0.5)
        poa_rows.append(poa)
    poa_df = pd.DataFrame(poa_rows)
    df = pd.concat([df.reset_index(drop=True), poa_df.reset_index(drop=True)], axis=1)
    df["uv_index_proxy"] = (df["poa_w_m2"] / 1000.0).clip(0, 2)
    return df.drop(columns=["raw_ghi"])


# -----------------------------------------------------------------------------
# MODULE TEMPERATURE, POWER, SOILING, DEGRADATION
# -----------------------------------------------------------------------------

def sandia_module_temperature_c(poa_w_m2: float, temp_air_c: float, wind_speed_m_s: float,
                                a: float = -3.56, b: float = -0.075) -> float:
    """T_module = E_POA * exp(a + b*WS) + T_air."""
    return float(poa_w_m2) * math.exp(a + b * float(wind_speed_m_s)) + float(temp_air_c)


def sandia_cell_temperature_c(poa_w_m2: float, temp_air_c: float, wind_speed_m_s: float,
                              a: float = -3.56, b: float = -0.075, delta_t: float = 3.0) -> float:
    """T_cell = T_module + (E_POA/1000)*DeltaT."""
    t_module = sandia_module_temperature_c(poa_w_m2, temp_air_c, wind_speed_m_s, a, b)
    return t_module + (float(poa_w_m2) / 1000.0) * delta_t


def faiman_cell_temperature_c(poa_w_m2: float, temp_air_c: float, wind_speed_m_s: float,
                              u0: float = 25.0, u1: float = 6.84) -> float:
    """Faiman thermal model: T_module = T_air + E_POA/(U0+U1*wind)."""
    return float(temp_air_c) + float(poa_w_m2) / max(u0 + u1 * float(wind_speed_m_s), 1e-9)


def pvwatts_dc_power_kw_per_kwp(poa_w_m2: float, t_cell_c: float, gamma_pdc_per_c: float) -> float:
    """PVWatts DC power per kWp. Uses pvlib when installed, with equation fallback."""
    poa = max(float(poa_w_m2), 0.0)
    if pvlib is not None:
        pdc_w = pvlib.pvsystem.pvwatts_dc(
            effective_irradiance=poa,
            temp_cell=float(t_cell_c),
            pdc0=1000.0,
            gamma_pdc=float(gamma_pdc_per_c),
            temp_ref=25.0,
        )
        return max(float(pdc_w) / 1000.0, 0.0)
    temp_factor = max(0.0, 1.0 + float(gamma_pdc_per_c) * (float(t_cell_c) - 25.0))
    return max((poa / 1000.0) * temp_factor, 0.0)


def soiling_ratio_exponential(dry_days: float, k_soil_daily: float, aod_55: float | None = None) -> float:
    """Optical transmittance/soiling ratio: SR = exp(-k*d). AOD increases k when available."""
    aod_factor = 1.0
    if aod_55 is not None and not pd.isna(aod_55):
        aod_factor = 1.0 + _clip(float(aod_55), 0.0, 1.0)
    return math.exp(-max(k_soil_daily, 0.0) * max(dry_days, 0.0) * aod_factor)


def arrhenius_acceleration(t_cell_c: float, activation_energy_ev: float, t_ref_c: float = 25.0) -> float:
    """AF_T = exp(Ea/kB * (1/T_ref - 1/T_use))."""
    t = float(t_cell_c) + 273.15
    tref = t_ref_c + 273.15
    return math.exp((float(activation_energy_ev) / KB_EV) * (1.0 / tref - 1.0 / t))


def peck_humidity_acceleration(t_cell_c: float, relative_humidity: float, activation_energy_ev: float,
                               n: float = 2.5, rh_ref: float = 0.50, t_ref_c: float = 25.0) -> float:
    """AF_TH = (RH/RHref)^n * Arrhenius(T)."""
    rh = _clip(relative_humidity, 0.01, 1.0)
    return (rh / rh_ref) ** n * arrhenius_acceleration(t_cell_c, activation_energy_ev, t_ref_c)


def technology_degradation_params(tech: pd.Series) -> Dict[str, float]:
    family = str(tech.get("family", "")).lower()
    name = str(tech.get("technology_name", "")).lower()
    status = str(tech.get("commercialization_status", "")).lower()
    if "perovskite" in family or "perovskite" in name:
        ea, n_hum = 0.45, 3.0
    elif "organic" in family or "opv" in name or "dssc" in name or "quantum" in name:
        ea, n_hum = 0.35, 3.0
    elif "thin" in family or "cdte" in name or "cigs" in name:
        ea, n_hum = 0.65, 2.3
    elif "iii" in family or "gaas" in name:
        ea, n_hum = 0.80, 1.5
    else:
        ea, n_hum = 0.70, 2.0
    if "research" in status or "pilot" in status:
        ea *= 0.85
    return {"activation_energy_ev": ea, "humidity_exponent": n_hum}


def _spectral_module_type(tech: pd.Series) -> tuple[str | None, str]:
    """Map the Solaryn database technology to pvlib's documented spectral classes."""
    family = str(tech.get("family", "")).lower()
    sub = str(tech.get("subfamily", "")).lower()
    name = str(tech.get("technology_name", "")).lower()
    if "silicon" in family:
        if "poly" in name or "mc-si" in sub or "microcrystalline" in name:
            return "multisi", "database family mapped to pvlib multisi"
        return "monosi", "database family mapped to pvlib monosi"
    if "cdte" in name or "cdsete" in name:
        return "cdte", "CdTe-class spectral proxy (CdSeTe uses CdTe proxy)"
    if "cigs" in name:
        return "cigs", "database family mapped to pvlib CIGS"
    if "amorphous" in name or "a-si" in sub:
        return "asi", "database family mapped to pvlib a-Si"
    return None, "no validated default pvlib spectral class"


def _spectral_factor_series(weather_df: pd.DataFrame, tech: pd.Series) -> tuple[pd.Series, str, bool]:
    module_type, note = _spectral_module_type(tech)
    factor = pd.Series(1.0, index=weather_df.index, dtype=float)
    if module_type is None or pvlib is None:
        return factor, note, False
    if "precipitable_water_cm" not in weather_df.columns or "airmass_absolute" not in weather_df.columns:
        return factor, note + "; atmospheric inputs unavailable", False
    pw = pd.to_numeric(weather_df["precipitable_water_cm"], errors="coerce")
    am = pd.to_numeric(weather_df["airmass_absolute"], errors="coerce")
    valid = pw.notna() & am.notna() & (pd.to_numeric(weather_df.get("poa_w_m2", 0), errors="coerce") > 0)
    if not valid.any():
        return factor, note + "; no valid daylight atmospheric inputs", False
    try:
        values = pvlib.spectrum.spectral_factor_firstsolar(pw[valid], am[valid], module_type=module_type)
        factor.loc[valid] = pd.Series(values, index=pw[valid].index).clip(lower=0.80, upper=1.20)
        factor = factor.fillna(1.0)
        return factor, note, True
    except Exception:
        return factor, note + "; spectral calculation failed safely to 1.0", False



def _technology_iam_factor(weather_df: pd.DataFrame, tech: pd.Series) -> tuple[pd.Series, str, bool]:
    """Angle-of-incidence optical modifier.

    Uses pvlib's physical IAM when AOI is available. A technology/module-specific
    refractive index may be supplied as evidence; otherwise a common glass value
    is used, so AOI affects absolute yield but does not create an artificial
    technology winner.
    """
    factor = pd.Series(1.0, index=weather_df.index, dtype=float)
    if pvlib is None or "aoi_deg" not in weather_df.columns:
        return factor, "AOI unavailable; neutral factor", False
    aoi = pd.to_numeric(weather_df["aoi_deg"], errors="coerce")
    valid = aoi.notna() & (pd.to_numeric(weather_df.get("poa_w_m2", 0), errors="coerce") > 0)
    if not valid.any():
        return factor, "AOI unavailable during daylight; neutral factor", False
    n = tech.get("cover_refractive_index", np.nan)
    if pd.isna(n):
        n = 1.526
        basis = "common glass refractive index; no technology differentiation"
    else:
        n = float(n)
        basis = "technology/module-specific refractive-index evidence"
    try:
        vals = pvlib.iam.physical(aoi[valid], n=n)
        factor.loc[valid] = pd.Series(vals, index=aoi[valid].index).fillna(0.0).clip(0.0, 1.05)
        return factor, basis, True
    except Exception:
        return factor, "AOI calculation failed safely to neutral factor", False


def _dynamic_soiling_series(weather_df: pd.DataFrame, site: pd.Series, tech: pd.Series) -> tuple[pd.Series, str]:
    """Transparent rain-reset/dry-deposition soiling model.

    Technology-specific differentiation is only allowed when an explicit
    ``soiling_susceptibility_factor`` is supplied. Otherwise the factor is 1.0,
    preserving a common project-level soiling assumption across technologies.
    """
    fixed_loss = _clip(float(site.get("soiling_loss_assumption_pct", 2.0)), 0.0, 30.0)
    use_dynamic = bool(site.get("dynamic_soiling", False))
    if not use_dynamic:
        return pd.Series(1.0-fixed_loss/100.0, index=weather_df.index, dtype=float), "fixed common project soiling assumption"
    base_k = max(float(site.get("soiling_daily_rate_pct", 0.15)), 0.0) / 100.0
    rain_reset = max(float(site.get("soiling_rain_reset_mm", 5.0)), 0.0)
    susceptibility = float(tech.get("soiling_susceptibility_factor", 1.0)) if pd.notna(tech.get("soiling_susceptibility_factor", np.nan)) else 1.0
    susceptibility = _clip(susceptibility, 0.25, 4.0)
    out=[]; dry_days=0.0
    for _, r in weather_df.iterrows():
        rain=max(float(r.get("rainfall_mm_day",0.0) or 0.0),0.0)
        weight=max(float(r.get("days_weight",1.0) or 1.0),0.0)
        if rain >= rain_reset:
            dry_days=0.0
        else:
            dry_days += weight/24.0
        aod=r.get("aod_55", np.nan)
        out.append(soiling_ratio_exponential(dry_days, base_k*susceptibility, None if pd.isna(aod) else float(aod)))
    basis = "dynamic rain-reset/AOD soiling; technology differentiation only from explicit susceptibility evidence"
    return pd.Series(out,index=weather_df.index,dtype=float), basis



def _front_optical_irradiance_series(weather_df: pd.DataFrame, tech: pd.Series) -> tuple[pd.Series, pd.Series, str, bool]:
    """Return front-side optical POA after incidence-angle reflection.

    Preference order:
    1. If the weather pipeline already contains component-wise IAM-corrected
       ``poa_optical_w_m2``, reuse it. This avoids double application of the incidence-angle modifier.
    2. Otherwise calculate a physical IAM modifier from AOI and apply it to POA.

    A technology-specific refractive index is only used when supplied explicitly;
    otherwise the common-glass optical result is non-differentiating evidence.
    """
    poa = pd.to_numeric(weather_df.get("poa_w_m2", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    supplied_n = tech.get("cover_refractive_index", np.nan)
    if "poa_optical_w_m2" in weather_df.columns and pd.isna(supplied_n):
        optical = pd.to_numeric(weather_df["poa_optical_w_m2"], errors="coerce").fillna(0.0).clip(lower=0.0)
        factor = (optical / poa.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0.0, 1.05)
        return optical, factor, "component-wise common-glass IAM from weather pipeline", True
    iam_factor, note, applied = _technology_iam_factor(weather_df, tech)
    return poa * iam_factor, iam_factor, note, applied


def _rear_bifacial_irradiance_series(weather_df: pd.DataFrame, tech: pd.Series) -> tuple[pd.Series, str, bool]:
    """Optional bifacial rear contribution with fail-closed evidence handling.

    Rear irradiance must be supplied by a dedicated bifacial/view-factor model or
    measurement. SOLARYN does not infer rear irradiance from a fixed generic gain.
    """
    rear = pd.Series(0.0, index=weather_df.index, dtype=float)
    bif = tech.get("bifaciality_factor", np.nan)
    if pd.isna(bif) or float(bif) <= 0:
        return rear, "monofacial or bifaciality not supplied", False
    if "poa_rear_w_m2" not in weather_df.columns:
        return rear, "bifacial module but rear irradiance unavailable; no bifacial gain assumed", False
    rear_raw = pd.to_numeric(weather_df["poa_rear_w_m2"], errors="coerce").fillna(0.0).clip(lower=0.0)
    bif = _clip(float(bif), 0.0, 1.2)
    rear_eff = rear_raw * bif
    return rear_eff, "rear POA × measured/supplied bifaciality factor", True


def _environmental_transmission_series(weather_df: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Apply externally supplied shading and snow transmission factors only.

    These are project/layout/environment effects, not technology heuristics. If the
    time series is absent the factor is neutral (1.0). Values are clipped to [0,1].
    """
    factor = pd.Series(1.0, index=weather_df.index, dtype=float)
    details = {"shading_applied": False, "snow_applied": False}
    if "shading_factor" in weather_df.columns:
        sh = pd.to_numeric(weather_df["shading_factor"], errors="coerce").fillna(1.0).clip(0.0, 1.0)
        factor *= sh
        details["shading_applied"] = True
        details["mean_shading_factor"] = float(sh.mean())
    else:
        details["mean_shading_factor"] = 1.0
    if "snow_factor" in weather_df.columns:
        sf = pd.to_numeric(weather_df["snow_factor"], errors="coerce").fillna(1.0).clip(0.0, 1.0)
        factor *= sf
        details["snow_applied"] = True
        details["mean_snow_factor"] = float(sf.mean())
    else:
        details["mean_snow_factor"] = 1.0
    return factor, details


def _select_cell_temperature(weather_df: pd.DataFrame, tech: pd.Series, poa_thermal: pd.Series) -> tuple[pd.Series, str, bool]:
    """Evidence-ordered module/cell temperature selection.

    True measured cell/module temperature outranks a module-specific thermal model.
    A generic temperature generated upstream is never relabeled as measured and does
    not override explicit U0/U1 module evidence.
    """
    temp_present = "temp_cell_c" in weather_df.columns and pd.to_numeric(weather_df.get("temp_cell_c"), errors="coerce").notna().all()
    measured_flag = bool(weather_df.get("temp_cell_is_measured", pd.Series(False, index=weather_df.index)).astype(bool).all()) if "temp_cell_is_measured" in weather_df.columns else False
    if temp_present and measured_flag:
        return pd.to_numeric(weather_df["temp_cell_c"], errors="coerce").astype(float), "measured cell/module temperature", True
    if pd.notna(tech.get("thermal_u0_w_m2k", np.nan)) and pd.notna(tech.get("thermal_u1_w_s_m3k", np.nan)):
        u0=float(tech.get("thermal_u0_w_m2k")); u1=float(tech.get("thermal_u1_w_s_m3k"))
        ta=pd.to_numeric(weather_df.get("temp_air_c", 25.0), errors="coerce").fillna(25.0)
        ws=pd.to_numeric(weather_df.get("wind_speed_m_s", 2.0), errors="coerce").fillna(2.0).clip(lower=0.0)
        vals=[faiman_cell_temperature_c(g,t,w,u0,u1) for g,t,w in zip(poa_thermal,ta,ws)]
        return pd.Series(vals,index=weather_df.index,dtype=float), "module-specific Faiman U0/U1", False
    if temp_present:
        src = str(weather_df["temp_cell_source"].iloc[0]) if "temp_cell_source" in weather_df.columns else "upstream modeled/provided temperature"
        return pd.to_numeric(weather_df["temp_cell_c"], errors="coerce").astype(float), src, False
    ta=pd.to_numeric(weather_df.get("temp_air_c", 25.0), errors="coerce").fillna(25.0)
    ws=pd.to_numeric(weather_df.get("wind_speed_m_s", 2.0), errors="coerce").fillna(2.0).clip(lower=0.0)
    vals=[sandia_cell_temperature_c(g,t,w) for g,t,w in zip(poa_thermal,ta,ws)]
    return pd.Series(vals,index=weather_df.index,dtype=float), "common Sandia open-rack thermal fallback", False


def _degradation_rate_for_lifetime(site: pd.Series, tech: pd.Series) -> tuple[float, str, bool]:
    """Choose a lifetime degradation rate without inventing climate acceleration.

    A candidate-specific field-calibrated rate may drive lifetime energy. Otherwise
    the project-wide scenario is used so climate stress diagnostics cannot silently
    manufacture a technology winner.
    """
    field_rate = tech.get("field_validated_degradation_pct_year", np.nan)
    field_status = str(tech.get("degradation_evidence_status", "")).strip().lower()
    if pd.notna(field_rate) and field_status in {"field_validated", "measured_long_term", "validated"}:
        return max(float(field_rate), 0.0), "candidate-specific field-validated degradation rate", True
    return max(float(site.get("degradation_scenario_pct_year", 0.50)), 0.0), "common project degradation scenario; environmental stress is diagnostic only", False


def _environmental_exposure_diagnostics(weather_df: pd.DataFrame, t_cell: pd.Series, poa: pd.Series, site: pd.Series) -> dict:
    """Measured/modelled exposure metrics for reliability screening, not degradation rates."""
    rh = pd.to_numeric(weather_df.get("relative_humidity", 0.5), errors="coerce").fillna(0.5)
    if float(rh.max()) <= 1.5:
        rh_pct = rh * 100.0
    else:
        rh_pct = rh
    daylight = poa > 50.0
    hot55 = int(((t_cell > 55.0) & daylight).sum())
    hot65 = int(((t_cell > 65.0) & daylight).sum())
    damp = int(((t_cell >= 40.0) & (rh_pct >= 85.0)).sum())
    if "date" in weather_df.columns:
        day = pd.to_datetime(weather_df["date"], errors="coerce")
    elif "time_utc" in weather_df.columns:
        day = pd.to_datetime(weather_df["time_utc"], errors="coerce", utc=True).dt.floor("D")
    else:
        day = pd.Series(np.arange(len(weather_df)) // 24, index=weather_df.index)
    tr = pd.DataFrame({"day":day, "tc":t_cell}).dropna().groupby("day")["tc"].agg(lambda x: float(x.max()-x.min()))
    salinity = _clip(float(site.get("salinity_risk", 0.0)), 0.0, 2.0)
    return {
        "hot_cell_hours_gt_55c": hot55,
        "hot_cell_hours_gt_65c": hot65,
        "damp_heat_hours_rh85_t40": damp,
        "mean_daily_cell_temp_range_c": round(float(tr.mean()) if len(tr) else 0.0, 2),
        "days_cell_temp_range_gt_30c": int((tr > 30.0).sum()) if len(tr) else 0,
        "salinity_risk_input": salinity,
        "reliability_exposure_basis": "exposure diagnostics only; no uncalibrated Arrhenius/Peck conversion to annual degradation",
    }

def _technology_pmax_series(weather_df: pd.DataFrame, tech: pd.Series, effective_irradiance: pd.Series, t_cell: pd.Series) -> tuple[pd.Series, dict]:
    """Use measured IEC 61853 G-T evidence when supplied; otherwise explicit fallback.

    This is the key evidence hierarchy for technology screening: measured Pmax(G,T)
    surfaces outrank a single STC temperature coefficient.
    """
    matrix_file=str(tech.get("iec61853_matrix_file", "") or "").strip()
    pmax_ref=float(tech.get("pmax_w", 1000.0) or 1000.0)
    if matrix_file:
        from pathlib import Path
        from src.iec61853_engine import read_iec61853_matrix, validate_iec61853_matrix, interpolate_iec61853_pmax
        mp=Path(matrix_file)
        if not mp.is_absolute():
            mp=Path.cwd()/mp
        if mp.exists():
            m=read_iec61853_matrix(mp)
            val=validate_iec61853_matrix(m,module_pmax_w=pmax_ref if "pmax_w" in tech.index else None)
            p,diag=interpolate_iec61853_pmax(m,effective_irradiance,t_cell)
            # normalize measured module watts to kW per kWp
            series=(p/max(pmax_ref,1e-9)).astype(float)
            return series, {"electrical_model_basis":"measured IEC 61853 Pmax(G,T) matrix","electrical_model_measured":True,"iec_measured_points":val.measured_points,**diag}
    gamma=float(tech.get("temp_coefficient_pct_c", -0.35))/100.0
    vals=[pvwatts_dc_power_kw_per_kwp(g,t,gamma) for g,t in zip(effective_irradiance,t_cell)]
    return pd.Series(vals,index=weather_df.index,dtype=float), {"electrical_model_basis":"PVWatts gamma fallback; no measured irradiance-response surface","electrical_model_measured":False}


def _annual_coverage(weather_df: pd.DataFrame) -> tuple[float, float, bool]:
    weights = pd.to_numeric(weather_df.get("days_weight", pd.Series(1.0, index=weather_df.index)), errors="coerce").fillna(1.0)
    representative = bool((weights > 1.5).any())
    if representative:
        return float(weights.sum()/24.0), 1.0, True
    if "date" in weather_df.columns:
        days = pd.to_datetime(weather_df["date"], errors="coerce").dropna().dt.floor("D").nunique()
    elif "time_utc" in weather_df.columns:
        days = pd.to_datetime(weather_df["time_utc"], utc=True, errors="coerce").dropna().dt.floor("D").nunique()
    else:
        days = int(round(len(weather_df)/24.0))
    expected=max(int(days)*24,1)
    return float(days), min(1.0, len(weather_df)/expected), False


def simulate_site_technology(site: pd.Series, tech: pd.Series, weather: pd.DataFrame | None = None) -> Dict[str, float]:
    """Evidence-aware hourly multi-physics technology simulation.

    Order of operations:
      broadband POA -> front IAM optics + optional rear bifacial POA -> spectral
      mismatch -> soiling -> externally supplied shading/snow -> cell temperature
      -> measured IEC 61853 Pmax(G,T), otherwise explicit PVWatts fallback -> energy.

    Reliability exposures (heat, damp heat, thermal cycling, UV/salinity inputs) are
    reported separately. They modify lifetime degradation only when an explicit
    field-validated degradation rate exists; otherwise a common project scenario is
    used to prevent uncalibrated climate heuristics from creating a technology winner.
    """
    weather_df = weather.copy() if weather is not None else generate_representative_weather(site)
    coverage_days, hour_coverage, representative = _annual_coverage(weather_df)
    if not representative and (coverage_days < 330 or hour_coverage < 0.95):
        raise ValueError(
            f"Annual/lifetime analysis requires a near-complete reference year; received "
            f"{coverage_days:.0f} days at {hour_coverage:.1%} coverage."
        )

    poa = pd.to_numeric(weather_df.get("poa_w_m2", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    weights = pd.to_numeric(weather_df.get("days_weight", pd.Series(1.0,index=weather_df.index)), errors="coerce").fillna(1.0)

    # 1) Optical incidence-angle response. Reuse component-wise corrected POA when
    # the upstream pvlib pipeline already calculated it; never apply IAM twice.
    front_optical, iam_factor, iam_note, iam_applied = _front_optical_irradiance_series(weather_df, tech)

    # 2) Optional bifacial rear-side irradiance. No fixed generic bifacial gain.
    rear_effective, bifacial_note, bifacial_applied = _rear_bifacial_irradiance_series(weather_df, tech)
    optical_total = front_optical + rear_effective

    # 3) Spectral mismatch (technology-class proxy unless stronger evidence path exists).
    spectral_factor, spectral_note, spectral_applied = _spectral_factor_series(weather_df, tech)
    spectral_total = optical_total * spectral_factor

    # 4) Soiling, then project-level shading/snow transmission.
    soiling_series, soiling_basis = _dynamic_soiling_series(weather_df, site, tech)
    env_transmission, env_diag = _environmental_transmission_series(weather_df)
    effective_irradiance = spectral_total * soiling_series * env_transmission

    # Thermal input should use absorbed/front-side irradiance before soiling as a
    # practical module-temperature driver; rear contribution is included if modeled.
    t_cell, thermal_basis, thermal_measured = _select_cell_temperature(weather_df, tech, optical_total)

    # Electrical response: measured IEC 61853 G-T matrix first, then transparent
    # PVWatts gamma fallback. No country/technology winner bonuses are permitted.
    p_series, electrical_diag = _technology_pmax_series(weather_df, tech, effective_irradiance, t_cell)
    p_no_soiling, _ = _technology_pmax_series(weather_df, tech, spectral_total * env_transmission, t_cell)
    p_no_spectral, _ = _technology_pmax_series(weather_df, tech, optical_total * soiling_series * env_transmission, t_cell)
    p_ref25, _ = _technology_pmax_series(weather_df, tech, effective_irradiance, pd.Series(25.0,index=weather_df.index))
    p_no_env, _ = _technology_pmax_series(weather_df, tech, spectral_total * soiling_series, t_cell)

    annual_yield = float((p_series * weights).sum())
    clean_yield = max(float((p_no_soiling * weights).sum()), 1e-9)
    no_spectral_yield = max(float((p_no_spectral * weights).sum()), 1e-9)
    ref25 = max(float((p_ref25 * weights).sum()), 1e-9)
    no_env_yield = max(float((p_no_env * weights).sum()), 1e-9)

    soiling_loss_pct = max(0.0, (1.0 - annual_yield / clean_yield) * 100.0)
    temperature_effect_pct = (annual_yield / ref25 - 1.0) * 100.0
    spectral_effect_pct = (annual_yield / no_spectral_yield - 1.0) * 100.0
    project_env_loss_pct = max(0.0, (1.0 - annual_yield / no_env_yield) * 100.0)

    # Reliability/lifetime: use calibrated candidate degradation only when evidence
    # explicitly says it is field validated. Otherwise use common project scenario.
    degradation_rate, degradation_basis, degradation_measured = _degradation_rate_for_lifetime(site, tech)
    database_degradation = max(float(tech.get("baseline_degradation_pct_year", 0.6)), 0.0)
    exposure = _environmental_exposure_diagnostics(weather_df, t_cell, poa, site)
    daylight = poa > 50.0
    tday = t_cell[daylight] if daylight.any() else pd.Series([25.0])
    uv_dose = float((pd.to_numeric(weather_df.get("uv_index_proxy", 0.0), errors="coerce").fillna(0.0) * weights).sum())

    poa_energy = max(float((poa * weights).sum()), 1e-9)
    front_optical_energy = float((front_optical * weights).sum())
    aoi_effect_pct = (front_optical_energy / poa_energy - 1.0) * 100.0
    rear_energy = float((rear_effective * weights).sum())

    return {
        "annual_yield_kwh_kwp": round(annual_yield, 2),
        "clean_annual_yield_kwh_kwp": round(clean_yield, 2),
        "annual_soiling_loss_pct": round(soiling_loss_pct, 2),
        "avg_cell_temperature_C": round(float(tday.mean()), 2),
        "p95_cell_temperature_C": round(float(tday.quantile(.95)), 2),
        "temperature_effect_pct": round(temperature_effect_pct, 2),
        "temperature_loss_pct": round(max(0.0, -temperature_effect_pct), 2),
        "temperature_gain_pct": round(max(0.0, temperature_effect_pct), 2),
        "spectral_effect_pct": round(spectral_effect_pct, 2),
        "mean_spectral_factor": round(float(spectral_factor[daylight].mean()) if daylight.any() else 1.0, 4),
        "spectral_model_applied": bool(spectral_applied),
        "spectral_model_note": spectral_note,
        "aoi_effect_pct": round(aoi_effect_pct, 2),
        "mean_iam_factor": round(float(iam_factor[daylight].mean()) if daylight.any() else 1.0, 4),
        "aoi_model_applied": bool(iam_applied),
        "aoi_model_note": iam_note,
        "bifacial_model_applied": bool(bifacial_applied),
        "bifacial_model_note": bifacial_note,
        "rear_effective_irradiance_kwh_m2": round(rear_energy/1000.0, 2),
        "project_environment_loss_pct": round(project_env_loss_pct, 2),
        "shading_applied": bool(env_diag["shading_applied"]),
        "snow_applied": bool(env_diag["snow_applied"]),
        "mean_shading_factor": round(float(env_diag["mean_shading_factor"]), 4),
        "mean_snow_factor": round(float(env_diag["mean_snow_factor"]), 4),
        "thermal_model_basis": thermal_basis,
        "thermal_temperature_measured": bool(thermal_measured),
        **electrical_diag,
        "site_degradation_pct_year": round(degradation_rate, 3),
        "database_degradation_pct_year": round(database_degradation, 3),
        "degradation_rate_basis": degradation_basis,
        "degradation_rate_measured": bool(degradation_measured),
        "degradation_acceleration_factor": 1.0,
        "degradation_stress_factor": 1.0,
        "uv_dose_proxy": round(uv_dose, 2),
        **exposure,
        "weather_coverage_days": round(float(coverage_days), 1),
        "hour_coverage_fraction": round(float(hour_coverage), 4),
        "soiling_model_basis": soiling_basis,
        "effective_irradiance_chain": "POA -> IAM(front) + optional bifacial rear -> spectral -> soiling -> shading/snow -> Pmax(G,T)",
    }

def pvgis_hourly_to_physics_weather(pvgis: pd.DataFrame, nasa_daily: pd.DataFrame | None = None) -> pd.DataFrame:
    """Convert PVGIS hourly POA into the shared SOLARYN weather schema.

    PVGIS supplies in-plane irradiance/temperature directly. NASA daily climate can
    optionally enrich humidity, rainfall and wind. This function is retained for
    independent PVGIS cross-checking beside the primary NASA-hourly + pvlib path.
    """
    df = pvgis.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    df["day_of_year"] = df["date"].dt.dayofyear
    df["hour"] = df["date"].dt.hour
    df["days_weight"] = 1.0
    if "wind_speed_m_s" not in df.columns:
        df["wind_speed_m_s"] = 2.0

    if nasa_daily is not None and not nasa_daily.empty:
        nd = nasa_daily.copy()
        nd["day"] = pd.to_datetime(nd["date"]).dt.date
        daily = nd.set_index("day")
        keys = df["date"].dt.date
        df["relative_humidity"] = [
            float(daily.loc[k, "RH2M"]) / 100.0 if k in daily.index else 0.5 for k in keys
        ]
        df["rainfall_mm_day"] = [
            float(daily.loc[k, "PRECTOTCORR"]) if k in daily.index else 0.0 for k in keys
        ]
        if "WS2M" in daily.columns:
            df["wind_speed_m_s"] = [
                float(daily.loc[k, "WS2M"]) if k in daily.index else 2.0 for k in keys
            ]
    else:
        df["relative_humidity"] = 0.5
        df["rainfall_mm_day"] = 0.0

    df["aod_55"] = np.nan
    df["uv_index_proxy"] = (
        pd.to_numeric(df["poa_w_m2"], errors="coerce").fillna(0.0) / 1000.0
    ).clip(0.0, 2.0)
    return df
