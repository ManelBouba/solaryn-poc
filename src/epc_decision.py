from __future__ import annotations

import numpy as np
import pandas as pd

from src.evidence_policy import DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT


def _leader_and_gap(df: pd.DataFrame, col: str) -> tuple[pd.Series, float]:
    ordered = df.sort_values(col, ascending=False).reset_index(drop=True)
    leader = ordered.iloc[0]
    if len(ordered) < 2:
        return leader, float("inf")
    top = float(ordered.iloc[0][col])
    second = float(ordered.iloc[1][col])
    gap_pct = 100.0 * (top - second) / max(abs(second), 1e-9)
    return leader, gap_pct


def epc_energy_decision(
    results: pd.DataFrame,
    minimum_separation_pct: float = 1.0,
    uncertainty_guardrail_pct: float = DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT,
) -> dict:
    """Bias-controlled decision guardrail for module comparison.

    A robust V9 physics leader requires:
      * a model-evidence-eligible result for every selected candidate;
      * the same leader for broadband/primary annual and the common-degradation
        lifetime sensitivity;
      * separation larger than both the user policy threshold and the declared
        energy-rating uncertainty guardrail.

    Manufacturer warranty and technology-class spectral corrections are sensitivities,
    not hidden winner-making inputs. If evidence is incomplete, Solaryn fails closed.
    """
    if results.empty:
        raise ValueError("No module results available.")

    primary_col = "annual_yield_kwh_kwp"
    broadband_col = (
        "annual_dc_specific_energy_broadband_kwh_kwp"
        if "annual_dc_specific_energy_broadband_kwh_kwp" in results.columns
        else (
            "annual_dc_specific_energy_no_spectral_kwh_kwp"
            if "annual_dc_specific_energy_no_spectral_kwh_kwp" in results.columns
            else primary_col
        )
    )
    common_lifetime_col = (
        "lifetime_energy_common_degradation_scenario_kwh_kwp"
        if "lifetime_energy_common_degradation_scenario_kwh_kwp" in results.columns
        else "lifetime_energy_warranty_scenario_kwh_kwp"
    )
    warranty_col = (
        "lifetime_energy_warranty_scenario_kwh_kwp"
        if "lifetime_energy_warranty_scenario_kwh_kwp" in results.columns
        else common_lifetime_col
    )

    broadband_leader, broadband_gap = _leader_and_gap(results, broadband_col)
    annual_leader, annual_gap = _leader_and_gap(results, primary_col)
    life_leader, life_gap = _leader_and_gap(results, common_lifetime_col)
    warranty_leader, warranty_gap = _leader_and_gap(results, warranty_col)

    eligible = (
        results["decision_eligible"].fillna(False).astype(bool)
        if "decision_eligible" in results.columns
        else pd.Series(True, index=results.index)
    )
    evidence_complete = bool(eligible.all())
    ineligible_ids = results.loc[~eligible, "module_id"].astype(str).tolist()

    same_physics = broadband_leader["module_id"] == annual_leader["module_id"] == life_leader["module_id"]
    sep = float(minimum_separation_pct)
    u = max(0.0, float(uncertainty_guardrail_pct))
    required_gap = max(sep, u)
    separated = broadband_gap >= required_gap and annual_gap >= required_gap and life_gap >= required_gap

    # New V9 outputs carry a dedicated spectral-sensitivity column. It is diagnostic
    # unless module-specific spectral evidence is available. Older V8-style tables used
    # annual_yield as the spectral-adjusted result; preserve the conservative legacy rule.
    spectral_sensitivity_flag = False
    spectral_sensitivity_leader_id = annual_leader["module_id"]
    if "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp" in results.columns:
        spectral_leader, spectral_gap = _leader_and_gap(results, "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp")
        spectral_sensitivity_leader_id = spectral_leader["module_id"]
        spectral_sensitivity_flag = spectral_leader["module_id"] != broadband_leader["module_id"]
        spectral_proxy_policy = "technology_class_proxy_is_sensitivity_only_unless_module_specific_evidence"
    else:
        spectral_gap = annual_gap
        spectral_sensitivity_flag = annual_leader["module_id"] != broadband_leader["module_id"]
        spectral_proxy_policy = "must_not_change_the_robust_leader"
        if spectral_sensitivity_flag:
            same_physics = False

    warranty_flip = warranty_leader["module_id"] != life_leader["module_id"]

    if not evidence_complete:
        status = "incomplete_cross_technology_model_evidence"
        headline = (
            "No robust cross-technology winner: at least one selected candidate lacks a module-specific "
            "performance matrix or a model class accepted for decision use."
        )
        winner = None
    elif same_physics and separated:
        status = "stable_physics_leader_above_uncertainty_guardrail"
        winner = life_leader["module_id"]
        headline = (
            f"{life_leader['manufacturer']} {life_leader['model']} is the stable physics leader under the "
            f"declared annual/common-degradation scenario, with all required gaps ≥ {required_gap:.2f}%."
        )
        if spectral_sensitivity_flag:
            headline += " Technology-class spectral sensitivity changes the leader; module-specific spectral data is required before a spectral claim."
        if warranty_flip:
            headline += " The manufacturer-warranty sensitivity changes the lifetime leader; warranty language is not treated as field degradation."
    else:
        winner = None
        if not same_physics:
            status = "no_robust_winner_under_declared_scenarios"
            headline = "No robust winner: the leader changes across the declared physics/lifetime scenarios."
        else:
            status = "no_robust_winner_under_uncertainty_guardrail"
            headline = (
                f"No robust winner: the leading module is separated by less than the required "
                f"{required_gap:.2f}% uncertainty/separation guardrail in at least one primary scenario."
            )

    return {
        "status": status,
        "headline": headline,
        "winner_module_id": winner,
        "provisional_broadband_leader_module_id": broadband_leader["module_id"],
        "broadband_leader_module_id": broadband_leader["module_id"],
        "annual_leader_module_id": annual_leader["module_id"],
        "lifetime_leader_module_id": life_leader["module_id"],
        "warranty_sensitivity_leader_module_id": warranty_leader["module_id"],
        "spectral_sensitivity_leader_module_id": spectral_sensitivity_leader_id,
        "broadband_lead_over_second_pct": broadband_gap,
        "annual_lead_over_second_pct": annual_gap,
        "lifetime_lead_over_second_pct": life_gap,
        "warranty_sensitivity_lead_over_second_pct": warranty_gap,
        "spectral_sensitivity_lead_over_second_pct": spectral_gap,
        "minimum_separation_policy_pct": sep,
        "energy_rating_uncertainty_guardrail_pct": u,
        "required_decision_gap_pct": required_gap,
        "evidence_complete_for_all_selected_candidates": evidence_complete,
        "decision_ineligible_module_ids": ineligible_ids,
        "warranty_sensitivity_changes_leader": bool(warranty_flip),
        "spectral_sensitivity_changes_leader": bool(spectral_sensitivity_flag),
        "claim_scope": "scenario_stability_not_probabilistic_confidence",
        "spectral_proxy_policy": spectral_proxy_policy,
        "uncertainty_policy": "decision_gap_must_exceed_declared_energy_rating_uncertainty_guardrail",
    }


