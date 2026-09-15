from __future__ import annotations

from datetime import datetime
from typing import Iterable

import numpy as np
import pandas as pd
import requests

NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_POWER_HOURLY_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

# Daily parameters are kept for backwards compatibility with older SOLARYN code.
NASA_POWER_DAILY_CORE_PARAMETERS = [
    "ALLSKY_SFC_SW_DWN",
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "RH2M",
    "WS2M",
    "PRECTOTCORR",
    "PS",  # surface pressure; used for pressure-adjusted air mass when available
]
NASA_POWER_OPTIONAL_PARAMETERS = ["AOD_55"]

# The primary workflow uses true hourly POWER data. The first three fields are GHI, DNI and DHI.
# POWER's hourly endpoint returns hourly-average irradiance values suitable for direct
# time-series modelling. Wind at 10 m is requested because the Sandia temperature model
# is parameterized for 10 m wind speed.
NASA_POWER_HOURLY_CORE_PARAMETERS = [
    "ALLSKY_SFC_SW_DWN",   # GHI
    "ALLSKY_SFC_SW_DNI",   # DNI
    "ALLSKY_SFC_SW_DIFF",  # DHI
    "T2M",
    "RH2M",
    "WS10M",
    "PRECTOTCORR",
    "PS",  # surface pressure; used for pressure-adjusted air mass / spectral model
]

# If a POWER deployment rejects one of the direct/diffuse aliases, SOLARYN still obtains
# true hourly GHI + meteorology and lets pvlib derive DNI/DHI from hourly GHI.
NASA_POWER_HOURLY_FALLBACK_PARAMETERS = [
    "ALLSKY_SFC_SW_DWN",
    "T2M",
    "RH2M",
    "WS10M",
    "PRECTOTCORR",
    "PS",
]


def _format_date(value: str) -> str:
    """Accept YYYY-MM-DD or YYYYMMDD and return YYYYMMDD."""
    v = str(value).strip()
    if "-" in v:
        return datetime.strptime(v, "%Y-%m-%d").strftime("%Y%m%d")
    datetime.strptime(v, "%Y%m%d")
    return v


