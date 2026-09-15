from pathlib import Path

import numpy as np
import pandas as pd

from src.data_fetchers import nasa_hourly_to_site_summary
from src.epc_decision import recommendation_decision
from src.epc_report import _monthly_profile

ROOT = Path(__file__).resolve().parents[1]


def _decision_rows(ineligible_leads: bool = False) -> pd.DataFrame:
    c_val = 2050.0 if ineligible_leads else 1995.0
    rows = [
        {"module_id":"A","manufacturer":"A","model":"A","technology_label":"TOPCon","annual_yield_kwh_kwp":2000.0,"annual_dc_specific_energy_broadband_kwh_kwp":2000.0,"annual_dc_specific_energy_spectral_sensitivity_kwh_kwp":2000.0,"lifetime_energy_common_degradation_scenario_kwh_kwp":47000.0,"lifetime_energy_warranty_scenario_kwh_kwp":47000.0,"decision_eligible":True,"electrical_model":"cec_single_diodel_datasheet_fit","model_evidence_level":"datasheet_fit_crystalline_silicon_fallback","thermal_evidence_level":"generic_construction_proxy"},
        {"module_id":"B","manufacturer":"B","model":"B","technology_label":"HJT","annual_yield_kwh_kwp":1900.0,"annual_dc_specific_energy_broadband_kwh_kwp":1900.0,"annual_dc_specific_energy_spectral_sensitivity_kwh_kwp":1900.0,"lifetime_energy_common_degradation_scenario_kwh_kwp":44650.0,"lifetime_energy_warranty_scenario_kwh_kwp":44650.0,"decision_eligible":True,"electrical_model":"cec_single_diodel_datasheet_fit","model_evidence_level":"datasheet_fit_crystalline_silicon_fallback","thermal_evidence_level":"generic_construction_proxy"},
        {"module_id":"C","manufacturer":"C","model":"C","technology_label":"CdTe","annual_yield_kwh_kwp":c_val,"annual_dc_specific_energy_broadband_kwh_kwp":c_val,"annual_dc_specific_energy_spectral_sensitivity_kwh_kwp":c_val,"lifetime_energy_common_degradation_scenario_kwh_kwp":c_val*23.5,"lifetime_energy_warranty_scenario_kwh_kwp":c_val*23.5,"decision_eligible":False,"electrical_model":"exploratory_only","model_evidence_level":"technology_model_not_validated_for_this_module","thermal_evidence_level":"generic_construction_proxy"},
    ]
    return pd.DataFrame(rows)


def test_decision_probability_excludes_evidence_ineligible_candidates():
    d = recommendation_decision(
        _decision_rows(),
        resource_disagreement_pct=2.0,
        resource_crosscheck_status="ok",
        n_samples=3000,
    )
    assert set(d["probability_by_candidate_pct"]) == {"A", "B"}
    assert "C" in d["exploratory_probability_by_candidate_pct"]
    assert d["decision_frontier_size"] == 2
    assert d["resource_confidence"] == "High"
    # Evidence-incomplete selected set caps wording even when the eligible frontier is clear.
    assert d["decision_status"] == "Conditional"


def test_ineligible_exploratory_leader_forces_no_decision():
    d = recommendation_decision(
        _decision_rows(ineligible_leads=True),
        resource_disagreement_pct=1.0,
        resource_crosscheck_status="ok",
        n_samples=2000,
    )
    assert d["exploratory_technical_leader_module_id"] == "C"
    assert d["technical_leader_module_id"] == "A"
    assert d["decision_status"] == "No decision"


def test_low_resource_confidence_caps_recommendation():
    rows = _decision_rows().iloc[:2].copy()
    d = recommendation_decision(
        rows,
        resource_disagreement_pct=12.0,
        resource_crosscheck_status="ok",
        n_samples=3000,
    )
    assert d["resource_confidence"] == "Low"
    assert d["decision_status"] == "Conditional"
    assert "resource" in d["next_evidence_request"].lower()


