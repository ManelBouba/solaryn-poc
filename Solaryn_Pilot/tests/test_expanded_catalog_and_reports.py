from pathlib import Path
import pandas as pd

from src.module_iv_engine import validate_module_candidates
from src.epc_report import build_epc_html_report
from src.validation_report import build_real_world_validation_report

ROOT = Path(__file__).resolve().parents[1]


def test_commercial_catalog_is_expanded_and_validated():
    modules = pd.read_csv(ROOT / "data/raw/module_candidate_master.csv")
    validate_module_candidates(modules)
    assert len(modules) >= 10
    labels = set(modules["technology_label"].astype(str))
    assert "TOPCon Bifacial" in labels
    assert "HJT Bifacial" in labels
    assert "HPBC 2.0 / Back Contact" in labels
    assert "IBC / Back Contact" in labels
    assert "CdTe Thin Film" in labels


def test_real_world_validation_report_has_measured_metrics_and_scope_boundary():
    html, summary, monthly = build_real_world_validation_report(ROOT)
    assert summary["status"] == "PASS_EXTERNAL_MEASURED_LAYER"
    assert summary["retained_rows"] == 28286
    assert summary["full_decision_engine_validated"] is False
    assert len(monthly) == 12
    assert "Real-World Validation Report" in html
    assert "does <strong>not</strong> validate the full" in html


def test_executive_report_renders_embedded_charts():
    modules = pd.read_csv(ROOT / "data/raw/module_candidate_master.csv").iloc[:2].copy()
    results = pd.DataFrame([
        {"module_id": modules.iloc[0].module_id, "manufacturer": modules.iloc[0].manufacturer, "model": modules.iloc[0].model, "technology_label": modules.iloc[0].technology_label,
         "annual_yield_kwh_kwp": 1800.0, "annual_dc_specific_energy_broadband_kwh_kwp": 1800.0, "annual_project_dc_energy_mwh": 180000.0,
         "lifetime_energy_common_degradation_scenario_kwh_kwp": 42000.0, "p95_cell_temperature_c_daylight": 62.0, "model_evidence_level": "datasheet_fit_crystalline_silicon_fallback", "decision_eligible": True},
        {"module_id": modules.iloc[1].module_id, "manufacturer": modules.iloc[1].manufacturer, "model": modules.iloc[1].model, "technology_label": modules.iloc[1].technology_label,
         "annual_yield_kwh_kwp": 1780.0, "annual_dc_specific_energy_broadband_kwh_kwp": 1780.0, "annual_project_dc_energy_mwh": 178000.0,
         "lifetime_energy_common_degradation_scenario_kwh_kwp": 41500.0, "p95_cell_temperature_c_daylight": 63.0, "model_evidence_level": "datasheet_fit_crystalline_silicon_fallback", "decision_eligible": True},
    ])
    stress = pd.DataFrame([
        {"module_id": modules.iloc[0].module_id,"manufacturer":modules.iloc[0].manufacturer,"model":modules.iloc[0].model,"hot_cell_hours_gt_65c":30,"hot_humid_hours_rh85_t40":2,"mean_daily_cell_temp_range_c":25,"days_cell_temp_range_gt_30c":8},
        {"module_id": modules.iloc[1].module_id,"manufacturer":modules.iloc[1].manufacturer,"model":modules.iloc[1].model,"hot_cell_hours_gt_65c":35,"hot_humid_hours_rh85_t40":3,"mean_daily_cell_temp_range_c":26,"days_cell_temp_range_gt_30c":9},
    ])
    decision={"decision_status":"Probable","technical_leader_module_id":modules.iloc[0].module_id,"technical_leader_manufacturer":modules.iloc[0].manufacturer,"technical_leader_model":modules.iloc[0].model,"headline":"Technical leader test.","probability_of_best_pct":72.0,"expected_regret_pct":0.4,"annual_lead_over_second_pct":1.1,"probability_by_candidate_pct":{modules.iloc[0].module_id:72.0,modules.iloc[1].module_id:28.0},"evidence_complete_for_all_selected_candidates":True,"decision_ineligible_module_ids":[],"next_evidence_request":"Acquire candidate-specific P(G,T)."}
    hourly = pd.DataFrame({"timestamp":pd.date_range("2020-01-01", periods=48, freq="h").tolist()*2,"module_id":[modules.iloc[0].module_id]*48+[modules.iloc[1].module_id]*48,"specific_power_kw_per_kwp":[0.4]*48+[0.38]*48})
    html=build_epc_html_report({"latitude":50.8,"longitude":4.35},{"project_name":"Test City","reference_year":2020,"system_size_mw":100,"tilt_deg":25,"azimuth_deg":180,"soiling_loss_pct":2,"common_degradation_pct_year":0.5,"project_segment":"utility"},results,decision,modules,stress,hourly=hourly)
    assert "Executive Recommendation Report" in html
    assert html.count("<svg") >= 4
    assert "Probability of best" in html
    assert "Seasonal production profile" in html
