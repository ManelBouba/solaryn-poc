from __future__ import annotations

import math
import numpy as np
import pandas as pd
from src.input_validation import evidence_flag

from src.lifetime_engine import common_degradation_curve, warranty_retention_curve


def _validate_economic_inputs(energy_value: float, discount_rate_pct: float, years: int) -> None:
    if not math.isfinite(float(energy_value)) or float(energy_value) < 0:
        raise ValueError("energy value must be finite and non-negative.")
    if not math.isfinite(float(discount_rate_pct)) or float(discount_rate_pct) <= -100:
        raise ValueError("discount rate must be finite and greater than -100%.")
    if int(years) < 1:
        raise ValueError("years must be >= 1.")


def _npv_from_retention_curve(
    annual_yield_kwh_kwp: float,
    curve: pd.DataFrame,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
) -> float:
    _validate_economic_inputs(energy_value_usd_kwh, discount_rate_pct, int(curve["year"].max()))
    annual_yield = float(annual_yield_kwh_kwp)
    if not math.isfinite(annual_yield) or annual_yield < 0:
        raise ValueError("annual_yield_kwh_kwp must be finite and non-negative.")

    r = float(discount_rate_pct) / 100.0
    annual_per_w = annual_yield / 1000.0 * curve["annual_energy_retention_scenario_pct"].to_numpy() / 100.0
    discounts = np.power(1.0 + r, curve["year"].to_numpy(dtype=float))
    return float(np.sum(annual_per_w * float(energy_value_usd_kwh) / discounts))


def npv_energy_value_common_scenario_per_w(
    annual_yield_kwh_kwp: float,
    annual_degradation_pct_year: float,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
    years: int = 25,
) -> float:
    """Discounted energy value per installed DC watt under one common lifetime scenario."""
    curve = common_degradation_curve(annual_degradation_pct_year, years)
    return _npv_from_retention_curve(annual_yield_kwh_kwp, curve, energy_value_usd_kwh, discount_rate_pct)


def npv_energy_value_per_w(
    annual_yield_kwh_kwp: float,
    first_year_retention_pct: float,
    annual_degradation_pct_year: float,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
    years: int = 25,
) -> float:
    """Warranty-derived sensitivity; not a field-degradation forecast."""
    curve = warranty_retention_curve(first_year_retention_pct, annual_degradation_pct_year, years)
    return _npv_from_retention_curve(annual_yield_kwh_kwp, curve, energy_value_usd_kwh, discount_rate_pct)


def project_npv(
    capex: float,
    annual_revenue: list[float] | np.ndarray,
    annual_opex: list[float] | np.ndarray,
    annual_replacement: list[float] | np.ndarray | None = None,
    *,
    discount_rate_pct: float,
) -> float:
    """Project NPV with end-of-year cash flows.

    NPV = -CAPEX + sum((Revenue - OPEX - Replacement)/(1+r)^y).
    """
    capex = float(capex)
    if not math.isfinite(capex) or capex < 0:
        raise ValueError("capex must be finite and non-negative.")
    rev = np.asarray(annual_revenue, dtype=float)
    opex = np.asarray(annual_opex, dtype=float)
    repl = np.zeros_like(rev) if annual_replacement is None else np.asarray(annual_replacement, dtype=float)
    if rev.ndim != 1 or len(rev) == 0 or opex.shape != rev.shape or repl.shape != rev.shape:
        raise ValueError("annual revenue, OPEX and replacement arrays must be non-empty and have identical lengths.")
    if not np.isfinite(rev).all() or not np.isfinite(opex).all() or not np.isfinite(repl).all():
        raise ValueError("cash-flow inputs must be finite.")
    r = float(discount_rate_pct) / 100.0
    if not math.isfinite(r) or r <= -1:
        raise ValueError("discount_rate_pct must be finite and greater than -100%.")
    years = np.arange(1, len(rev) + 1, dtype=float)
    return float(-capex + np.sum((rev - opex - repl) / np.power(1.0 + r, years)))


def lcoe(
    capex: float,
    annual_costs: list[float] | np.ndarray,
    annual_energy_kwh: list[float] | np.ndarray,
    *,
    discount_rate_pct: float,
) -> float:
    """Discounted levelized cost of delivered energy in currency/kWh."""
    costs = np.asarray(annual_costs, dtype=float)
    energy = np.asarray(annual_energy_kwh, dtype=float)
    if costs.ndim != 1 or len(costs) == 0 or costs.shape != energy.shape:
        raise ValueError("annual_costs and annual_energy_kwh must be non-empty and have identical lengths.")
    if not np.isfinite(costs).all() or not np.isfinite(energy).all() or np.any(energy < 0):
        raise ValueError("annual cost/energy inputs must be finite; energy cannot be negative.")
    r = float(discount_rate_pct) / 100.0
    if not math.isfinite(r) or r <= -1:
        raise ValueError("discount_rate_pct must be finite and greater than -100%.")
    years = np.arange(1, len(costs) + 1, dtype=float)
    discount = np.power(1.0 + r, years)
    numerator = float(capex) + float(np.sum(costs / discount))
    denominator = float(np.sum(energy / discount))
    if denominator <= 0:
        raise ValueError("discounted lifetime energy must be positive.")
    return numerator / denominator


def area_bos_cost_per_w(module_area_m2: float, pmax_w: float, area_bos_usd_m2: float) -> float:
    area = float(module_area_m2)
    pmax = float(pmax_w)
    cost = float(area_bos_usd_m2)
    if not all(math.isfinite(x) for x in [area, pmax, cost]) or area <= 0 or pmax <= 0 or cost < 0:
        raise ValueError("module area and Pmax must be positive; area-sensitive BOS cost must be non-negative.")
    return cost * area / pmax


