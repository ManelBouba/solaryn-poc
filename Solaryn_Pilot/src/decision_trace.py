"""Build a transparent site -> response -> reliability -> economics decision trace."""
from __future__ import annotations
import pandas as pd


def build_candidate_trace(project: dict, result: pd.Series | dict, qualification: dict, evidence: dict,
                          economics: pd.Series | dict | None = None) -> dict:
    r=dict(result); e=dict(economics or {})
    return {
        "site": {k: project.get(k) for k in ("latitude","longitude","tilt_deg","azimuth_deg","albedo","salinity_stress")},
        "climate_stress": {
            "t98_module_c": r.get("p98_module_temperature_c_all_hours", r.get("p98_module_temperature_c_daylight")),
            "p95_module_c": r.get("p95_module_temperature_c_daylight"),
            "humidity_exposure": qualification.get("humidity_exposure"),
            "snow_exposure": qualification.get("snow_exposure"),
            "salinity_exposure": qualification.get("salinity_exposure"),
        },
        "product_response": {
            "annual_yield_kwh_kwp": r.get("annual_yield_kwh_kwp"),
            "off_stc_irradiance_response_pct": r.get("off_stc_irradiance_response_pct"),
            "temperature_response_effect_pct": r.get("temperature_response_effect_pct"),
            "iam_effect_pct": r.get("iam_effect_pct"),
            "spectral_effect_pct": r.get("spectral_effect_pct"),
            "bifacial_rear_gain_pct": r.get("bifacial_rear_gain_pct"),
        },
        "reliability_evidence": {"qualification": qualification, "evidence": evidence},
        "lifetime": {
            "common_scenario_kwh_kwp": r.get("lifetime_energy_common_degradation_scenario_kwh_kwp"),
            "p50_kwh_kwp": r.get("lifetime_p50_kwh_kwp"),
            "p90_kwh_kwp": r.get("lifetime_p90_kwh_kwp"),
            "degradation_mean_pct_year": r.get("degradation_mean_pct_year"),
            "degradation_sigma_pct_year": r.get("degradation_sigma_pct_year"),
            "degradation_evidence_basis": r.get("degradation_evidence_basis"),
            "warranty_sensitivity_kwh_kwp": r.get("lifetime_energy_warranty_scenario_kwh_kwp"),
        },
        "economics": {
            "allowable_premium_vs_baseline_usd_w": e.get("allowable_module_price_premium_vs_baseline_usd_w"),
            "indifference_module_price_usd_w": e.get("indifference_module_price_usd_w"),
            "actual_quote_usd_w": e.get("actual_quote_usd_w"),
        },
    }