def test_multiyear_resource_is_annualized_not_summed():
    times = pd.date_range("2019-01-01", "2020-12-31 23:00", freq="h", tz="UTC")
    n = len(times)
    df = pd.DataFrame({
        "time_utc": times,
        "ALLSKY_SFC_SW_DWN": np.full(n, 100.0),
        "ALLSKY_SFC_SW_DNI": np.full(n, 50.0),
        "T2M": np.full(n, 20.0),
        "RH2M": np.full(n, 50.0),
        "WS10M": np.full(n, 3.0),
        "PRECTOTCORR": np.zeros(n),
        "PS": np.full(n, 101.0),
    })
    site = nasa_hourly_to_site_summary(df, 50.0, 4.0).iloc[0]
    expected = ((8760 * 100 / 1000) + (8784 * 100 / 1000)) / 2
    assert site["resource_year_count"] == 2
    assert site["ghi_kwh_m2_year"] == expected


def test_monthly_profile_preserves_twelve_months_with_multiyear_weights():
    times = pd.date_range("2019-01-01", "2020-12-31 23:00", freq="h", tz="UTC")
    h = pd.DataFrame({
        "timestamp": times,
        "module_id": "A",
        "specific_power_kw_per_kwp": 0.1,
        "days_weight": 0.5,
    })
    modules = pd.DataFrame([{"module_id":"A","manufacturer":"Maker","model":"Module"}])
    out = _monthly_profile(h, modules)
    assert out["month_num"].nunique() == 12
    assert set(out["month_num"].astype(int)) == set(range(1,13))


def test_bifacial_candidate_data_is_candidate_specific_and_sourced():
    modules = pd.read_csv(ROOT / "data/raw/module_candidate_master.csv").set_index("module_id")
    assert modules.loc["MOD_TOPCON_CANADIAN_CS62_66TB_620H", "bifaciality_factor"] == 0.80
    assert modules.loc["MOD_HJT_CANADIAN_CS62_66HB_635H", "bifaciality_factor"] == 0.85
    assert modules.loc["MOD_TOPCON_JASOLAR_JAM72D42_640_LB", "bifaciality_factor"] == 0.80
    assert modules.loc["MOD_TOPCON_TRINA_TSM_NEG21C20_700", "bifaciality_factor"] == 0.80
    assert modules.loc["MOD_PERC_LONGI_LR5_72HPH_550M", "bifaciality_factor"] == 0.0


def _strong_pair(*, measured: bool, geometry: str = "project_design_or_measured") -> tuple[pd.DataFrame, str]:
    evidence = "module_specific_measured_matrix" if measured else "datasheet_fit_crystalline_silicon_fallback"
    model = "iec61853_measured_matrix" if measured else "cec_single_diode_datasheet_fit"
    rows = pd.DataFrame([
        {"module_id":"A","manufacturer":"A","model":"A","technology_label":"TOPCon","annual_yield_kwh_kwp":2300.0,"annual_dc_specific_energy_broadband_kwh_kwp":2300.0,"annual_dc_specific_energy_spectral_sensitivity_kwh_kwp":2300.0,"lifetime_energy_common_degradation_scenario_kwh_kwp":54050.0,"lifetime_energy_warranty_scenario_kwh_kwp":54050.0,"decision_eligible":True,"electrical_model":model,"model_evidence_level":evidence,"thermal_evidence_level":"candidate_specific_validated"},
        {"module_id":"B","manufacturer":"B","model":"B","technology_label":"HJT","annual_yield_kwh_kwp":1700.0,"annual_dc_specific_energy_broadband_kwh_kwp":1700.0,"annual_dc_specific_energy_spectral_sensitivity_kwh_kwp":1700.0,"lifetime_energy_common_degradation_scenario_kwh_kwp":39950.0,"lifetime_energy_warranty_scenario_kwh_kwp":39950.0,"decision_eligible":True,"electrical_model":model,"model_evidence_level":evidence,"thermal_evidence_level":"candidate_specific_validated"},
    ])
    return rows, geometry


def _two_year_scenarios() -> pd.DataFrame:
    return pd.DataFrame({"A": [2250.0, 2350.0], "B": [1660.0, 1740.0]}, index=[2019, 2020])


