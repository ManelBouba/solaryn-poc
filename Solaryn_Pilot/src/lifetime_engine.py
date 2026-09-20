from __future__ import annotations

import math
import numpy as np
import pandas as pd
from src.input_validation import horizon_years


def common_degradation_curve(
    annual_degradation_pct_year: float = 0.50,
    years: int = 25,
) -> pd.DataFrame:
    """Common multiplicative degradation scenario applied identically to all candidates.

    The curve is a declared project sensitivity, not a technology-specific lifetime
    prediction. Product/BOM-specific lifetime differentiation must come from field or
    calibrated reliability evidence rather than a family-wide assumed rate.
    """
    y = horizon_years(years)
    d_pct = float(annual_degradation_pct_year)
    if y < 1:
        raise ValueError("years must be >= 1")
    if not math.isfinite(d_pct) or not (0.0 <= d_pct < 100.0):
        raise ValueError("annual_degradation_pct_year must be finite and in [0, 100).")

    d = d_pct / 100.0
    rows = []
    start_ret = 1.0
    for year in range(1, y + 1):
        end_ret = start_ret * (1.0 - d)
        # The average-of-year approximation is consistent with an energy quantity
        # accumulated continuously over the year while degradation progresses.
        avg_ret = 0.5 * (start_ret + end_ret)
        rows.append(
            {
                "year": year,
                "start_of_year_retention_pct": 100.0 * start_ret,
                "end_of_year_retention_pct": 100.0 * end_ret,
                "annual_energy_retention_scenario_pct": 100.0 * avg_ret,
            }
        )
        start_ret = end_ret
    return pd.DataFrame(rows)


def common_linear_degradation_curve(
    annual_degradation_pct_year: float = 0.50,
    years: int = 25,
) -> pd.DataFrame:
    """Backward-compatible name for the common multiplicative project scenario."""
    return common_degradation_curve(annual_degradation_pct_year, years)


def warranty_retention_curve(
    first_year_retention_pct: float,
    annual_degradation_pct_year: float,
    years: int = 25,
) -> pd.DataFrame:
    """Translate a manufacturer's linear power-warranty wording into a sensitivity.

    This is not an energy warranty and not a field-degradation prediction. It is kept
    separate from the primary common project degradation scenario.
    """
    y = horizon_years(years)
    if y < 1:
        raise ValueError("years must be >= 1")
    r1 = float(first_year_retention_pct)
    d = float(annual_degradation_pct_year)
    if not math.isfinite(r1) or not (0 < r1 <= 100):
        raise ValueError("first_year_retention_pct must be finite and in (0, 100].")
    if not math.isfinite(d) or d < 0:
        raise ValueError("annual_degradation_pct_year must be finite and non-negative.")

    rows = []
    start_ret = 100.0
    for year in range(1, y + 1):
        end_ret = max(0.0, r1 - d * (year - 1))
        avg_ret = 0.5 * (start_ret + end_ret)
        rows.append(
            {
                "year": year,
                "start_of_year_retention_pct": start_ret,
                "end_of_year_warranty_retention_pct": end_ret,
                "annual_energy_retention_scenario_pct": avg_ret,
            }
        )
        start_ret = end_ret
    return pd.DataFrame(rows)


def lifetime_energy_common_scenario(
    new_module_annual_energy_kwh_kwp: float,
    annual_degradation_pct_year: float = 0.50,
    years: int = 25,
) -> dict:
    annual = float(new_module_annual_energy_kwh_kwp)
    if not math.isfinite(annual) or annual < 0:
        raise ValueError("new_module_annual_energy_kwh_kwp must be finite and non-negative.")
    curve = common_degradation_curve(annual_degradation_pct_year, years)
    curve["annual_specific_energy_kwh_kwp"] = annual * curve["annual_energy_retention_scenario_pct"] / 100.0
    curve["cumulative_specific_energy_kwh_kwp"] = curve["annual_specific_energy_kwh_kwp"].cumsum()
    end_ret = float(curve.iloc[-1]["end_of_year_retention_pct"])
    return {
        "curve": curve,
        "lifetime_energy_common_degradation_scenario_kwh_kwp": float(curve["annual_specific_energy_kwh_kwp"].sum(min_count=1)),
        "final_year_common_scenario_end_retention_pct": end_ret,
        # Kept for callers that expect the historical field name.
        "year_25_common_scenario_end_retention_pct": end_ret,
        "basis": "common_multiplicative_project_degradation_sensitivity_same_for_all_candidates_not_field_prediction",
    }


