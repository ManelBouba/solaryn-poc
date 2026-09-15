from __future__ import annotations
import math

BOM_FIELDS=('glass_configuration','encapsulant','backsheet','cell_interconnect','junction_box','edge_seal','frame','cell_architecture')


def bom_completeness(candidate: dict) -> dict:
    present=[f for f in BOM_FIELDS if str(candidate.get(f,'')).strip()]
    return {'bom_fields_present':len(present),'bom_fields_total':len(BOM_FIELDS),
            'bom_completeness_pct':round(100*len(present)/len(BOM_FIELDS),1),'present_fields':present}


def reliability_exposure_score(exposure: dict, candidate: dict) -> dict:
    """Diagnostic exposure-risk score; does NOT invent annual degradation.

    The score is for triage/evidence gathering only. Lifetime energy may be modified only
    by a field-validated candidate degradation rate elsewhere in the engine.
    """
    heat=min(float(exposure.get('hours_cell_gt_65c',0))/300.0,1.0)
    damp=min(float(exposure.get('damp_heat_hours_40c_85rh',0))/500.0,1.0)
    cycle=min(float(exposure.get('days_thermal_cycle_gt_30c',0))/120.0,1.0)
    sal=min(max(float(exposure.get('salinity_risk',0))/3.0,0),1)
    uv=min(float(exposure.get('uv_dose_proxy',0))/2500.0,1.0)
    raw=100*(0.28*heat+0.25*damp+0.20*cycle+0.15*sal+0.12*uv)
    bom=bom_completeness(candidate)
    return {'reliability_exposure_risk_score_0_100':round(raw,1),**bom,
            'decision_use':'diagnostic_only_unless_failure_mode_or_degradation_model_is_field_calibrated'}
