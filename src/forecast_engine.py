from __future__ import annotations

import pandas as pd

from src.physics_model import site_adjusted_performance


def forecast_25_years(
    site: pd.Series,
    tech_row: pd.Series,
    degradation_pct_year: float | None = None,
    years: int = 25,
    weather: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Create a transparent lifetime-yield forecast from the same site physics used in ranking.

    When hourly weather is supplied, the year-1 yield and degradation basis come from
    that weather path rather than a separate representative-climate calculation.
    """
    perf = site_adjusted_performance(site, tech_row, weather=weather)
    dc_kw = float(site["system_size_mw"]) * 1000.0
    year1_yield = dc_kw * float(perf["annual_yield_kwh_kwp"])
    d = float(
        degradation_pct_year
        if degradation_pct_year is not None
        else perf["adjusted_degradation_pct_year"]
    ) / 100.0

    rows = []
    for year in range(1, int(years) + 1):
        annual_yield = year1_yield * ((1.0 - d) ** (year - 1))
        retained = 100.0 * ((1.0 - d) ** (year - 1))
        rows.append({
            "year": year,
            "annual_yield_kwh": round(annual_yield, 2),
            "retained_performance_pct": round(retained, 2),
            "cumulative_yield_kwh": None,
            "estimated_operating_efficiency_pct": perf["estimated_operating_efficiency_pct"],
            "cell_temperature_C": perf["cell_temperature_C"],
            "performance_ratio_model": perf["performance_ratio_model"],
        })

    df = pd.DataFrame(rows)
    df["cumulative_yield_kwh"] = df["annual_yield_kwh"].cumsum().round(2)
    return df
