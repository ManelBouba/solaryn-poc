from __future__ import annotations

import numpy as np
import pandas as pd


def compute_stress_exposures(hourly: pd.DataFrame) -> dict:
    """Compute transparent environmental exposure metrics.

    These are *exposure descriptors*, not annual degradation penalties or failure
    probabilities. Conversion from exposure to degradation requires calibrated
    module/BOM-specific empirical models that are not yet part of this PoC.
    """
    if hourly.empty:
        raise ValueError("Hourly module simulation is empty.")

    t = pd.to_numeric(hourly["module_cell_temperature_c"], errors="coerce")
    rh_pct = (
        pd.to_numeric(hourly["relative_humidity_pct"], errors="coerce")
        if "relative_humidity_pct" in hourly
        else pd.to_numeric(hourly["relative_humidity"], errors="coerce") * 100.0
    )
    poa = pd.to_numeric(hourly["poa_w_m2"], errors="coerce").fillna(0.0)
    uv = pd.to_numeric(hourly.get("uv_index_proxy", 0.0), errors="coerce").fillna(0.0)
    daylight = poa > 20.0

    if "time_utc" in hourly:
        idx = pd.DatetimeIndex(pd.to_datetime(hourly["time_utc"], utc=True))
    elif "date" in hourly:
        idx = pd.DatetimeIndex(pd.to_datetime(hourly["date"]))
    else:
        idx = pd.date_range("2000-01-01", periods=len(hourly), freq="h")

    t_series = pd.Series(t.to_numpy(), index=idx)
    daily_range = t_series.resample("D").max() - t_series.resample("D").min()

    # A dimensionless exposure index for comparison only. Thresholds are explicit
    # and have no hidden conversion to %/year degradation.
    hot_component = ((t - 25.0).clip(lower=0.0) / 40.0)
    wet_component = ((rh_pct - 60.0).clip(lower=0.0) / 40.0)
    damp_heat_exposure = float((hot_component * wet_component).fillna(0.0).sum())

    return {
        "hot_cell_hours_gt_55c": int(((t > 55.0) & daylight).sum()),
        "hot_cell_hours_gt_65c": int(((t > 65.0) & daylight).sum()),
        "hot_humid_hours_rh85_t40": int(((rh_pct >= 85.0) & (t >= 40.0)).sum()),
        "mean_daily_cell_temp_range_c": float(daily_range.mean()),
        "days_cell_temp_range_gt_30c": int((daily_range > 30.0).sum()),
        "uv_proxy_dose": float(uv.sum()),
        "damp_heat_exposure_proxy": damp_heat_exposure,
        "calibration_status": "exposure_only_not_degradation_rate",
    }
