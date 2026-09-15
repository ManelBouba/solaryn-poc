from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib


def default_fixed_tilt_geometry(latitude: float, tilt_deg: float | None = None, azimuth_deg: float | None = None) -> tuple[float, float]:
    """Return a simple equator-facing fixed-tilt geometry for the screening application."""
    tilt = min(max(abs(float(latitude)), 5.0), 35.0) if tilt_deg is None else float(tilt_deg)
    azimuth = (180.0 if float(latitude) >= 0 else 0.0) if azimuth_deg is None else float(azimuth_deg)
    return tilt, azimuth


def _series(df: pd.DataFrame, name: str, index: pd.DatetimeIndex) -> pd.Series:
    if name not in df.columns:
        return pd.Series(np.nan, index=index, dtype=float)
    return pd.Series(pd.to_numeric(df[name], errors="coerce").to_numpy(), index=index, dtype=float)


def _pressure_to_pa(power_pressure: pd.Series) -> tuple[pd.Series, str]:
    """Convert NASA POWER ``PS`` to Pa with sanity-checked unit handling.

    POWER's renewable-energy API serves surface pressure in kPa. The guarded
    hPa/Pa branches are retained only to fail safely on externally supplied tables
    or legacy exports. This fixes the previous ambiguous ``<2000`` magnitude rule,
    which could misread ~1000 hPa as 1000 kPa.
    """
    p = power_pressure.astype(float).copy()
    med = float(p.dropna().median()) if p.notna().any() else np.nan
    if not np.isfinite(med):
        return pd.Series(101325.0, index=p.index), "standard atmosphere fallback; NASA PS missing"
    if 20.0 <= med <= 120.0:
        return p * 1000.0, "NASA POWER PS in kPa -> Pa"
    if 200.0 <= med <= 1200.0:
        return p * 100.0, "pressure interpreted as hPa -> Pa (legacy/external guard)"
    if 20000.0 <= med <= 120000.0:
        return p, "pressure already in Pa (legacy/external guard)"
    raise ValueError(
        f"Surface-pressure magnitude is not physically interpretable (median={med:.3f}). "
        "Verify NASA POWER PS units before spectral/air-mass calculation."
    )


