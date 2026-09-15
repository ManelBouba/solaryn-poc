import pandas as pd
from src.climate_physics import generate_representative_weather, simulate_site_technology
from src.recommendation_engine import rank_technologies, project_decision_summary


def _site():
    return pd.Series({
        "latitude":32.2,"ghi_kwh_m2_year":2059,"avg_temp_c":19.0,"max_temp_c":46.7,
        "wind_speed_m_s":2.8,"humidity_pct":62.0,"rainfall_mm_year":190,
        "soiling_loss_assumption_pct":2.0,"degradation_scenario_pct_year":0.5,
    })

def _tech(tid,name,family,gamma):
    return {
      "technology_id":tid,"technology_name":name,"family":family,"subfamily":"",
      "TRL_level":9,"commercialization_status":"commercial","source_quality":"literature_range",
      "source_url":"","temp_coefficient_pct_c":gamma,"baseline_degradation_pct_year":0.5,
      "efficiency_commercial_percent":20,"module_cost_usd_w":0.25,"bankability_score":90,"maturity_score":90,
      "humidity_resilience_score":3,"moisture_sensitivity_score":2,"uv_stability_score":8,
      "ion_migration_score":0,"phase_stability_score":8,
      "electron_mobility_cm2Vs":1000,"hole_mobility_cm2Vs":400,"carrier_lifetime_ns":100000,
      "absorption_coefficient_cm-1":10000,"absorber_thickness_um":160,"bandgap_eV":1.12,
      "voc_typical_V":0.68,"defect_density_cm-3":1e10,
    }

def test_multiphysics_returns_explicit_evidence_bases():
    site=_site(); tech=pd.Series(_tech("A","pc-Si","Silicon",-0.39))
    out=simulate_site_technology(site,tech,generate_representative_weather(site))
    assert "electrical_model_basis" in out
    assert out["electrical_model_measured"] is False
    assert "thermal_model_basis" in out
    assert "soiling_model_basis" in out

def test_cross_family_generic_models_withhold_recommendation():
    site=_site(); df=pd.DataFrame([_tech("A","pc-Si","Silicon",-0.39),_tech("B","CdTe","Thin Film",-0.28)])
    ranking=rank_technologies(site,df,weather=generate_representative_weather(site),objective="Lifetime energy")
    summary=project_decision_summary(ranking)
    assert summary["cross_family_comparison"] is True
    assert summary["decision_eligible"] is False
    assert "withheld" in summary["scientific_status"]