def lifetime_energy_from_warranty_scenario(
    new_module_annual_energy_kwh_kwp: float,
    first_year_retention_pct: float,
    annual_degradation_pct_year: float,
    years: int = 25,
) -> dict:
    annual = float(new_module_annual_energy_kwh_kwp)
    if not math.isfinite(annual) or annual < 0:
        raise ValueError("new_module_annual_energy_kwh_kwp must be finite and non-negative.")
    curve = warranty_retention_curve(first_year_retention_pct, annual_degradation_pct_year, years)
    curve["annual_specific_energy_kwh_kwp"] = annual * curve["annual_energy_retention_scenario_pct"] / 100.0
    curve["cumulative_specific_energy_kwh_kwp"] = curve["annual_specific_energy_kwh_kwp"].cumsum()
    end_ret = float(curve.iloc[-1]["end_of_year_warranty_retention_pct"])
    return {
        "curve": curve,
        "lifetime_energy_warranty_scenario_kwh_kwp": float(curve["annual_specific_energy_kwh_kwp"].sum(min_count=1)),
        "final_year_warranty_retention_pct": end_ret,
        "end_of_year_25_warranty_retention_pct": end_ret,
        "basis": "warranty_derived_linear_power_retention_scenario_not_energy_guarantee_or_field_prediction",
    }




def degradation_parameters_for_candidate(
    module: pd.Series | dict,
    *,
    common_mean_pct_year: float = 0.50,
    common_sigma_pct_year: float = 0.20,
) -> dict:
    """Resolve degradation inputs without technology-family assumptions.

    A product-specific mean is used only when a field-validated/measured rate is
    explicitly recorded. Manufacturer warranty degradation remains a separate
    sensitivity and never becomes the primary lifetime mean. When no validated field
    evidence exists, all compared candidates share the same project degradation prior.
    """
    m = dict(module)
    common_mu = float(common_mean_pct_year)
    common_sd = float(common_sigma_pct_year)
    if not math.isfinite(common_mu) or common_mu < 0:
        raise ValueError("common_mean_pct_year must be finite and non-negative.")
    if not math.isfinite(common_sd) or common_sd < 0:
        raise ValueError("common_sigma_pct_year must be finite and non-negative.")

    status = str(m.get("degradation_evidence_status", "")).strip().lower()
    validated = status in {"field_validated", "validated_field", "measured_field", "independent_field"}
    field_mu = pd.to_numeric(pd.Series([m.get("field_validated_degradation_pct_year")]), errors="coerce").iloc[0]
    field_sd = pd.to_numeric(pd.Series([m.get("field_validated_degradation_sigma_pct_year")]), errors="coerce").iloc[0]

    if validated and pd.notna(field_mu) and math.isfinite(float(field_mu)) and float(field_mu) >= 0:
        sigma = float(field_sd) if pd.notna(field_sd) and math.isfinite(float(field_sd)) and float(field_sd) >= 0 else common_sd
        return {
            "mean_pct_year": float(field_mu),
            "sigma_pct_year": sigma,
            "basis": "product_specific_field_evidence",
            "evidence_status": status,
        }

    return {
        "mean_pct_year": common_mu,
        "sigma_pct_year": common_sd,
        "basis": "common_project_prior_shared_across_candidates",
        "evidence_status": status or "not_provided",
    }

