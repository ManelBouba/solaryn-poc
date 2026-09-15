from __future__ import annotations
import pandas as pd
import numpy as np

def normalize(series: pd.Series, min_value: float | None = None, max_value: float | None = None) -> pd.Series:
    """Normalize values to 0-100. If min/max are not provided, use dataset min/max."""
    s = pd.to_numeric(series, errors="coerce").astype(float)
    lo = s.min() if min_value is None else min_value
    hi = s.max() if max_value is None else max_value
    if hi == lo:
        return pd.Series(np.full(len(s), 50.0), index=s.index)
    return ((s - lo) / (hi - lo) * 100).clip(0, 100)

def inverse_normalize(series: pd.Series, min_value: float | None = None, max_value: float | None = None) -> pd.Series:
    """Normalize values inversely to 0-100, where low raw values create high risk scores."""
    return 100 - normalize(series, min_value, max_value)

def compute_climate_fingerprint(df: pd.DataFrame) -> pd.DataFrame:
    """
    Equations:
    H = 0.35*Tavg_norm + 0.40*Tmax_norm + 0.25*GHI_norm
    S = 0.55*Dust_norm + 0.30*LowRain_norm + 0.15*Wind_norm
    M = 0.65*Humidity_norm + 0.35*Salinity_norm
    TC = 0.70*(Tmax-Tavg)_norm + 0.30*Wind_norm
    C = 0.40*H + 0.30*S + 0.20*M + 0.10*TC
    """
    out = df.copy()

    out["avg_temp_norm"] = normalize(out["avg_temp_c"], 5, 35)
    out["max_temp_norm"] = normalize(out["max_temp_c"], 25, 55)
    out["ghi_norm"] = normalize(out["ghi_kwh_m2_year"], 800, 2400)
    out["dust_norm"] = normalize(out["dust_soiling_risk"], 0, 3)
    out["low_rainfall_norm"] = inverse_normalize(out["rainfall_mm_year"], 0, 1000)
    out["wind_norm"] = normalize(out["wind_speed_m_s"], 2, 7)
    out["humidity_norm"] = normalize(out["humidity_pct"], 20, 90)
    out["salinity_norm"] = normalize(out["salinity_risk"], 0, 2)
    out["thermal_range_norm"] = normalize(out["max_temp_c"] - out["avg_temp_c"], 5, 30)

    out["heat_stress_index"] = (
        0.35*out["avg_temp_norm"] + 0.40*out["max_temp_norm"] + 0.25*out["ghi_norm"]
    ).round(2)

    out["soiling_stress_index"] = (
        0.65*out["dust_norm"] + 0.35*out["low_rainfall_norm"]
    ).round(2)

    out["moisture_corrosion_index"] = (
        0.65*out["humidity_norm"] + 0.35*out["salinity_norm"]
    ).round(2)

    out["thermal_cycling_proxy"] = (
        out["thermal_range_norm"]
    ).round(2)

    out["climate_severity_score"] = (
        0.40*out["heat_stress_index"] +
        0.30*out["soiling_stress_index"] +
        0.20*out["moisture_corrosion_index"] +
        0.10*out["thermal_cycling_proxy"]
    ).round(2)

    out["climate_fingerprint_scope"] = "descriptive_only_not_recommendation_physics"
    return out