def _clean_power_value(value):
    """Convert NASA POWER numeric values and common fill values to floats/NaN."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    if x <= -900.0:
        return np.nan
    return x


def _parse_power_daily_json(payload: dict) -> pd.DataFrame:
    params = payload.get("properties", {}).get("parameter", {})
    if not params:
        raise ValueError("NASA POWER response does not contain properties.parameter data.")

    rows = []
    all_dates = sorted({date for values in params.values() for date in values.keys()})
    for date_key in all_dates:
        row = {"date": pd.to_datetime(date_key, format="%Y%m%d")}
        for name, values in params.items():
            row[name] = _clean_power_value(values.get(date_key))
        rows.append(row)

    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _parse_power_hourly_json(payload: dict) -> pd.DataFrame:
    """Parse NASA POWER hourly JSON keys (YYYYMMDDHH) into a UTC time series."""
    params = payload.get("properties", {}).get("parameter", {})
    if not params:
        raise ValueError("NASA POWER hourly response does not contain properties.parameter data.")

    all_times = sorted({key for values in params.values() for key in values.keys()})
    rows = []
    for time_key in all_times:
        # Hourly requests in SOLARYN explicitly ask POWER for UTC.
        ts = pd.to_datetime(time_key, format="%Y%m%d%H", utc=True)
        row = {"time_utc": ts}
        for name, values in params.items():
            row[name] = _clean_power_value(values.get(time_key))
        rows.append(row)

    return pd.DataFrame(rows).sort_values("time_utc").reset_index(drop=True)


def fetch_nasa_power_hourly_dataframe(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    parameters: Iterable[str] | None = None,
    time_standard: str = "UTC",
) -> pd.DataFrame:
    """
    Download true hourly solar + meteorological data from NASA POWER.

    The primary request asks POWER for hourly GHI, DNI, DHI, temperature, relative
    humidity, 10 m wind speed and precipitation. If the endpoint rejects the direct/
    diffuse aliases, SOLARYN retries with true hourly GHI + meteorology; pvlib then
    derives DNI/DHI from hourly GHI instead of reconstructing an hourly profile from
    daily totals.
    """
    parameters_list = list(parameters or NASA_POWER_HOURLY_CORE_PARAMETERS)
    query = {
        "parameters": ",".join(parameters_list),
        "community": "RE",
        "longitude": float(longitude),
        "latitude": float(latitude),
        "start": _format_date(start),
        "end": _format_date(end),
        "format": "JSON",
        "time-standard": str(time_standard).upper(),
    }

    response = requests.get(NASA_POWER_HOURLY_URL, params=query, timeout=120)
    used_fallback = False
    if response.status_code >= 400 and parameters is None:
        query["parameters"] = ",".join(NASA_POWER_HOURLY_FALLBACK_PARAMETERS)
        response = requests.get(NASA_POWER_HOURLY_URL, params=query, timeout=120)
        used_fallback = True

    response.raise_for_status()
    payload = response.json()
    df = _parse_power_hourly_json(payload)
    df.attrs["raw_provider_json"] = payload
    df.attrs["request_parameters"] = dict(query)
    from datetime import datetime, timezone
    df.attrs["retrieved_at"] = datetime.now(timezone.utc).isoformat()

    for col in NASA_POWER_HOURLY_CORE_PARAMETERS:
        if col not in df.columns:
            df[col] = np.nan

    df.attrs["nasa_power_endpoint"] = NASA_POWER_HOURLY_URL
    df.attrs["time_standard"] = str(time_standard).upper()
    df.attrs["direct_diffuse_fallback_required"] = bool(
        used_fallback
        or df["ALLSKY_SFC_SW_DNI"].isna().all()
        or df["ALLSKY_SFC_SW_DIFF"].isna().all()
    )
    return df


def nasa_hourly_to_site_summary(
    nasa_hourly: pd.DataFrame,
    latitude: float,
    longitude: float,
    project_name: str = "NASA POWER selected point",
    system_size_mw: float = 1.0,
    site_type: str = "utility",
    budget_level: str = "medium",
    require_full_year: bool = True,
    min_reference_days: int = 330,
    min_hour_coverage: float = 0.95,
) -> pd.DataFrame:
    """Aggregate one or more near-complete hourly POWER years correctly.

    Multi-year runs return *mean annual* resource totals rather than the sum across
    all requested years. Each included calendar year must independently pass the
    coverage gate when ``require_full_year=True``. This avoids both partial-year
    annualization errors and the previous single-year-only limitation.
    """
    df = nasa_hourly.copy()
    if df.empty:
        raise ValueError("NASA POWER hourly dataframe is empty.")
    if "time_utc" not in df.columns:
        raise ValueError("NASA POWER hourly dataframe must contain time_utc.")

    times = pd.DatetimeIndex(pd.to_datetime(df["time_utc"], utc=True))
    years = sorted(pd.Index(times.year).unique().tolist())
    if not years:
        raise ValueError("NASA POWER hourly dataframe contains no valid timestamps.")

    coverage_rows = []
    for year in years:
        mask = times.year == int(year)
        ty = times[mask]
        unique_days = pd.Index(ty.floor("D").unique())
        coverage_days = int(len(unique_days))
        expected_hours = 8784 if pd.Timestamp(year=int(year), month=12, day=31).is_leap_year else 8760
        hour_coverage = min(1.0, float(len(ty)) / float(expected_hours))
        full = coverage_days >= int(min_reference_days) and hour_coverage >= float(min_hour_coverage)
        coverage_rows.append((int(year), coverage_days, hour_coverage, full))

    if require_full_year:
        failed = [r for r in coverage_rows if not r[3]]
        if failed:
            detail = "; ".join(f"{y}: {d} days/{h:.1%} hours" for y, d, h, _ in failed)
            raise ValueError(
                "SOLARYN annual/lifetime analysis requires a near-complete reference year for every selected resource year. "
                f"Insufficient coverage: {detail}."
            )

    def col(name: str) -> pd.Series:
        if name not in df.columns:
            return pd.Series(np.nan, index=df.index, dtype=float)
        return pd.to_numeric(df[name], errors="coerce")

    ghi = col("ALLSKY_SFC_SW_DWN").clip(lower=0)
    dni = col("ALLSKY_SFC_SW_DNI").clip(lower=0)
    temp = col("T2M")
    humidity = col("RH2M")
    wind = col("WS10M")
    rain = col("PRECTOTCORR").clip(lower=0)
    pressure = col("PS")

    work = pd.DataFrame({
        "time": times,
        "ghi": ghi.to_numpy(),
        "dni": dni.to_numpy(),
        "rain": rain.to_numpy(),
    })
    work["year"] = work["time"].dt.year
    annual_ghi = work.groupby("year")["ghi"].sum(min_count=1) / 1000.0
    annual_dni = work.groupby("year")["dni"].sum(min_count=1) / 1000.0
    annual_rain = work.groupby("year")["rain"].sum(min_count=1)

    ghi_annual = float(annual_ghi.mean()) if len(annual_ghi) else np.nan
    dni_annual = float(annual_dni.mean()) if dni.notna().any() and len(annual_dni) else np.nan
    rainfall_annual = float(annual_rain.mean()) if len(annual_rain) else np.nan

    rain_daily = pd.Series(rain.fillna(0).to_numpy(), index=times).resample("D").sum()
    dry_day_fraction = float((rain_daily < 1.0).mean()) if len(rain_daily) else 0.0
    dust_proxy = float(np.clip(3.0 * dry_day_fraction, 0.0, 3.0))

    min_days_observed = min(r[1] for r in coverage_rows)
    min_hour_coverage_observed = min(r[2] for r in coverage_rows)
    all_full = all(r[3] for r in coverage_rows)

    return pd.DataFrame([{
        "site_id": "NASA_SELECTED_POINT",
        "project_name": project_name,
        "country": "NASA POWER",
        "region": f"lat={latitude:.4f}, lon={longitude:.4f}",
        "latitude": float(latitude),
        "longitude": float(longitude),
        "site_type": site_type,
        "system_size_mw": float(system_size_mw),
        "avg_temp_c": float(temp.mean()),
        "max_temp_c": float(temp.max()),
        "ghi_kwh_m2_year": ghi_annual if all_full else np.nan,
        "dni_kwh_m2_year": dni_annual if all_full else np.nan,
        "humidity_pct": float(humidity.mean()),
        "rainfall_mm_year": rainfall_annual if all_full else np.nan,
        "wind_speed_m_s": float(wind.mean()),
        "pressure_power_units_mean": float(pressure.mean()) if pressure.notna().any() else np.nan,
        "dust_soiling_risk": dust_proxy,
        "elevation_m": 0.0,
        "salinity_risk": 0,
        "climate_zone": "from_nasa_power_hourly",
        "budget_level": budget_level,
        "nasa_hour_count": int(len(df)),
        "resource_year_count": int(len(years)),
        "resource_year_start": int(min(years)),
        "resource_year_end": int(max(years)),
        "weather_coverage_days": int(min_days_observed),
        "hour_coverage_fraction": round(float(min_hour_coverage_observed), 4),
        "is_full_reference_year": bool(all_full),
        "resource_aggregation": "mean_annual_across_complete_years",
    }])


# -----------------------------------------------------------------------------
# BACKWARDS-COMPATIBLE DAILY FUNCTIONS
# -----------------------------------------------------------------------------

def fetch_nasa_power_daily_dataframe(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    parameters: Iterable[str] | None = None,
    include_optional_aod: bool = True,
) -> pd.DataFrame:
    """Legacy daily downloader retained for compatibility; not used by the primary app."""
    params_list = list(parameters or NASA_POWER_DAILY_CORE_PARAMETERS)
    if include_optional_aod:
        params_list = params_list + [p for p in NASA_POWER_OPTIONAL_PARAMETERS if p not in params_list]

    query = {
        "parameters": ",".join(params_list),
        "community": "RE",
        "longitude": float(longitude),
        "latitude": float(latitude),
        "start": _format_date(start),
        "end": _format_date(end),
        "format": "JSON",
        "time-standard": "LST",
    }

    response = requests.get(NASA_POWER_DAILY_URL, params=query, timeout=90)
    if response.status_code >= 400 and include_optional_aod:
        query["parameters"] = ",".join(NASA_POWER_DAILY_CORE_PARAMETERS)
        response = requests.get(NASA_POWER_DAILY_URL, params=query, timeout=90)

    response.raise_for_status()
    df = _parse_power_daily_json(response.json())
    for col in NASA_POWER_DAILY_CORE_PARAMETERS + NASA_POWER_OPTIONAL_PARAMETERS:
        if col not in df.columns:
            df[col] = np.nan
    return df


def nasa_daily_to_site_summary(
    nasa_daily: pd.DataFrame,
    latitude: float,
    longitude: float,
    project_name: str = "NASA POWER selected point",
    system_size_mw: float = 1.0,
    site_type: str = "utility",
    budget_level: str = "medium",
) -> pd.DataFrame:
    """Legacy daily-to-site summary retained for compatibility."""
    df = nasa_daily.copy()
    rainfall_year = float(pd.to_numeric(df["PRECTOTCORR"], errors="coerce").fillna(0).sum())
    ghi_year = float(pd.to_numeric(df["ALLSKY_SFC_SW_DWN"], errors="coerce").fillna(0).sum())
    avg_temp = float(pd.to_numeric(df["T2M"], errors="coerce").mean())
    max_temp = float(pd.to_numeric(df["T2M_MAX"], errors="coerce").max())
    humidity = float(pd.to_numeric(df["RH2M"], errors="coerce").mean())
    wind = float(pd.to_numeric(df["WS2M"], errors="coerce").mean())

    aod = pd.to_numeric(df.get("AOD_55", pd.Series(dtype=float)), errors="coerce")
    if aod.notna().any():
        dust_proxy = float(np.clip(aod.mean() / 0.6 * 3.0, 0, 3))
    else:
        dry_days = int((pd.to_numeric(df["PRECTOTCORR"], errors="coerce").fillna(0) < 1.0).sum())
        dust_proxy = min(3.0, dry_days / 365.0 * 3.0)

    return pd.DataFrame([{
        "site_id": "NASA_SELECTED_POINT",
        "project_name": project_name,
        "country": "NASA POWER",
        "region": f"lat={latitude:.4f}, lon={longitude:.4f}",
        "latitude": float(latitude),
        "longitude": float(longitude),
        "site_type": site_type,
        "system_size_mw": float(system_size_mw),
        "avg_temp_c": avg_temp,
        "max_temp_c": max_temp,
        "ghi_kwh_m2_year": ghi_year,
        "dni_kwh_m2_year": ghi_year * 0.85,
        "humidity_pct": humidity,
        "rainfall_mm_year": rainfall_year,
        "wind_speed_m_s": wind,
        "dust_soiling_risk": dust_proxy,
        "elevation_m": 0.0,
        "salinity_risk": 0,
        "climate_zone": "from_nasa_power_daily_legacy",
        "budget_level": budget_level,
    }])


def fetch_pvgis_pvcalc(lat: float, lon: float, peakpower_kw: float = 1.0, loss_pct: float = 14.0) -> dict:
    """Optional PVGIS endpoint for future independent cross-checking of annual PV energy."""
    url = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
    params = {
        "lat": lat,
        "lon": lon,
        "peakpower": peakpower_kw,
        "loss": loss_pct,
        "outputformat": "json",
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()

# -----------------------------------------------------------------------------
# PVGIS HOURLY CROSS-CHECK / ALTERNATIVE IRRADIANCE SOURCE
# -----------------------------------------------------------------------------
PVGIS_SERIES_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"


def pvlib_azimuth_to_pvgis_aspect(azimuth_deg: float) -> float:
    """Convert pvlib compass azimuth to the PVGIS ``aspect`` convention.

    pvlib uses 0=north, 90=east, 180=south, 270=west. PVGIS uses
    0=south, -90=east, 90=west and +/-180=north.
    """
    azimuth = float(azimuth_deg) % 360.0
    aspect = azimuth - 180.0
    if aspect > 180.0:
        aspect -= 360.0
    return aspect


def fetch_pvgis_hourly_dataframe(
    lat: float,
    lon: float,
    startyear: int,
    endyear: int,
    angle: float | None = None,
    aspect: float = 0.0,
) -> pd.DataFrame:
    """Fetch real hourly in-plane irradiance and air temperature from PVGIS seriescalc."""
    params = {
        "lat": float(lat),
        "lon": float(lon),
        "startyear": int(startyear),
        "endyear": int(endyear),
        "outputformat": "json",
        "components": 1,
        "usehorizon": 1,
        "aspect": float(aspect),
    }
    if angle is not None:
        params["angle"] = float(angle)

    response = requests.get(PVGIS_SERIES_URL, params=params, timeout=120)
    response.raise_for_status()
    hourly = response.json().get("outputs", {}).get("hourly", [])
    if not hourly:
        raise ValueError("PVGIS returned no hourly rows.")

    df = pd.DataFrame(hourly)
    from datetime import datetime, timezone
    df.attrs.update(raw_provider_json=response.json(), request_parameters=params, retrieved_at=datetime.now(timezone.utc).isoformat(), time_standard="UTC", endpoint=PVGIS_SERIES_URL)
    df["date"] = pd.to_datetime(df["time"], format="%Y%m%d:%H%M")
    rename = {
        "G(i)": "poa_w_m2",
        "Gb(i)": "beam_poa_w_m2",
        "Gd(i)": "diffuse_poa_w_m2",
        "Gr(i)": "reflected_poa_w_m2",
        "T2m": "temp_air_c",
        "WS10m": "wind_speed_m_s",
    }
    df = df.rename(columns=rename)
    if "poa_w_m2" not in df.columns:
        parts = [
            c for c in ["beam_poa_w_m2", "diffuse_poa_w_m2", "reflected_poa_w_m2"]
            if c in df.columns
        ]
        if not parts:
            raise ValueError("PVGIS response did not contain usable in-plane irradiance fields.")
        df["poa_w_m2"] = df[parts].sum(axis=1)
    return df
