"""PRD section 13: deterministic policy, independent of UI and probability plots."""
import numpy as np
import pandas as pd
from src.input_validation import evidence_flag, finite_number
from src.epc_decision import _robust_evidence_ready, _robust_thermal_ready, _robust_rear_ready

POLICY_RELEASE = "3.0.0"
LABELS = {
    "ROBUST_MODELED_ADVANTAGE": "Robust modeled advantage",
    "PROVISIONAL_TECHNICAL_LEADER": "Provisional technical leader",
    "EFFECTIVELY_TIED": "Effectively tied",
    "INSUFFICIENT_EVIDENCE": "Insufficient evidence",
}

def decide(results, *, resource_status="not_checked", guardrail_pct=2.0,
           minimum_separation_pct=1.0, failed_candidates=None,
           geometry_confidence="screening_assumptions"):
    gap_required = max(finite_number(guardrail_pct, "guardrail", 0, 100),
                       finite_number(minimum_separation_pct, "minimum separation", 0, 100))
    f = results.copy()
    if len(f) < 2 or f.module_id.duplicated().any():
        raise ValueError("At least two distinct successful candidate simulations are required.")
    for col in ["annual_yield_kwh_kwp", "lifetime_energy_common_degradation_scenario_kwh_kwp"]:
        vals = pd.to_numeric(f[col], errors="coerce")
        if not np.isfinite(vals).all() or (vals <= 0).any():
            raise ValueError("Calculation failed: non-positive or non-finite energy; no ranking available.")
    ordered = f.sort_values(["annual_yield_kwh_kwp", "module_id"], ascending=[False, True])
    top, second = ordered.iloc[0], ordered.iloc[1]
    gap = 100 * (top.annual_yield_kwh_kwp / second.annual_yield_kwh_kwp - 1)
    exact_tie = bool(np.isclose(top.annual_yield_kwh_kwp, second.annual_yield_kwh_kwp, rtol=1e-10))
    eligible = f.get("decision_eligible", pd.Series(False, index=f.index)).map(evidence_flag)
    missing = f.loc[~eligible, "module_id"].tolist()
    life = f.sort_values("lifetime_energy_common_degradation_scenario_kwh_kwp", ascending=False).iloc[0]
    flip = str(life.module_id) != str(top.module_id)
    sensitivity_flips = []
    for col in ["lifetime_energy_warranty_scenario_kwh_kwp", "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp"]:
        if col in f and np.isfinite(pd.to_numeric(f[col], errors="coerce")).all():
            if str(f.sort_values(col, ascending=False).iloc[0].module_id) != str(top.module_id):
                sensitivity_flips.append(col)
    electrical, enote = _robust_evidence_ready(f)
    thermal, tnote = _robust_thermal_ready(f)
    rear, rnote = _robust_rear_ready(f, geometry_confidence)
    reviewed = bool(f.get("claim_evidence_reviewed", pd.Series(False, index=f.index)).map(evidence_flag).all())
    reasons = []
    if missing: reasons.append("Selected candidates lack decision-grade electrical evidence: " + ", ".join(missing))
    if failed_candidates: reasons.append("Selected candidate simulations failed; they cannot be excluded from the requested comparison.")
    if gap <= gap_required: reasons.append(f"Modeled separation {gap:.2f}% is within the {gap_required:.2f}% decision guardrail.")
    if flip or sensitivity_flips: reasons.append("A declared lifetime or sensitivity scenario changes the leader.")
    if resource_status != "adequate": reasons.append("Independent resource agreement is not adequate for a robust claim.")
    if not electrical: reasons.append(enote)
    if not thermal: reasons.append(tnote)
    if not rear: reasons.append(rnote)
    if not reviewed: reasons.append("Exact evidence has not passed a recorded independent claim review; source links and user-entered coefficients alone cannot authorize a robust claim.")
    if missing or failed_candidates:
        state = "INSUFFICIENT_EVIDENCE"
    elif exact_tie or gap <= gap_required or flip or sensitivity_flips:
        state = "EFFECTIVELY_TIED"
    elif resource_status == "adequate" and electrical and thermal and rear and reviewed and geometry_confidence in {"project_design", "measured"}:
        state = "ROBUST_MODELED_ADVANTAGE"
    else:
        state = "PROVISIONAL_TECHNICAL_LEADER"
        if geometry_confidence not in {"project_design", "measured"}: reasons.append("Geometry is a declared screening assumption.")
    leader = None if exact_tie else str(top.module_id)
    headline = LABELS[state] + ". "
    headline += ("No unique numerical leader." if exact_tie else
                 f"{top.manufacturer} {top.model} has the highest modeled annual DC energy ({top.annual_yield_kwh_kwp:,.1f} kWh/kWp/year).")
    return dict(status=state, label=LABELS[state], headline=headline,
                provisional_leader_module_id=leader,
                robust_winner_module_id=leader if state == "ROBUST_MODELED_ADVANTAGE" else None,
                annual_lead_over_second_pct=float(gap), required_decision_gap_pct=gap_required,
                reasons=reasons, sensitivity_leader_changes=sensitivity_flips,
                evidence_ineligible_module_ids=missing, failed_candidates=failed_candidates or [],
                guardrail_interpretation="Versioned decision policy; not statistical confidence.",
                next_evidence="Resolve failed simulations and evidence gaps; compare price and project constraints when effectively tied.")
