import numpy as np
import pandas as pd
import pytest

from src.epc_decision import recommendation_decision
from src.economics_engine import switching_point_table


def _results():
    return pd.DataFrame([
        {
            "module_id": "A", "manufacturer": "MakerA", "model": "A1", "technology_label": "TOPCon",
            "annual_yield_kwh_kwp": 2000.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 2000.0,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": 1995.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 47000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 46900.0,
            "decision_eligible": True,
            "electrical_model": "cec_single_diode_datasheet_fit",
            "model_evidence_level": "datasheet_fit_crystalline_silicon_fallback",
            "thermal_evidence_level": "generic_construction_proxy",
        },
        {
            "module_id": "B", "manufacturer": "MakerB", "model": "B1", "technology_label": "CdTe",
            "annual_yield_kwh_kwp": 1980.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1980.0,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": 1982.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 46530.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 46400.0,
            "decision_eligible": False,
            "electrical_model": "cec_single_diode_exploratory_only",
            "model_evidence_level": "technology_model_not_validated_for_this_module",
            "thermal_evidence_level": "generic_construction_proxy",
        },
    ])


def test_recommendation_keeps_technical_leader_but_does_not_force_final_winner():
    decision = recommendation_decision(_results(), minimum_separation_pct=1.0, uncertainty_guardrail_pct=2.0, n_samples=2000)
    assert decision["technical_leader_module_id"] == "A"
    assert decision["winner_module_id"] is None
    assert decision["decision_status"] == "Conditional"
    assert decision["evidence_complete_for_all_selected_candidates"] is False
    assert 0 <= decision["probability_of_best_pct"] <= 100
    assert decision["expected_regret_pct"] >= 0
    assert "Technical leader: MakerA A1" in decision["headline"]


def test_screening_economics_can_show_sensitivity_without_marking_it_decision_grade():
    results = _results()
    modules = pd.DataFrame([
        {"module_id": "A", "manufacturer": "MakerA", "model": "A1", "module_area_m2": 2.5, "pmax_w": 550.0,
         "quote_usd_w": 0.20, "first_year_retention_pct": 99.0, "annual_warranty_degradation_pct_year": 0.4},
        {"module_id": "B", "manufacturer": "MakerB", "model": "B1", "module_area_m2": 2.6, "pmax_w": 550.0,
         "quote_usd_w": 0.19, "first_year_retention_pct": 99.0, "annual_warranty_degradation_pct_year": 0.4},
    ])
    table = switching_point_table(
        results, modules, "A", energy_value_usd_kwh=0.05, discount_rate_pct=7.0,
        area_bos_usd_m2=10.0, allow_screening_sensitivity=True,
    )
    b = table.set_index("module_id").loc["B"]
    assert np.isfinite(b["indifference_module_price_usd_w"])
    assert bool(b["economic_decision_eligible"]) is False
    assert b["economic_evidence_note"] == "screening_sensitivity_incomplete_model_evidence"


def test_recommendation_requires_two_finite_simulated_candidates():
    results = _results()
    results.loc[1, ["annual_yield_kwh_kwp", "lifetime_energy_common_degradation_scenario_kwh_kwp"]] = np.nan
    with pytest.raises(ValueError, match="At least two candidates with finite simulated energy"):
        recommendation_decision(results)
