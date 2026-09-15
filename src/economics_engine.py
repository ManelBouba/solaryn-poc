from __future__ import annotations

import numpy as np
import pandas as pd

from src.lifetime_engine import common_linear_degradation_curve, warranty_retention_curve


def _npv_from_retention_curve(
    annual_yield_kwh_kwp: float,
    curve: pd.DataFrame,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
) -> float:
    r = float(discount_rate_pct) / 100.0
    if r <= -1:
        raise ValueError("discount_rate_pct must be greater than -100%.")
    annual_per_w = (
        float(annual_yield_kwh_kwp) / 1000.0
        * curve["annual_energy_retention_scenario_pct"].to_numpy() / 100.0
    )
    discounts = np.array([(1.0 + r) ** year for year in curve["year"]], dtype=float)
    return float(np.sum(annual_per_w * float(energy_value_usd_kwh) / discounts))


def npv_energy_value_common_scenario_per_w(
    annual_yield_kwh_kwp: float,
    annual_degradation_pct_year: float,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
    years: int = 25,
) -> float:
    """Primary bias-controlled energy-value sensitivity using one common degradation path."""
    curve = common_linear_degradation_curve(annual_degradation_pct_year, years)
    return _npv_from_retention_curve(annual_yield_kwh_kwp, curve, energy_value_usd_kwh, discount_rate_pct)


def npv_energy_value_per_w(
    annual_yield_kwh_kwp: float,
    first_year_retention_pct: float,
    annual_degradation_pct_year: float,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
    years: int = 25,
) -> float:
    """Warranty-derived economic sensitivity retained for backwards compatibility.

    This is NOT the V9 primary switching metric because manufacturer warranty language
    must not manufacture the procurement winner. It is reported only as a sensitivity.
    """
    curve = warranty_retention_curve(first_year_retention_pct, annual_degradation_pct_year, years)
    return _npv_from_retention_curve(annual_yield_kwh_kwp, curve, energy_value_usd_kwh, discount_rate_pct)


def area_bos_cost_per_w(module_area_m2: float, pmax_w: float, area_bos_usd_m2: float) -> float:
    return float(area_bos_usd_m2) * float(module_area_m2) / float(pmax_w)


def switching_point_table(
    results: pd.DataFrame,
    modules: pd.DataFrame,
    baseline_module_id: str,
    energy_value_usd_kwh: float,
    discount_rate_pct: float,
    area_bos_usd_m2: float,
    years: int = 25,
    common_degradation_pct_year: float = 0.50,
    allow_exploratory: bool = False,
) -> pd.DataFrame:
    """Compute module-price indifference thresholds versus a real baseline quote.

    ``allow_exploratory=True`` is intended only for PoC validation. It calculates
    transparent provisional thresholds for candidates whose energy-model evidence is
    incomplete, while keeping ``economic_decision_eligible=False`` so those outputs
    cannot be mistaken for bankability-grade economics.

    V9 primary threshold uses a *common* project degradation sensitivity across all
    modules. A second warranty-derived threshold is shown only as a sensitivity.

      quote_A* = quote_B + (NPVenergy_A - NPVenergy_B)
                         + (areaBOS_B - areaBOS_A)

    This remains a module + area-sensitive BOS switching proxy, not full LCOE.
    """
    if baseline_module_id not in set(results["module_id"]):
        raise ValueError("Baseline module is not in result set.")

    m_lookup = modules.set_index("module_id")
    r_lookup = results.set_index("module_id")
    if (
        not allow_exploratory
        and "decision_eligible" in r_lookup.columns
        and not bool(r_lookup.loc[baseline_module_id, "decision_eligible"])
    ):
        raise ValueError("Economic switching baseline is decision-ineligible because its energy model evidence is incomplete.")
    baseline_m = m_lookup.loc[baseline_module_id]
    baseline_quote = pd.to_numeric(pd.Series([baseline_m.get("quote_usd_w")]), errors="coerce").iloc[0]
    if not np.isfinite(baseline_quote):
        raise ValueError("Enter a real quoted $/W for the selected baseline module.")

    def values(mid: str) -> tuple[float, float, float]:
        m = m_lookup.loc[mid]
        rr = r_lookup.loc[mid]
        annual = float(rr["annual_yield_kwh_kwp"])
        common_energy_npv = npv_energy_value_common_scenario_per_w(
            annual,
            common_degradation_pct_year,
            energy_value_usd_kwh,
            discount_rate_pct,
            years,
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
    for mid in results["module_id"]:
        m = m_lookup.loc[mid]
        rr = r_lookup.loc[mid]
        economic_eligible = bool(rr.get("decision_eligible", True))
        quote = pd.to_numeric(pd.Series([m.get("quote_usd_w")]), errors="coerce").iloc[0]
        if economic_eligible or allow_exploratory:
            common_npv, warranty_npv, area_bos = values(mid)
            common_premium = (common_npv - base_common) + (base_area - area_bos)
            warranty_premium = (warranty_npv - base_warranty) + (base_area - area_bos)
            threshold = float(baseline_quote) + common_premium
            warranty_threshold = float(baseline_quote) + warranty_premium
            preferred = bool(np.isfinite(quote) and quote <= threshold) if mid != baseline_module_id else True
            evidence_note = (
                "energy_model_eligible_for_switching_screen"
                if economic_eligible
                else "poc_exploratory_threshold_incomplete_model_evidence"
            )
        else:
            # Bankability-oriented mode remains fail-closed by default.
            common_npv = warranty_npv = area_bos = np.nan
            common_premium = warranty_premium = np.nan
            threshold = warranty_threshold = np.nan
            preferred = np.nan
            evidence_note = "blocked_incomplete_energy_model_evidence"
        rows.append({
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
            "economic_model_scope": "module_plus_area_BOS_switching_proxy_not_LCOE",
            "degradation_policy": "common_project_scenario_primary_warranty_only_sensitivity",
        })
    return pd.DataFrame(rows)
