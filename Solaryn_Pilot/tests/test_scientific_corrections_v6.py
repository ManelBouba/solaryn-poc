import numpy as np
import pandas as pd

from src.lifetime_engine import degradation_parameters_for_candidate
from src.uncertainty_engine import (
    candidate_model_sigma_pct,
    compare_candidates_correlated,
    compare_lifetime_candidates_correlated,
)
from src.site_qualification import qualification_for_candidate
from src.decision_trace import build_candidate_trace


def test_screening_uncertainty_does_not_depend_on_evidence_grade_or_technology_label():
    hjt = {"module_id": "HJT", "technology_label": "HJT", "evidence_grade": "A", "model_evidence_level": "measured"}
    topcon = {"module_id": "TOP", "technology_label": "TOPCon", "evidence_grade": "D", "model_evidence_level": "fallback"}
    assert candidate_model_sigma_pct(hjt, 4.25) == 4.25
    assert candidate_model_sigma_pct(topcon, 4.25) == 4.25


def test_empirical_model_residual_overrides_common_screening_width():
    row = {"validated_model_sigma_pct": 1.7, "screening_model_sigma_pct": 5.0}
    assert candidate_model_sigma_pct(row, 5.0) == 1.7


def test_correlated_annual_comparison_does_not_manufacture_winner_for_equal_candidates():
    frame = pd.DataFrame([
        {"module_id": "A", "annual_yield_kwh_kwp": 1500.0, "screening_model_sigma_pct": 3.0},
        {"module_id": "B", "annual_yield_kwh_kwp": 1500.0, "screening_model_sigma_pct": 3.0},
    ])
    res = compare_candidates_correlated(frame, n=12000, seed=13, shared_resource_sigma_pct=4.0)
    pa = res["probability_of_best_pct"]["A"]
    pb = res["probability_of_best_pct"]["B"]
    assert abs(pa - 50.0) < 2.0
    assert abs(pb - 50.0) < 2.0


def test_degradation_fallback_is_common_not_technology_specific():
    for tech in ["HJT", "TOPCon", "PERC", "CdTe", "IBC"]:
        d = degradation_parameters_for_candidate(
            {"technology_label": tech, "annual_warranty_degradation_pct_year": 0.25},
            common_mean_pct_year=0.50,
            common_sigma_pct_year=0.18,
        )
        assert d["mean_pct_year"] == 0.50
        assert d["sigma_pct_year"] == 0.18
        assert d["basis"] == "common_project_prior_shared_across_candidates"


def test_validated_field_degradation_can_differentiate_product():
    d = degradation_parameters_for_candidate(
        {
            "technology_label": "TOPCon",
            "degradation_evidence_status": "field_validated",
            "field_validated_degradation_pct_year": 0.32,
            "field_validated_degradation_sigma_pct_year": 0.06,
        },
        common_mean_pct_year=0.50,
        common_sigma_pct_year=0.20,
    )
    assert d["mean_pct_year"] == 0.32
    assert d["sigma_pct_year"] == 0.06
    assert d["basis"] == "product_specific_field_evidence"


def test_lifetime_mc_uses_shared_degradation_prior_when_evidence_missing():
    frame = pd.DataFrame([
        {"module_id": "HJT", "annual_yield_kwh_kwp": 1600.0, "technology_label": "HJT", "screening_model_sigma_pct": 2.5},
        {"module_id": "TOP", "annual_yield_kwh_kwp": 1600.0, "technology_label": "TOPCon", "screening_model_sigma_pct": 2.5},
    ])
    res = compare_lifetime_candidates_correlated(frame, n=12000, seed=19, years=25)
    assert res["degradation_basis"]["HJT"] == "common_project_prior_shared_across_candidates"
    assert res["degradation_basis"]["TOP"] == "common_project_prior_shared_across_candidates"
    assert abs(res["probability_of_best_pct"]["HJT"] - 50.0) < 2.0


def test_lifetime_mc_honors_only_explicit_validated_field_degradation():
    frame = pd.DataFrame([
        {
            "module_id": "A", "annual_yield_kwh_kwp": 1500.0, "screening_model_sigma_pct": 0.2,
            "degradation_evidence_status": "field_validated", "field_validated_degradation_pct_year": 0.25,
            "field_validated_degradation_sigma_pct_year": 0.03,
        },
        {
            "module_id": "B", "annual_yield_kwh_kwp": 1500.0, "screening_model_sigma_pct": 0.2,
        },
    ])
    res = compare_lifetime_candidates_correlated(
        frame, n=10000, seed=23, years=25,
        common_degradation_mean_pct_year=0.60,
        common_degradation_sigma_pct_year=0.03,
    )
    assert res["degradation_basis"]["A"] == "product_specific_field_evidence"
    assert res["degradation_basis"]["B"] == "common_project_prior_shared_across_candidates"
    assert res["probability_of_best_pct"]["A"] > 95.0


def _weather():
    idx = pd.date_range("2026-01-01", periods=4, freq="h", tz="UTC")
    return pd.DataFrame({
        "poa_w_m2": [0, 500, 700, 0],
        "relative_humidity_pct": [90, 90, 90, 90],
        "temp_air_c": [20, 30, 32, 20],
        "rainfall_mm_hour": [0, 0, 0, 0],
    }, index=idx)


def test_missing_qualification_evidence_is_conditional_by_default_not_automatic_fail():
    q = qualification_for_candidate(
        {"certifications": "IEC 61215"},
        {"p98_module_temperature_c_all_hours": 75.0},
        _weather(),
        {"salinity_stress": "coastal", "hard_qualification_gates": False},
    )
    assert q.status == "conditional"
    assert "high_temperature_qualification" in q.missing
    assert "IEC_61701_salt_mist" in q.missing


def test_decision_trace_uses_all_hours_t98_and_exposes_lifetime_evidence_basis():
    trace = build_candidate_trace(
        {"latitude": 1, "longitude": 2, "tilt_deg": 20, "azimuth_deg": 180, "albedo": 0.2, "salinity_stress": "auto"},
        {
            "p98_module_temperature_c_all_hours": 74.0,
            "p98_module_temperature_c_daylight": 80.0,
            "lifetime_p50_kwh_kwp": 30000,
            "lifetime_p90_kwh_kwp": 28000,
            "degradation_evidence_basis": "common_project_prior_shared_across_candidates",
        },
        {}, {}, {},
    )
    assert trace["climate_stress"]["t98_module_c"] == 74.0
    assert trace["lifetime"]["p50_kwh_kwp"] == 30000
    assert trace["lifetime"]["degradation_evidence_basis"] == "common_project_prior_shared_across_candidates"