def switching_point_table(
    results: pd.DataFrame,
    modules: pd.DataFrame,
    baseline_module_id: str,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
    area_bos_usd_m2: float,
    years: int = 25,
    common_degradation_pct_year: float = 0.50,
    allow_screening_sensitivity: bool = False,
    **legacy_kwargs,
) -> pd.DataFrame:
    """Compute maximum justifiable module-price premium versus a quoted baseline.

    The threshold contains discounted energy-value difference and area-sensitive BOS
    difference. It is a procurement switching sensitivity, not a complete project NPV or
    LCOE. By default candidates with incomplete energy-model evidence fail closed.
    """
    # Accept the former keyword without exposing it in current product documentation.
    if "allow_exploratory" in legacy_kwargs:
        allow_screening_sensitivity = bool(legacy_kwargs.pop("allow_exploratory"))
    if legacy_kwargs:
        raise TypeError(f"Unexpected keyword(s): {', '.join(legacy_kwargs)}")
    _validate_economic_inputs(energy_value_usd_kwh, discount_rate_pct, years)

    if baseline_module_id not in set(results["module_id"]):
        raise ValueError("Baseline module is not in result set.")
    if baseline_module_id not in set(modules["module_id"]):
        raise ValueError("Baseline module is not in module catalog.")

    m_lookup = modules.set_index("module_id")
    r_lookup = results.set_index("module_id")
    baseline_is_eligible = evidence_flag(r_lookup.loc[baseline_module_id].get("decision_eligible", False))
    if not allow_screening_sensitivity and not baseline_is_eligible:
        raise ValueError("Economic baseline is evidence-limited; switching economics are disabled.")

    baseline_m = m_lookup.loc[baseline_module_id]
    baseline_quote = pd.to_numeric(pd.Series([baseline_m.get("quote_usd_w")]), errors="coerce").iloc[0]
    if not np.isfinite(baseline_quote) or float(baseline_quote) < 0:
        raise ValueError("Enter a finite non-negative quoted $/W for the selected baseline module.")

    def values(mid: str) -> tuple[float, float, float]:
        m = m_lookup.loc[mid]
        rr = r_lookup.loc[mid]
        annual = float(rr["annual_yield_kwh_kwp"])
        common_energy_npv = npv_energy_value_common_scenario_per_w(
            annual, common_degradation_pct_year, energy_value_usd_kwh, discount_rate_pct, years
        )
        warranty_energy_npv = npv_energy_value_per_w(
            annual,
            m["first_year_retention_pct"],
            m["annual_warranty_degradation_pct_year"],
            energy_value_usd_kwh,
            discount_rate_pct,
            years,
        )
        area_bos = area_bos_cost_per_w(m["module_area_m2"], m["pmax_w"], area_bos_usd_m2)
        return common_energy_npv, warranty_energy_npv, area_bos

    base_common, base_warranty, base_area = values(baseline_module_id)
    rows = []
    for mid in results["module_id"].astype(str):
        m = m_lookup.loc[mid]
        rr = r_lookup.loc[mid]
        economic_eligible = evidence_flag(rr.get("decision_eligible", False)) and baseline_is_eligible
        quote = pd.to_numeric(pd.Series([m.get("quote_usd_w")]), errors="coerce").iloc[0]
        if np.isfinite(quote) and float(quote) < 0:
            raise ValueError(f"Quote for {mid} cannot be negative.")

        if economic_eligible or allow_screening_sensitivity:
            common_npv, warranty_npv, area_bos = values(mid)
            common_premium = (common_npv - base_common) + (base_area - area_bos)
            warranty_premium = (warranty_npv - base_warranty) + (base_area - area_bos)
            threshold = float(baseline_quote) + common_premium
            warranty_threshold = float(baseline_quote) + warranty_premium
            preferred = bool(np.isfinite(quote) and quote <= threshold) if mid != baseline_module_id else True
            evidence_note = "decision_evidence_supported" if economic_eligible else "screening_sensitivity_incomplete_model_evidence"
        else:
            common_npv = warranty_npv = area_bos = np.nan
            common_premium = threshold = warranty_threshold = np.nan
            preferred = np.nan
            evidence_note = "blocked_incomplete_energy_model_evidence"

        rows.append(
            {
                "module_id": mid,
                "manufacturer": m["manufacturer"],
                "model": m["model"],
                "baseline_module_id": baseline_module_id,
                "npv_energy_value_usd_per_w": common_npv,
                "npv_energy_value_common_degradation_usd_per_w": common_npv,
                "npv_energy_value_warranty_sensitivity_usd_per_w": warranty_npv,
                "area_bos_proxy_usd_per_w": area_bos,
                "allowable_module_price_premium_vs_baseline_usd_w": common_premium,
                "indifference_module_price_usd_w": threshold,
                "indifference_module_price_warranty_sensitivity_usd_w": warranty_threshold,
                "actual_quote_usd_w": quote,
                "economically_preferred_vs_baseline_at_quote": preferred,
                "economic_decision_eligible": economic_eligible,
                "economic_evidence_note": evidence_note,
                "common_degradation_scenario_pct_year": float(common_degradation_pct_year),
                "economic_model_scope": "discounted_energy_value_plus_area_sensitive_BOS_switching_threshold",
                "degradation_policy": "common_project_scenario_primary_warranty_only_sensitivity",
            }
        )
    return pd.DataFrame(rows)
