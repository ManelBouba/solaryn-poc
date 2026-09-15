import numpy as np
import pandas as pd

from src.epc_decision import poc_validation_decision
from src.economics_engine import switching_point_table


def _results():
    return pd.DataFrame([
        {
            "module_id": "A",
            "manufacturer": "MakerA",
            "model": "A1",
            "annual_yield_kwh_kwp": 2000.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 2000.0,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": 1995.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 47000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 46900.0,
            "decision_eligible": True,
        },
        {
            "module_id": "B",
            "manufacturer": "MakerB",
            "model": "B1",
            "annual_yield_kwh_kwp": 1980.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1980.0,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": 1982.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 46530.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 46400.0,
            "decision_eligible": False,
        },
    ])


def test_poc_returns_provisional_winner_even_when_robust_gate_blocks():
    decision = poc_validation_decision(_results(), minimum_separation_pct=1.0, uncertainty_guardrail_pct=2.0)
    assert decision["winner_module_id"] == "A"
    assert decision["status"] == "poc_provisional_result"
    assert decision["evidence_complete_for_all_selected_candidates"] is False
    assert decision["robust_winner_module_id"] is None
    assert decision["validation_confidence"] == "moderate"
    assert decision["headline"].startswith("No robust cross-technology winner")
    assert "MakerA A1 has the highest provisional modeled" in decision["headline"]


def test_poc_economics_can_show_exploratory_threshold_without_marking_it_decision_grade():
    results = _results()
    modules = pd.DataFrame([
        {
            "module_id": "A", "manufacturer": "MakerA", "model": "A1",
            "module_area_m2": 2.5, "pmax_w": 550.0, "quote_usd_w": 0.20,
            "first_year_retention_pct": 99.0, "annual_warranty_degradation_pct_year": 0.4,
        },
        {
            "module_id": "B", "manufacturer": "MakerB", "model": "B1",
            "module_area_m2": 2.6, "pmax_w": 550.0, "quote_usd_w": 0.19,
            "first_year_retention_pct": 99.0, "annual_warranty_degradation_pct_year": 0.4,
        },
    ])
    table = switching_point_table(
        results, modules, "A",
        energy_value_usd_kwh=0.05,
        discount_rate_pct=7.0,
        area_bos_usd_m2=10.0,
        allow_exploratory=True,
    )
    b = table.set_index("module_id").loc["B"]
    assert np.isfinite(b["indifference_module_price_usd_w"])
    assert bool(b["economic_decision_eligible"]) is False
    assert b["economic_evidence_note"] == "poc_exploratory_threshold_incomplete_model_evidence"


def test_poc_requires_two_finite_simulated_candidates():
    import numpy as np
    import pandas as pd
    from src.epc_decision import poc_validation_decision

    results = pd.DataFrame([
        {
            "module_id": "A", "manufacturer": "A", "model": "A1",
            "annual_yield_kwh_kwp": 1500.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1500.0,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": 1500.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 36000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 35000.0,
            "decision_eligible": True,
        },
        {
            "module_id": "B", "manufacturer": "B", "model": "B1",
            "annual_yield_kwh_kwp": np.nan,
            "annual_dc_specific_energy_broadband_kwh_kwp": np.nan,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": np.nan,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": np.nan,
            "lifetime_energy_warranty_scenario_kwh_kwp": np.nan,
            "decision_eligible": False,
        },
    ])
    import pytest
    with pytest.raises(ValueError, match="at least two candidates with finite simulated energy"):
        poc_validation_decision(results)
