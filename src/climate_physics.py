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
    """Run Solaryn's corrected commercial screening physics on the existing database.

    The Solaryn database is preserved. Commercial energy uses only parameters with a
    direct physical role in this compact model: hourly POA, cell temperature,
    technology Pmax temperature coefficient and (where supported) a pvlib spectral
    mismatch class. Soiling is a SITE loss common to all technologies. The database
    degradation value remains a lifetime scenario; Arrhenius/Peck remains a separate
    environmental stress diagnostic, not a field degradation prediction.
    """
    weather_df = weather.copy() if weather is not None else generate_representative_weather(site)
    coverage_days, hour_coverage, representative = _annual_coverage(weather_df)
    if not representative and (coverage_days < 330 or hour_coverage < 0.95):
        raise ValueError(
            f"Annual/lifetime analysis requires a near-complete reference year; received {coverage_days:.0f} days at {hour_coverage:.1%} coverage."
        )

    gamma = float(tech.get("temp_coefficient_pct_c", -0.35)) / 100.0
    database_degradation = max(float(tech.get("baseline_degradation_pct_year", 0.6)), 0.0)
    # The database degradation remains visible evidence, but the default EPC comparison
    # uses one project scenario for every technology unless offer-specific validated
    # degradation data are deliberately supplied later.
    forecast_degradation = max(float(site.get("degradation_scenario_pct_year", 0.50)), 0.0)
    assumed_soiling_loss_pct = _clip(float(site.get("soiling_loss_assumption_pct", 2.0)), 0.0, 30.0)
    salinity = _clip(float(site.get("salinity_risk", 0.0)), 0.0, 2.0)
    humidity_resilience = _clip(float(tech.get("humidity_resilience_score", 3.0)), 1.0, 5.0)

    # Common project-level soiling assumption. The site climate fingerprint still
    # describes dust/rain exposure, but annual energy does not infer an O&M cleaning
    # schedule from climate alone. The same assumption is applied to every technology.
    soiling_ratio_fixed = 1.0 - assumed_soiling_loss_pct / 100.0

    spectral_factor, spectral_note, spectral_applied = _spectral_factor_series(weather_df, tech)

    energy_ref25 = 0.0
    energy_clean = 0.0
    energy_soiled = 0.0
    energy_broadband_nospectral = 0.0
    weighted_t_cell=[]
    degradation_af_weighted=[]
    uv_dose=0.0

    params = technology_degradation_params(tech)
    ea=params["activation_energy_ev"]; n_hum=params["humidity_exponent"]
    for i, r in weather_df.iterrows():
        poa=max(float(r.get("poa_w_m2",0.0)),0.0)
        sf=float(spectral_factor.loc[i]) if i in spectral_factor.index else 1.0
        poa_effective=poa*sf
        if "temp_cell_c" in weather_df.columns and pd.notna(r.get("temp_cell_c",pd.NA)):
            t_cell=float(r.get("temp_cell_c"))
        else:
            t_cell=sandia_cell_temperature_c(poa,float(r.get("temp_air_c",25.0)),float(r.get("wind_speed_m_s",2.0)))
        weight=float(r.get("days_weight",1.0))
        energy_broadband_nospectral += pvwatts_dc_power_kw_per_kwp(poa,t_cell,gamma)*weight
        energy_ref25 += pvwatts_dc_power_kw_per_kwp(poa_effective*soiling_ratio_fixed,25.0,gamma)*weight
        energy_clean += pvwatts_dc_power_kw_per_kwp(poa_effective,t_cell,gamma)*weight
        energy_soiled += pvwatts_dc_power_kw_per_kwp(poa_effective*soiling_ratio_fixed,t_cell,gamma)*weight
        if poa > 50:
            n_weight=max(1,int(round(weight))); weighted_t_cell.extend([t_cell]*n_weight)
            af_t=arrhenius_acceleration(t_cell,ea)
            af_h=peck_humidity_acceleration(t_cell,float(r.get("relative_humidity",0.5)),ea,n_hum)
            degradation_af_weighted.append((0.65*af_t+0.35*af_h)*weight*poa)
            uv_dose += float(r.get("uv_index_proxy",0.0))*weight*poa/1000.0

    t_arr=np.array(weighted_t_cell) if weighted_t_cell else np.array([25.0])
    clean_yield=max(energy_clean,1e-9); ref25=max(energy_ref25,1e-9)
    soiling_loss_pct=max(0.0,(1.0-energy_soiled/clean_yield)*100.0)
    temp_effect_pct=(energy_soiled/ref25-1.0)*100.0
    temp_loss_pct=max(0.0,-temp_effect_pct)
    temp_gain_pct=max(0.0,temp_effect_pct)
    spectral_effect_pct=(energy_clean/max(energy_broadband_nospectral,1e-9)-1.0)*100.0

    weights=pd.to_numeric(weather_df.get("days_weight",pd.Series(1.0,index=weather_df.index)),errors="coerce").fillna(1.0)
    poa_weight_sum=float((pd.to_numeric(weather_df["poa_w_m2"],errors="coerce").fillna(0)*weights).sum()) if "poa_w_m2" in weather_df else 1.0
    degradation_af=sum(degradation_af_weighted)/max(poa_weight_sum,1e-9) if degradation_af_weighted else 1.0
    uv_factor=1.0+0.04*_clip(uv_dose/2500.0,0.0,2.0)
    salt_factor=1.0+0.10*salinity*(1.0-humidity_resilience/5.0)
    degradation_stress=max(float(degradation_af*uv_factor*salt_factor),0.01)

    return {
        "annual_yield_kwh_kwp": round(float(energy_soiled),2),
        "clean_annual_yield_kwh_kwp": round(float(clean_yield),2),
        "annual_soiling_loss_pct": round(float(soiling_loss_pct),2),
        "avg_cell_temperature_C": round(float(np.mean(t_arr)),2),
        "p95_cell_temperature_C": round(float(np.percentile(t_arr,95)),2),
        "temperature_effect_pct": round(float(temp_effect_pct),2),
        "temperature_loss_pct": round(float(temp_loss_pct),2),
        "temperature_gain_pct": round(float(temp_gain_pct),2),
        "spectral_effect_pct": round(float(spectral_effect_pct),2),
        "mean_spectral_factor": round(float(spectral_factor.mean()),4),
        "spectral_model_applied": bool(spectral_applied),
        "spectral_model_note": spectral_note,
        "degradation_acceleration_factor": round(float(degradation_af),3),
        "degradation_stress_factor": round(float(degradation_stress),3),
        "site_degradation_pct_year": round(float(forecast_degradation),3),
        "database_degradation_pct_year": round(float(database_degradation),3),
        "degradation_rate_basis": "common project scenario for fair technology comparison; database technology value displayed separately",
        "uv_dose_proxy": round(float(uv_dose),2),
        "weather_coverage_days": round(float(coverage_days),1),
        "hour_coverage_fraction": round(float(hour_coverage),4),
        "soiling_model_basis": "common project soiling-loss assumption; no technology-specific soiling advantage",
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