def lifetime_energy_distribution(
    annual_yield_kwh_kwp: float,
    mean_degradation_pct_year: float = 0.50,
    degradation_sigma_pct_year: float = 0.20,
    annual_yield_sigma_pct: float = 3.0,
    years: int = 25,
    n: int = 5000,
    seed: int = 95,
) -> dict:
    """Screening distribution for lifetime energy without inventing family superiority.

    The degradation mean is a declared project scenario shared across candidates.
    Evidence quality may change ``degradation_sigma_pct_year`` at the caller, but not
    the mean. P90 is reported as the 10th percentile (90% exceedance).
    """
    annual=float(annual_yield_kwh_kwp); mu=float(mean_degradation_pct_year); sd=float(degradation_sigma_pct_year)
    if not math.isfinite(annual) or annual < 0: raise ValueError("annual_yield_kwh_kwp must be finite and non-negative")
    if not math.isfinite(mu) or not 0 <= mu < 20: raise ValueError("mean degradation must be in [0,20) %/yr")
    if not math.isfinite(sd) or sd < 0: raise ValueError("degradation sigma must be non-negative")
    if int(n) < 100: raise ValueError("n must be >=100")
    rng=np.random.default_rng(seed)
    # Truncated normal at physical non-negative degradation.
    d=np.maximum(rng.normal(mu, sd, int(n)), 0.0)/100.0
    cv=max(float(annual_yield_sigma_pct),0.0)/100.0
    if cv:
        sig=np.sqrt(np.log1p(cv*cv)); mult=rng.lognormal(-0.5*sig*sig, sig, int(n))
    else: mult=np.ones(int(n))
    first=annual*mult
    yrs=np.arange(int(years), dtype=float)
    life=(first[:,None] * np.power(1.0-d[:,None], yrs[None,:])).sum(axis=1)
    return {
        "p50_lifetime_kwh_kwp": float(np.percentile(life,50)),
        "p90_lifetime_kwh_kwp": float(np.percentile(life,10)),
        "mean_lifetime_kwh_kwp": float(life.mean()),
        "degradation_mean_pct_year": mu,
        "degradation_sigma_pct_year": sd,
        "annual_yield_sigma_pct": float(annual_yield_sigma_pct),
        "n_samples": int(n),
        "basis": "common degradation prior; evidence changes uncertainty width, not technology mean",
    }

def add_lifetime_metrics(
    results: pd.DataFrame,
    modules: pd.DataFrame,
    years: int = 25,
    common_degradation_pct_year: float = 0.50,
) -> pd.DataFrame:
    """Add neutral common-degradation and warranty-sensitivity lifetime metrics."""
    out = results.copy()
    lookup = modules.set_index("module_id")
    common_lifetime, common_end = [], []
    warranty_lifetime, warranty_end, warranty_bases = [], [], []

    for _, row in out.iterrows():
        annual = float(row["annual_yield_kwh_kwp"])
        if not math.isfinite(annual):
            common_lifetime.append(float("nan"))
            common_end.append(float("nan"))
            warranty_lifetime.append(float("nan"))
            warranty_end.append(float("nan"))
            warranty_bases.append("not_computed_missing_annual_energy")
            continue
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
        common_end.append(common["final_year_common_scenario_end_retention_pct"])
        warranty_lifetime.append(warranty["lifetime_energy_warranty_scenario_kwh_kwp"])
        warranty_end.append(warranty["final_year_warranty_retention_pct"])
        warranty_bases.append(warranty["basis"])

    out["lifetime_energy_common_degradation_scenario_kwh_kwp"] = common_lifetime
    out["year_25_common_scenario_end_retention_pct"] = common_end
    out["common_degradation_scenario_pct_year"] = float(common_degradation_pct_year)
    out["common_lifetime_scenario_basis"] = "same_project_multiplicative_degradation_sensitivity_for_all_candidates"
    out["lifetime_energy_warranty_scenario_kwh_kwp"] = warranty_lifetime
    out["year_25_warranty_end_retention_pct"] = warranty_end
    out["lifetime_scenario_basis"] = warranty_bases
    return out
