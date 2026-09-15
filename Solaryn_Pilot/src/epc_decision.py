from __future__ import annotations

import numpy as np
import pandas as pd
from src.input_validation import evidence_flag

from src.evidence_policy import DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT
from src.uncertainty_engine import DecisionUncertaintyPolicy, compare_candidates_correlated


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
    """Conservative deterministic evidence guardrail for module comparisons.

    This check is retained as an auditable secondary diagnostic. It does not pretend a
    fixed gap is a scientific confidence interval; the threshold is a configurable risk
    policy. The primary product decision also reports probability of best and expected
    regret through :func:`recommendation_decision`.
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
        results["decision_eligible"].map(evidence_flag)
        if "decision_eligible" in results.columns
        else pd.Series(False, index=results.index)
    )
    evidence_complete = bool(eligible.all())
    ineligible_ids = results.loc[~eligible, "module_id"].astype(str).tolist()

    same_physics = broadband_leader["module_id"] == annual_leader["module_id"] == life_leader["module_id"]
    sep = max(0.0, float(minimum_separation_pct))
    u = max(0.0, float(uncertainty_guardrail_pct))
    required_gap = max(sep, u)
    separated = broadband_gap >= required_gap and annual_gap >= required_gap and life_gap >= required_gap

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
        spectral_proxy_policy = "unsupported_spectral_differentiation_cannot_change_primary_decision"
        if spectral_sensitivity_flag:
            same_physics = False

    warranty_flip = warranty_leader["module_id"] != life_leader["module_id"]

    if not evidence_complete:
        status = "evidence_limited"
        headline = "No robust cross-technology recommendation: at least one selected candidate lacks decision-grade model evidence."
        winner = None
    elif same_physics and separated:
        status = "stable_above_policy_guardrail"
        winner = str(life_leader["module_id"])
        headline = (
            f"{life_leader['manufacturer']} {life_leader['model']} remains the leader across the primary annual and "
            f"common-lifetime scenarios, with all declared gaps at or above {required_gap:.2f}%."
        )
    else:
        winner = None
        if not same_physics:
            status = "scenario_sensitive"
            headline = "No robust recommendation: the leader changes across the declared primary scenarios."
        else:
            status = "below_policy_guardrail"
            headline = (
                f"No robust recommendation: the leading candidate is separated by less than the configured "
                f"{required_gap:.2f}% decision policy in at least one primary scenario."
            )

    return {
        "status": status,
        "headline": headline,
        "winner_module_id": winner,
        "provisional_broadband_leader_module_id": str(broadband_leader["module_id"]),
        "broadband_leader_module_id": str(broadband_leader["module_id"]),
        "annual_leader_module_id": str(annual_leader["module_id"]),
        "lifetime_leader_module_id": str(life_leader["module_id"]),
        "warranty_sensitivity_leader_module_id": str(warranty_leader["module_id"]),
        "spectral_sensitivity_leader_module_id": str(spectral_sensitivity_leader_id),
        "broadband_lead_over_second_pct": float(broadband_gap),
        "annual_lead_over_second_pct": float(annual_gap),
        "lifetime_lead_over_second_pct": float(life_gap),
        "warranty_sensitivity_lead_over_second_pct": float(warranty_gap),
        "spectral_sensitivity_lead_over_second_pct": float(spectral_gap),
        "minimum_separation_policy_pct": sep,
        "energy_rating_uncertainty_guardrail_pct": u,
        "required_decision_gap_pct": required_gap,
        "evidence_complete_for_all_selected_candidates": evidence_complete,
        "decision_ineligible_module_ids": ineligible_ids,
        "warranty_sensitivity_changes_leader": bool(warranty_flip),
        "spectral_sensitivity_changes_leader": bool(spectral_sensitivity_flag),
        "claim_scope": "deterministic_scenario_stability_policy_not_confidence_interval",
        "spectral_proxy_policy": spectral_proxy_policy,
    }


def _resource_confidence(resource_disagreement_pct: float | None, crosscheck_status: str | None) -> dict:
    """Classify independent-resource agreement using transparent product policy bands.

    The bands are governance thresholds, not physical laws. They control how strongly
    Solaryn may word a recommendation; they never alter mean modeled energy.
    """
    status = str(crosscheck_status or "not_checked").lower()
    if status not in {"ok", "success", "passed"} or resource_disagreement_pct is None:
        return {
            "label": "Not checked",
            "decision_cap": "Conditional",
            "reason": "Independent resource cross-check is unavailable.",
        }
    value = abs(float(resource_disagreement_pct))
    if not np.isfinite(value):
        return {
            "label": "Not checked",
            "decision_cap": "Conditional",
            "reason": "Independent resource cross-check is unavailable.",
        }
    if value <= 5.0:
        return {"label": "High", "decision_cap": "Robust", "reason": f"Independent annual POA sources differ by {value:.1f}%."}
    if value <= 10.0:
        return {"label": "Moderate", "decision_cap": "Probable", "reason": f"Independent annual POA sources differ by {value:.1f}%."}
    return {"label": "Low", "decision_cap": "Conditional", "reason": f"Independent annual POA sources differ by {value:.1f}%; resource disagreement is decision-material."}


def _robust_evidence_ready(frontier: pd.DataFrame) -> tuple[bool, str]:
    """Require decision-critical electrical evidence stronger than a datasheet fit."""
    if frontier.empty:
        return False, "No decision-eligible candidates."
    ordered = frontier.sort_values("annual_yield_kwh_kwp", ascending=False).head(2)
    weak = []
    for _, row in ordered.iterrows():
        level = str(row.get("model_evidence_level", "")).lower()
        model = str(row.get("electrical_model", "")).lower()
        strong = ("module_specific_measured_matrix" in level or "iec61853" in model or "independent_validated" in level)
        if not strong:
            weak.append(str(row.get("module_id", "candidate")))
    if weak:
        return False, "Top decision candidates still rely on datasheet/model fallback electrical evidence: " + ", ".join(weak)
    return True, "Top decision candidates have measured or independently validated off-STC electrical evidence."


def _robust_thermal_ready(frontier: pd.DataFrame) -> tuple[bool, str]:
    """Require top-two thermal behavior to be measured/module-specific/independently validated."""
    if frontier.empty:
        return False, "No decision-eligible candidates."
    ordered = frontier.sort_values("annual_yield_kwh_kwp", ascending=False).head(2)
    weak = []
    for _, row in ordered.iterrows():
        level = str(row.get("thermal_evidence_level", "")).lower()
        strong = any(token in level for token in ("module_specific", "measured", "validated"))
        if not strong:
            weak.append(str(row.get("module_id", "candidate")))
    if weak:
        return False, "Top decision candidates still rely on generic thermal construction proxies: " + ", ".join(weak)
    return True, "Top decision candidates have module-specific, measured, or independently validated thermal evidence."


def _robust_rear_ready(frontier: pd.DataFrame, geometry_confidence: str) -> tuple[bool, str]:
    """Require measured/as-built geometry when modeled rear irradiance is decision-material.

    The threshold is a transparent product-governance trigger, not a physical constant.
    It only controls claim strength; it never alters the modeled rear-side energy.
    """
    if frontier.empty:
        return False, "No decision-eligible candidates."
    ordered = frontier.sort_values("annual_yield_kwh_kwp", ascending=False).head(2)
    rear_material = False
    for _, row in ordered.iterrows():
        active = bool(row.get("rear_irradiance_model_active", False))
        gain = pd.to_numeric(pd.Series([row.get("bifacial_rear_gain_pct", 0.0)]), errors="coerce").iloc[0]
        if active and np.isfinite(gain) and abs(float(gain)) >= 0.5:
            rear_material = True
            break
    if not rear_material:
        return True, "Rear-side contribution is absent or below the 0.5% claim-governance trigger for the top decision candidates."
    # The current product can model rear irradiance from row geometry, but that
    # model has not yet been independently validated against measured rear POA for
    # the commercial decision path. Even measured geometry therefore cannot by
    # itself unlock the strongest claim. This is deliberately fail-closed.
    geom = str(geometry_confidence).lower()
    if geom == "measured":
        return False, "Measured/as-built geometry is available, but decision-material rear POA still requires independent measured rear-irradiance validation before Robust wording."
    return False, "Decision-material rear-side gain is modeled from design/screening geometry and the rear-POA model is not independently validated for this project; obtain measured/as-built geometry, albedo, and rear-irradiance validation."


def recommendation_decision(
    results: pd.DataFrame,
    *,
    minimum_separation_pct: float = 1.0,
    uncertainty_guardrail_pct: float = DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT,
    risk_policy: DecisionUncertaintyPolicy | None = None,
    shared_resource_sigma_pct: float = 3.0,
    annual_scenarios: pd.DataFrame | None = None,
    resource_disagreement_pct: float | None = None,
    resource_crosscheck_status: str | None = None,
    geometry_confidence: str = "screening_assumptions",
    n_samples: int = 20_000,
    seed: int = 95,
) -> dict:
    """Return an evidence-, resource-, and uncertainty-aware recommendation.

    Two frontiers are deliberately separated:
    1. *Exploratory model frontier*: every candidate with a finite modeled result.
    2. *Decision frontier*: only candidates whose electrical model is eligible for the
       requested decision scope.

    This prevents a high-uncertainty, evidence-ineligible candidate from receiving a
    misleading procurement ``P(best)`` merely because its distribution has wide tails.
    If the exploratory nominal leader is itself evidence-ineligible, the correct output
    is ``No decision`` because the missing evidence could change the procurement choice.
    """
    if results.empty:
        raise ValueError("No module results available.")
    risk_policy = risk_policy or DecisionUncertaintyPolicy()

    annual_col = "annual_yield_kwh_kwp"
    lifetime_col = (
        "lifetime_energy_common_degradation_scenario_kwh_kwp"
        if "lifetime_energy_common_degradation_scenario_kwh_kwp" in results.columns
        else annual_col
    )
    usable = results.copy()
    usable[annual_col] = pd.to_numeric(usable[annual_col], errors="coerce")
    usable[lifetime_col] = pd.to_numeric(usable[lifetime_col], errors="coerce")
    usable = usable[np.isfinite(usable[annual_col]) & np.isfinite(usable[lifetime_col])].reset_index(drop=True)
    if len(usable) < 2:
        raise ValueError("At least two candidates with finite simulated energy are required.")

    eligible_mask = (
        usable["decision_eligible"].map(evidence_flag)
        if "decision_eligible" in usable.columns
        else pd.Series(False, index=usable.index)
    )
    frontier = usable.loc[eligible_mask].reset_index(drop=True)
    if frontier.empty:
        # No candidate can support a decision claim. Keep a numerical exploratory
        # leader visible but fail closed at the recommendation layer.
        frontier = usable.iloc[[0]].copy()
        frontier["decision_eligible"] = False

    exploratory_leader, exploratory_gap = _leader_and_gap(usable, annual_col)
    technical_leader, annual_gap = _leader_and_gap(frontier, annual_col)
    lifetime_leader, lifetime_gap = _leader_and_gap(frontier, lifetime_col)

    # Deterministic policy guardrail applies only when at least two candidates pass
    # the evidence gate; otherwise there is no competitive decision frontier.
    if len(frontier) >= 2 and bool(frontier.get("decision_eligible", pd.Series(False)).all()):
        strict = epc_energy_decision(
            frontier,
            minimum_separation_pct=minimum_separation_pct,
            uncertainty_guardrail_pct=uncertainty_guardrail_pct,
        )
        decision_uncertainty = compare_candidates_correlated(
            frontier,
            value_col=annual_col,
            shared_resource_sigma_pct=shared_resource_sigma_pct,
            shared_scenarios=annual_scenarios,
            n=n_samples,
            seed=seed,
        )
    else:
        only = str(technical_leader["module_id"])
        val = float(technical_leader[annual_col])
        strict = {
            "status": "insufficient_decision_frontier",
            "headline": "Fewer than two candidates pass the decision evidence gate.",
            "winner_module_id": None,
            "required_decision_gap_pct": max(float(minimum_separation_pct), float(uncertainty_guardrail_pct)),
        }
        decision_uncertainty = {
            "probability_of_best_pct": {only: 100.0},
            "expected_regret_pct": {only: 0.0},
            "p50": {only: val}, "p90": {only: val},
            "candidate_model_sigma_pct": {only: float("nan")},
            "shared_resource_sigma_pct": float(shared_resource_sigma_pct),
            "resource_uncertainty_basis": "not_meaningful_single_eligible_candidate",
            "method": "single decision-eligible candidate; competitive probability not decision-meaningful",
        }
    exploratory_uncertainty = compare_candidates_correlated(
        usable,
        value_col=annual_col,
        shared_resource_sigma_pct=shared_resource_sigma_pct,
        shared_scenarios=annual_scenarios,
        n=n_samples,
        seed=seed,
    )

    leader_id = str(technical_leader["module_id"])
    exploratory_leader_id = str(exploratory_leader["module_id"])
    p_best = float(decision_uncertainty["probability_of_best_pct"][leader_id])
    regret = float(decision_uncertainty["expected_regret_pct"][leader_id])
    evidence_complete = bool(eligible_mask.all())
    ineligible_ids = usable.loc[~eligible_mask, "module_id"].astype(str).tolist()
    exploratory_leader_eligible = evidence_flag(exploratory_leader.get("decision_eligible", False))
    resource = _resource_confidence(resource_disagreement_pct, resource_crosscheck_status)
    eligible_frontier = usable.loc[eligible_mask].reset_index(drop=True)
    robust_evidence_ready, robust_evidence_reason = _robust_evidence_ready(eligible_frontier)
    robust_thermal_ready, robust_thermal_reason = _robust_thermal_ready(eligible_frontier)
    geometry_confidence_norm = str(geometry_confidence or "screening_assumptions").strip().lower()
    geometry_ready_for_robust = geometry_confidence_norm in {"project_design", "measured", "project_design_or_measured"}
    robust_rear_ready, robust_rear_reason = _robust_rear_ready(eligible_frontier, geometry_confidence_norm)
    resource_history_ready_for_robust = decision_uncertainty.get("resource_uncertainty_basis") == "empirical_interannual"

    # A common multiplicative degradation sensitivity cannot establish a different
    # lifetime technology winner. Keep the arithmetic for scenario planning but do not
    # use it as independent evidence for recommendation robustness.
    lifetime_status = "Not differentiated — neutral common degradation sensitivity only"

    if not exploratory_leader_eligible:
        decision_status = "No decision"
        final_id = None
        next_evidence = (
            "The numerical exploratory leader is outside the decision-grade electrical-model evidence boundary. "
            "Obtain candidate-specific IEC 61853 P(G,T) data or an independently validated device model before excluding it."
        )
    else:
        robust_ready = (
            len(frontier) >= 2
            and evidence_complete
            and resource["label"] == "High"
            and resource_history_ready_for_robust
            and robust_evidence_ready
            and robust_thermal_ready
            and geometry_ready_for_robust
            and robust_rear_ready
            and p_best >= risk_policy.robust_probability_pct
            and regret <= risk_policy.robust_max_expected_regret_pct
            and strict.get("winner_module_id") == leader_id
        )
        probable_ready = (
            len(frontier) >= 2
            and evidence_complete
            and resource["label"] in {"High", "Moderate"}
            and p_best >= risk_policy.probable_probability_pct
        )
        if robust_ready:
            decision_status = "Robust"
            final_id = leader_id
            next_evidence = "No decision-critical evidence gap identified by the current screening policy. Preserve the run manifest and validate against project measurements when available."
        elif probable_ready:
            decision_status = "Probable"
            final_id = leader_id
            next_evidence = "Acquire candidate-specific off-STC validation for the closest competing module to reduce ranking uncertainty."
        else:
            decision_status = "Conditional"
            final_id = None
            if len(frontier) < 2:
                next_evidence = "At least one additional competing candidate must pass the decision evidence gate before a procurement recommendation can be robust."
            elif resource["label"] == "Low":
                next_evidence = (
                    f"Reconcile the solar-resource input first: {resource['reason']} "
                    "Prefer on-site POA measurements or a third independent resource before procurement."
                )
            elif resource["label"] == "Not checked":
                next_evidence = "Run an independent resource/POA cross-check before promoting the result beyond a conditional recommendation."
            elif not evidence_complete:
                next_evidence = "Acquire decision-grade off-STC data for evidence-limited candidates before making a cross-technology procurement claim."
            elif not resource_history_ready_for_robust and p_best >= risk_policy.probable_probability_pct:
                next_evidence = "Use at least two complete resource years so interannual variability is represented by shared empirical site scenarios before using Robust wording."
            elif not robust_evidence_ready and p_best >= risk_policy.probable_probability_pct:
                next_evidence = robust_evidence_reason + " Acquire candidate-specific IEC 61853 P(G,T) or independently validated parameters before using Robust wording."
            elif not robust_thermal_ready and p_best >= risk_policy.probable_probability_pct:
                next_evidence = robust_thermal_reason + " Supply measured/module-specific thermal coefficients or an independently validated mount/construction transfer model."
            elif not geometry_ready_for_robust and p_best >= risk_policy.probable_probability_pct:
                next_evidence = "Replace screening geometry assumptions with project-design or measured tilt/row/albedo inputs before using Robust wording."
            elif not robust_rear_ready and p_best >= risk_policy.probable_probability_pct:
                next_evidence = robust_rear_reason
            else:
                next_evidence = "Acquire candidate-specific performance evidence for the top two decision-eligible modules; current distributions overlap materially."

    manufacturer = str(technical_leader.get("manufacturer", "")).strip()
    model = str(technical_leader.get("model", "")).strip()
    technology = str(technical_leader.get("technology_label", "")).strip()
    technical_name = " ".join(x for x in [manufacturer, model] if x)
    headline = (
        f"Technical leader: {technical_name or leader_id} (decision-eligible frontier)"
        + (f" ({technology})" if technology else "")
        + f", {float(technical_leader[annual_col]):,.1f} kWh/kWp/year. "
        f"Decision status: {decision_status}. Decision-frontier P(best)={p_best:.1f}% and expected regret={regret:.2f}%."
    )
    if exploratory_leader_id != leader_id:
        headline += (
            f" Exploratory numerical leader {exploratory_leader_id} is not the decision leader because its evidence/model path does not pass the decision gate."
        )

    return {
        "status": decision_status,
        "decision_status": decision_status,
        "headline": headline,
        "winner_module_id": final_id,
        "recommended_module_id": final_id,
        "technical_leader_module_id": leader_id,
        "technical_leader_manufacturer": manufacturer,
        "technical_leader_model": model,
        "technical_leader_technology": technology,
        "exploratory_technical_leader_module_id": exploratory_leader_id,
        "exploratory_technical_leader_eligible": exploratory_leader_eligible,
        "exploratory_lead_over_second_pct": float(exploratory_gap),
        "lifetime_leader_module_id": str(lifetime_leader["module_id"]),
        "lifetime_status": lifetime_status,
        # Backwards-compatible numerical gap across every modeled candidate.
        # The procurement decision uses the separate decision-frontier gap below.
        "annual_lead_over_second_pct": float(exploratory_gap),
        "decision_frontier_lead_over_second_pct": float(annual_gap),
        "lifetime_lead_over_second_pct": float(lifetime_gap),
        "probability_of_best_pct": p_best,
        "expected_regret_pct": regret,
        "probability_by_candidate_pct": decision_uncertainty["probability_of_best_pct"],
        "expected_regret_by_candidate_pct": decision_uncertainty["expected_regret_pct"],
        "p50_by_candidate": decision_uncertainty["p50"],
        "p90_by_candidate": decision_uncertainty["p90"],
        "candidate_model_sigma_pct": decision_uncertainty["candidate_model_sigma_pct"],
        "shared_resource_sigma_pct": decision_uncertainty["shared_resource_sigma_pct"],
        "resource_uncertainty_basis": decision_uncertainty.get("resource_uncertainty_basis", "screening_prior"),
        "exploratory_probability_by_candidate_pct": exploratory_uncertainty["probability_of_best_pct"],
        "exploratory_expected_regret_by_candidate_pct": exploratory_uncertainty["expected_regret_pct"],
        "decision_frontier_size": int(len(usable.loc[eligible_mask])),
        "evidence_complete_for_all_selected_candidates": evidence_complete,
        "decision_ineligible_module_ids": ineligible_ids,
        "leader_evidence_eligible": True,
        "next_evidence_request": next_evidence,
        "deterministic_guardrail_status": strict["status"],
        "deterministic_guardrail_headline": strict["headline"],
        "required_decision_gap_pct": strict["required_decision_gap_pct"],
        "resource_confidence": resource["label"],
        "resource_confidence_reason": resource["reason"],
        "robust_evidence_ready": bool(robust_evidence_ready),
        "robust_evidence_reason": robust_evidence_reason,
        "robust_thermal_ready": bool(robust_thermal_ready),
        "robust_thermal_reason": robust_thermal_reason,
        "resource_history_ready_for_robust": bool(resource_history_ready_for_robust),
        "geometry_confidence": geometry_confidence_norm,
        "geometry_ready_for_robust": bool(geometry_ready_for_robust),
        "robust_rear_ready": bool(robust_rear_ready),
        "robust_rear_reason": robust_rear_reason,
        "resource_disagreement_pct": (float(resource_disagreement_pct) if resource_disagreement_pct is not None and np.isfinite(float(resource_disagreement_pct)) else np.nan),
        "risk_policy": {
            "robust_probability_pct": risk_policy.robust_probability_pct,
            "probable_probability_pct": risk_policy.probable_probability_pct,
            "robust_max_expected_regret_pct": risk_policy.robust_max_expected_regret_pct,
            "resource_high_agreement_max_pct": 5.0,
            "resource_moderate_agreement_max_pct": 10.0,
        },
        "claim_scope": "DC_module_selection_decision_support; commercial procurement requires project-specific AC/system design, quotes, BOS/O&M, and applicable lifetime evidence",
        "uncertainty_method": decision_uncertainty["method"],
    }