def test_datasheet_fit_cannot_receive_robust_wording_even_with_large_gap():
    rows, geometry = _strong_pair(measured=False)
    d = recommendation_decision(
        rows,
        resource_disagreement_pct=1.0,
        resource_crosscheck_status="ok",
        geometry_confidence=geometry,
        annual_scenarios=_two_year_scenarios(),
        shared_resource_sigma_pct=0.5,
        n_samples=5000,
    )
    assert d["robust_evidence_ready"] is False
    assert d["decision_status"] != "Robust"


def test_measured_electrical_evidence_plus_project_geometry_can_unlock_robust_wording():
    rows, geometry = _strong_pair(measured=True)
    d = recommendation_decision(
        rows,
        resource_disagreement_pct=1.0,
        resource_crosscheck_status="ok",
        geometry_confidence=geometry,
        annual_scenarios=_two_year_scenarios(),
        shared_resource_sigma_pct=0.5,
        n_samples=5000,
    )
    assert d["robust_evidence_ready"] is True
    assert d["geometry_ready_for_robust"] is True
    assert d["decision_status"] == "Robust"
    assert d["recommended_module_id"] == "A"


def test_screening_geometry_prevents_robust_wording():
    rows, _ = _strong_pair(measured=True)
    d = recommendation_decision(
        rows,
        resource_disagreement_pct=1.0,
        resource_crosscheck_status="ok",
        geometry_confidence="screening_assumptions",
        annual_scenarios=_two_year_scenarios(),
        shared_resource_sigma_pct=0.5,
        n_samples=5000,
    )
    assert d["geometry_ready_for_robust"] is False
    assert d["decision_status"] != "Robust"


def test_invalid_bifaciality_fails_closed_on_uploaded_candidate():
    from src.module_offer_io import normalize_module_offer_dataframe
    base = pd.read_csv(ROOT / "data/raw/module_candidate_master.csv").iloc[[0]].copy()
    base["bifaciality_factor"] = 1.5
    base["bifaciality_source"] = "manufacturer_datasheet"
    try:
        normalize_module_offer_dataframe(base)
    except ValueError as exc:
        assert "bifaciality_factor" in str(exc)
    else:
        raise AssertionError("Invalid bifaciality must fail closed")


def test_generic_thermal_proxy_prevents_robust_wording():
    rows, geometry = _strong_pair(measured=True)
    rows["thermal_evidence_level"] = "generic_construction_proxy"
    d = recommendation_decision(
        rows, resource_disagreement_pct=1.0, resource_crosscheck_status="ok",
        geometry_confidence=geometry, annual_scenarios=_two_year_scenarios(), n_samples=5000
    )
    assert d["robust_thermal_ready"] is False
    assert d["decision_status"] != "Robust"


def test_single_year_prior_cannot_receive_robust_wording():
    rows, geometry = _strong_pair(measured=True)
    d = recommendation_decision(
        rows, resource_disagreement_pct=1.0, resource_crosscheck_status="ok",
        geometry_confidence=geometry, annual_scenarios=None, shared_resource_sigma_pct=0.5, n_samples=5000
    )
    assert d["resource_history_ready_for_robust"] is False
    assert d["decision_status"] != "Robust"


def test_decision_material_rear_gain_stays_below_robust_until_rear_poa_is_validated():
    rows, _ = _strong_pair(measured=True)
    rows["rear_irradiance_model_active"] = True
    rows["bifaciality_factor"] = 0.8
    rows["bifacial_rear_gain_pct"] = [6.0, 5.5]
    d = recommendation_decision(
        rows, resource_disagreement_pct=1.0, resource_crosscheck_status="ok",
        geometry_confidence="project_design", annual_scenarios=_two_year_scenarios(), n_samples=5000
    )
    assert d["robust_rear_ready"] is False
    assert d["decision_status"] != "Robust"

    d2 = recommendation_decision(
        rows, resource_disagreement_pct=1.0, resource_crosscheck_status="ok",
        geometry_confidence="measured", annual_scenarios=_two_year_scenarios(), n_samples=5000
    )
    assert d2["robust_rear_ready"] is False
    assert d2["decision_status"] != "Robust"
    assert "rear" in d2["robust_rear_reason"].lower()