def nasa_hourly_to_pvlib_weather(
    nasa_hourly: pd.DataFrame,
    latitude: float,
    longitude: float,
    tilt_deg: float | None = None,
    azimuth_deg: float | None = None,
    albedo: float = 0.20,
) -> pd.DataFrame:
    """Convert true NASA POWER hourly data to a pvlib-ready weather table.

    GHI remains the observed/modelled hourly POWER input. Missing DNI/DHI are
    decomposed with pvlib Erbs. The table also carries precipitable water and
    pressure-adjusted air mass so supported technology families can receive a
    documented first-order spectral mismatch correction.
    """
    if nasa_hourly.empty:
        raise ValueError("NASA POWER hourly dataframe is empty.")
    if "time_utc" not in nasa_hourly.columns:
        raise ValueError("NASA POWER hourly dataframe must contain time_utc.")

    df = nasa_hourly.copy()
    times = pd.DatetimeIndex(pd.to_datetime(df["time_utc"], utc=True))
    order = np.argsort(times.asi8)
    if not np.array_equal(order, np.arange(len(times))):
        df = df.iloc[order].reset_index(drop=True)
        times = pd.DatetimeIndex(pd.to_datetime(df["time_utc"], utc=True))

    location = pvlib.location.Location(latitude=float(latitude), longitude=float(longitude), tz="UTC")
    solpos = location.get_solarposition(times)

    ghi = _series(df, "ALLSKY_SFC_SW_DWN", times).fillna(0).clip(lower=0)
    nasa_dni = _series(df, "ALLSKY_SFC_SW_DNI", times)
    nasa_dhi = _series(df, "ALLSKY_SFC_SW_DIFF", times)
    erbs = pvlib.irradiance.erbs(ghi, solpos["zenith"], times)
    dni = nasa_dni.where(nasa_dni.notna(), erbs["dni"]).fillna(0).clip(lower=0)
    dhi = nasa_dhi.where(nasa_dhi.notna(), erbs["dhi"]).fillna(0).clip(lower=0)
    dni_source = np.where(nasa_dni.notna(), "NASA POWER hourly", "pvlib Erbs from NASA hourly GHI")
    dhi_source = np.where(nasa_dhi.notna(), "NASA POWER hourly", "pvlib Erbs from NASA hourly GHI")

    tilt, azimuth = default_fixed_tilt_geometry(latitude, tilt_deg, azimuth_deg)

    # Physics correction: use an anisotropic diffuse transposition model rather than
    # isotropic sky diffuse. This matters when comparing climates with very different
    # diffuse fractions (e.g. Brussels vs arid sites). Perez-Driesse is available in
    # pvlib >=0.13 and requires extraterrestrial DNI and relative air mass.
    airmass_relative = location.get_airmass(solar_position=solpos)["airmass_relative"]
    dni_extra = pd.Series(pvlib.irradiance.get_extra_radiation(times), index=times, dtype=float)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt, surface_azimuth=azimuth,
        solar_zenith=solpos["apparent_zenith"], solar_azimuth=solpos["azimuth"],
        dni=dni, ghi=ghi, dhi=dhi, dni_extra=dni_extra, airmass=airmass_relative,
        albedo=float(albedo), model="perez-driesse",
    )

    # Common front-glass incidence-angle loss. This corrects absolute module DC
    # energy without manufacturing a technology-specific advantage. Exact module
    # IAM curves may replace this common glass model when an EPC supplies them.
    aoi_deg = pd.Series(
        pvlib.irradiance.aoi(
            surface_tilt=tilt, surface_azimuth=azimuth,
            solar_zenith=solpos["apparent_zenith"],
            solar_azimuth=solpos["azimuth"],
        ),
        index=times, dtype=float,
    )
    iam_direct = pd.Series(pvlib.iam.physical(aoi_deg), index=times, dtype=float).fillna(0.0).clip(lower=0.0, upper=1.05)
    iam_diffuse = pvlib.iam.marion_diffuse("physical", surface_tilt=tilt)
    iam_sky = float(iam_diffuse["sky"])
    iam_ground = float(iam_diffuse["ground"])
    poa_optical = (
        poa["poa_direct"].fillna(0).clip(lower=0) * iam_direct
        + poa["poa_sky_diffuse"].fillna(0).clip(lower=0) * iam_sky
        + poa["poa_ground_diffuse"].fillna(0).clip(lower=0) * iam_ground
    ).clip(lower=0.0)

    temp_air = _series(df, "T2M", times).interpolate(limit_direction="both")
    wind = _series(df, "WS10M", times).interpolate(limit_direction="both").clip(lower=0.1)
    rh = _series(df, "RH2M", times).interpolate(limit_direction="both").clip(lower=0, upper=100)
    rain_hour = _series(df, "PRECTOTCORR", times).fillna(0).clip(lower=0)

    temp_params = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_polymer"]
    temp_cell = pvlib.temperature.sapm_cell(
        poa_global=poa["poa_global"].fillna(0).clip(lower=0),
        temp_air=temp_air, wind_speed=wind, **temp_params,
    )

    pressure_pa, pressure_source = _pressure_to_pa(_series(df, "PS", times))
    airmass_absolute = pvlib.atmosphere.get_absolute_airmass(airmass_relative, pressure_pa)
    precipitable_water = pvlib.atmosphere.gueymard94_pw(temp_air, rh)

    daily_rain = rain_hour.resample("D").sum()
    day_keys = pd.DatetimeIndex(times.floor("D"))
    rainfall_mm_day = pd.Series([float(daily_rain.get(k, 0.0)) for k in day_keys], index=times)

    uv_proxy = (poa["poa_global"].fillna(0).clip(lower=0) / 1000.0) * (
        1.0 + 0.08 * np.maximum(0.0, 2.0 - airmass_relative.fillna(10.0))
    )

    n_years = max(int(pd.Index(times.year).nunique()), 1)
    annual_weight = 1.0 / float(n_years)
    weather = pd.DataFrame({
        "time_utc": times, "date": times.floor("D"), "month": times.month,
        "year": times.year, "day_of_year": times.dayofyear, "hour": times.hour,
        "days_weight": annual_weight, "resource_year_count": n_years,
        "ghi_w_m2": ghi.to_numpy(), "dni_w_m2": dni.to_numpy(), "dhi_w_m2": dhi.to_numpy(),
        "dni_source": dni_source, "dhi_source": dhi_source,
        "solar_zenith_deg": solpos["apparent_zenith"].to_numpy(),
        "solar_azimuth_deg": solpos["azimuth"].to_numpy(),
        "aoi_deg": aoi_deg.to_numpy(),
        "iam_direct": iam_direct.to_numpy(),
        "iam_sky": iam_sky,
        "iam_ground": iam_ground,
        "poa_optical_w_m2": pd.Series(poa_optical, index=times).to_numpy(),
        "air_mass": airmass_relative.to_numpy(),
        "airmass_absolute": pd.Series(airmass_absolute, index=times).to_numpy(),
        "precipitable_water_cm": pd.Series(precipitable_water, index=times).to_numpy(),
        "pressure_pa": pressure_pa.to_numpy(), "pressure_source": pressure_source,
        "surface_tilt_deg": tilt, "surface_azimuth_deg": azimuth,
        "poa_transposition_model": "perez-driesse",
        "poa_w_m2": poa["poa_global"].fillna(0).clip(lower=0).to_numpy(),
        "poa_direct_w_m2": poa["poa_direct"].fillna(0).clip(lower=0).to_numpy(),
        "poa_sky_diffuse_w_m2": poa["poa_sky_diffuse"].fillna(0).clip(lower=0).to_numpy(),
        "poa_ground_diffuse_w_m2": poa["poa_ground_diffuse"].fillna(0).clip(lower=0).to_numpy(),
        "temp_air_c": temp_air.to_numpy(), "temp_cell_c": pd.Series(temp_cell, index=times).to_numpy(),
        "temp_cell_is_measured": False, "temp_cell_source": "pvlib SAPM open-rack modeled cell temperature",
        "wind_speed_m_s": wind.to_numpy(), "relative_humidity": (rh / 100.0).to_numpy(),
        "relative_humidity_pct": rh.to_numpy(), "rainfall_mm_hour": rain_hour.to_numpy(),
        "rainfall_mm_day": rainfall_mm_day.to_numpy(), "aod_55": np.nan,
        "uv_index_proxy": pd.Series(uv_proxy, index=times).fillna(0).to_numpy(),
    })
    return weather.reset_index(drop=True)