def poc_validation_decision(
    results: pd.DataFrame,
    minimum_separation_pct: float = 1.0,
    uncertainty_guardrail_pct: float = DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT,
) -> dict:
    """Return a usable PoC ranking while preserving V9 evidence diagnostics.

    The bankability-style evidence/uncertainty gate remains available as a secondary
    diagnostic via :func:`epc_energy_decision`, but it does not suppress a PoC result.
    This is intentional: the PoC must demonstrate climate-aware ranking and switching
    behaviour before every candidate has lender-grade/module-specific evidence.

    A candidate can therefore be ranked provisionally when its simulation produced a
    finite result. Evidence completeness and the uncertainty guardrail are converted
    into validation-confidence flags rather than hard blockers.
    """
    if results.empty:
        raise ValueError("No module results available.")

    robust = epc_energy_decision(
        results,
        minimum_separation_pct=minimum_separation_pct,
        uncertainty_guardrail_pct=uncertainty_guardrail_pct,
    )

    annual_col = "annual_yield_kwh_kwp"
    lifetime_col = (
        "lifetime_energy_common_degradation_scenario_kwh_kwp"
        if "lifetime_energy_common_degradation_scenario_kwh_kwp" in results.columns
        else annual_col
    )

    usable_mask = np.isfinite(pd.to_numeric(results[annual_col], errors="coerce"))
    if lifetime_col in results.columns:
        usable_mask &= np.isfinite(pd.to_numeric(results[lifetime_col], errors="coerce"))
    usable = results.loc[usable_mask].copy()
    if usable.empty:
        raise ValueError("No candidate produced a finite PoC simulation result.")
    if len(usable) < 2:
        raise ValueError(
            "POC comparison requires at least two candidates with finite simulated energy. "
            f"Only {len(usable)} candidate produced a usable result."
        )

    annual_leader, annual_gap = _leader_and_gap(usable, annual_col)
    life_leader, life_gap = _leader_and_gap(usable, lifetime_col)
    same_leader = str(annual_leader["module_id"]) == str(life_leader["module_id"])

    required_gap = max(
        max(0.0, float(minimum_separation_pct)),
        max(0.0, float(uncertainty_guardrail_pct)),
    )
    leader_evidence_eligible = bool(annual_leader.get("decision_eligible", True))
    all_evidence_complete = bool(
        usable.get("decision_eligible", pd.Series(True, index=usable.index)).fillna(False).astype(bool).all()
    )

    if same_leader and annual_gap >= required_gap and life_gap >= required_gap and leader_evidence_eligible:
        confidence = "strong"
    elif same_leader and leader_evidence_eligible:
        confidence = "moderate"
    else:
        confidence = "exploratory"

    notes = []
    if annual_gap < required_gap:
        notes.append(
            f"annual lead {annual_gap:.2f}% is below the {required_gap:.2f}% validation guardrail"
        )
    if not same_leader:
        notes.append("annual and lifetime scenario leaders differ")
    if not all_evidence_complete:
        notes.append("one or more candidates use exploratory/incomplete model evidence")
    if not leader_evidence_eligible:
        notes.append("the provisional leader itself is not decision-grade")

    winner_name = f"{annual_leader.get('manufacturer', '')} {annual_leader.get('model', '')}".strip()
    if robust.get("winner_module_id") is not None:
        scientific_status = "Robust modeled winner under the declared PoC evidence and decision guardrail."
    elif robust.get("status") == "incomplete_cross_technology_model_evidence":
        scientific_status = "No robust cross-technology winner: model evidence is insufficient for that claim."
    else:
        scientific_status = "No robust winner under the declared PoC decision guardrail."
    headline = (
        f"{scientific_status} {winner_name} has the highest provisional modeled annual DC specific energy "
        f"at {float(annual_leader[annual_col]):,.1f} kWh/kWp/year, with a {annual_gap:.2f}% lead over second place."
    )
    if notes:
        headline += " Validation note: " + "; ".join(notes) + "."

    ineligible_ids = (
        usable.loc[
            ~usable.get("decision_eligible", pd.Series(True, index=usable.index)).fillna(False).astype(bool),
            "module_id",
        ].astype(str).tolist()
        if "decision_eligible" in usable.columns
        else []
    )

    return {
        "status": "poc_provisional_result",
        "headline": headline,
        "winner_module_id": str(annual_leader["module_id"]),
        "provisional_broadband_leader_module_id": str(annual_leader["module_id"]),
        "broadband_leader_module_id": str(annual_leader["module_id"]),
        "annual_leader_module_id": str(annual_leader["module_id"]),
        "lifetime_leader_module_id": str(life_leader["module_id"]),
        "warranty_sensitivity_leader_module_id": robust.get("warranty_sensitivity_leader_module_id"),
        "spectral_sensitivity_leader_module_id": robust.get("spectral_sensitivity_leader_module_id"),
        "broadband_lead_over_second_pct": float(annual_gap),
        "annual_lead_over_second_pct": float(annual_gap),
        "lifetime_lead_over_second_pct": float(life_gap),
        "warranty_sensitivity_lead_over_second_pct": robust.get("warranty_sensitivity_lead_over_second_pct"),
        "spectral_sensitivity_lead_over_second_pct": robust.get("spectral_sensitivity_lead_over_second_pct"),
        "minimum_separation_policy_pct": max(0.0, float(minimum_separation_pct)),
        "energy_rating_uncertainty_guardrail_pct": max(0.0, float(uncertainty_guardrail_pct)),
        "required_decision_gap_pct": float(required_gap),
        "evidence_complete_for_all_selected_candidates": all_evidence_complete,
        "decision_ineligible_module_ids": ineligible_ids,
        "warranty_sensitivity_changes_leader": robust.get("warranty_sensitivity_changes_leader", False),
        "spectral_sensitivity_changes_leader": robust.get("spectral_sensitivity_changes_leader", False),
        "claim_scope": "poc_validation_provisional_not_bankability",
        "spectral_proxy_policy": robust.get("spectral_proxy_policy"),
        "uncertainty_policy": "guardrail_is_validation_confidence_flag_not_poc_result_blocker",
        "validation_confidence": confidence,
        "leader_evidence_eligible": leader_evidence_eligible,
        "robust_status": robust.get("status"),
        "robust_headline": robust.get("headline"),
        "robust_winner_module_id": robust.get("winner_module_id"),
        "poc_usable_candidate_count": int(len(usable)),
        "poc_total_candidate_count": int(len(results)),
    }
