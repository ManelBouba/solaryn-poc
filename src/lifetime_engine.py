from __future__ import annotations

import pandas as pd


def common_linear_degradation_curve(
    annual_degradation_pct_year: float = 0.50,
    years: int = 25,
) -> pd.DataFrame:
    """Common project degradation sensitivity applied identically to all modules.

    This is deliberately not technology-specific. Until Solaryn has calibrated
    BOM/module-specific field-degradation models, a common scenario prevents warranty
    language or database defaults from manufacturing a technology winner.
    """
    y = int(years)
    d = float(annual_degradation_pct_year)
    if y < 1:
        raise ValueError("years must be >= 1")
    if d < 0:
        raise ValueError("annual_degradation_pct_year cannot be negative.")
    rows = []
    start_ret = 100.0
    for year in range(1, y + 1):
        end_ret = max(0.0, 100.0 - d * year)
        avg_ret = 0.5 * (start_ret + end_ret)
        rows.append({
            "year": year,
            "start_of_year_retention_pct": start_ret,
            "end_of_year_retention_pct": end_ret,
            "annual_energy_retention_scenario_pct": avg_ret,
        })
        start_ret = end_ret
    return pd.DataFrame(rows)


def warranty_retention_curve(
    first_year_retention_pct: float,
    annual_degradation_pct_year: float,
    years: int = 25,
) -> pd.DataFrame:
    """Translate manufacturer power-warranty endpoints into a transparent sensitivity.

    This is NOT an energy warranty and NOT a field-degradation prediction.
    """
    y = int(years)
    if y < 1:
        raise ValueError("years must be >= 1")
    r1 = float(first_year_retention_pct)
    d = float(annual_degradation_pct_year)
    if not (0 < r1 <= 100):
        raise ValueError("first_year_retention_pct must be in (0, 100].")
    if d < 0:
        raise ValueError("annual_degradation_pct_year cannot be negative.")

    rows = []
    start_ret = 100.0
    for year in range(1, y + 1):
        end_ret = max(0.0, r1 - d * (year - 1))
        avg_ret = 0.5 * (start_ret + end_ret)
        rows.append({
            "year": year,
            "start_of_year_retention_pct": start_ret,
            "end_of_year_warranty_retention_pct": end_ret,
            "annual_energy_retention_scenario_pct": avg_ret,
        })
        start_ret = end_ret
    return pd.DataFrame(rows)


def _lifetime_from_curve(new_module_annual_energy_kwh_kwp: float, curve: pd.DataFrame) -> float:
    return float(
        (
            float(new_module_annual_energy_kwh_kwp)
            * curve["annual_energy_retention_scenario_pct"] / 100.0
        ).sum()
    )


def lifetime_energy_common_scenario(
    new_module_annual_energy_kwh_kwp: float,
    annual_degradation_pct_year: float = 0.50,
    years: int = 25,
) -> dict:
    curve = common_linear_degradation_curve(annual_degradation_pct_year, years)
    curve["annual_specific_energy_kwh_kwp"] = (
        float(new_module_annual_energy_kwh_kwp)
        * curve["annual_energy_retention_scenario_pct"] / 100.0
    )
    curve["cumulative_specific_energy_kwh_kwp"] = curve["annual_specific_energy_kwh_kwp"].cumsum()
    return {
        "curve": curve,
        "lifetime_energy_common_degradation_scenario_kwh_kwp": float(curve["annual_specific_energy_kwh_kwp"].sum(min_count=1)),
        "year_25_common_scenario_end_retention_pct": float(curve.iloc[-1]["end_of_year_retention_pct"]),
        "basis": "common_linear_project_degradation_sensitivity_same_for_all_candidates_not_field_prediction",
    }


def lifetime_energy_from_warranty_scenario(
    new_module_annual_energy_kwh_kwp: float,
    first_year_retention_pct: float,
    annual_degradation_pct_year: float,
    years: int = 25,
) -> dict:
    curve = warranty_retention_curve(first_year_retention_pct, annual_degradation_pct_year, years)
    curve["annual_specific_energy_kwh_kwp"] = (
        float(new_module_annual_energy_kwh_kwp)
        * curve["annual_energy_retention_scenario_pct"] / 100.0
    )
    curve["cumulative_specific_energy_kwh_kwp"] = curve["annual_specific_energy_kwh_kwp"].cumsum()
    return {
        "curve": curve,
        "lifetime_energy_warranty_scenario_kwh_kwp": float(curve["annual_specific_energy_kwh_kwp"].sum(min_count=1)),
        "end_of_year_25_warranty_retention_pct": float(curve.iloc[-1]["end_of_year_warranty_retention_pct"]),
        "basis": "warranty_derived_linear_power_retention_scenario_not_energy_guarantee_or_field_prediction",
    }


def add_lifetime_metrics(
    results: pd.DataFrame,
    modules: pd.DataFrame,
    years: int = 25,
    common_degradation_pct_year: float = 0.50,
) -> pd.DataFrame:
    """Add both bias-controlled common and manufacturer-warranty lifetime sensitivities."""
    out = results.copy()
    lookup = modules.set_index("module_id")
    common_lifetime = []
    common_end = []
    warranty_lifetime = []
    warranty_end = []
    warranty_bases = []
    for _, row in out.iterrows():
        annual = float(row["annual_yield_kwh_kwp"])
        common = lifetime_energy_common_scenario(
            annual,
            annual_degradation_pct_year=common_degradation_pct_year,
            years=years,
        )
        m = lookup.loc[row["module_id"]]
        warranty = lifetime_energy_from_warranty_scenario(
            annual,
            m["first_year_retention_pct"],
            m["annual_warranty_degradation_pct_year"],
            years,
        )
        common_lifetime.append(common["lifetime_energy_common_degradation_scenario_kwh_kwp"])
        common_end.append(common["year_25_common_scenario_end_retention_pct"])
        warranty_lifetime.append(warranty["lifetime_energy_warranty_scenario_kwh_kwp"])
        warranty_end.append(warranty["end_of_year_25_warranty_retention_pct"])
        warranty_bases.append(warranty["basis"])

    out["lifetime_energy_common_degradation_scenario_kwh_kwp"] = common_lifetime
    out["year_25_common_scenario_end_retention_pct"] = common_end
    out["common_degradation_scenario_pct_year"] = float(common_degradation_pct_year)
    out["common_lifetime_scenario_basis"] = "same_project_degradation_sensitivity_for_all_candidates"
    out["lifetime_energy_warranty_scenario_kwh_kwp"] = warranty_lifetime
    out["year_25_warranty_end_retention_pct"] = warranty_end
    out["lifetime_scenario_basis"] = warranty_bases
    return out
