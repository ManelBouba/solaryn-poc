from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.module_iv_engine import validate_module_candidates
from src.lifetime_engine import warranty_retention_curve, lifetime_energy_from_warranty_scenario
from src.epc_decision import epc_energy_decision
from src.economics_engine import switching_point_table

ROOT = Path(__file__).resolve().parents[1]


def _modules():
    return pd.read_csv(ROOT / "data/raw/module_candidate_master.csv")


def test_seed_modules_link_back_to_original_solaryn_database():
    modules = _modules()
    tech = pd.read_csv(ROOT / "data/raw/technology_master.csv")
    assert len(tech) == 30
    assert set(modules["technology_id"]).issubset(set(tech["technology_id"]))
    assert {"Mono PERC", "TOPCon", "HJT", "CdTe Thin Film"}.issubset(set(modules["technology_label"]))
    assert {"TOPCon Bifacial", "HJT Bifacial", "HPBC 2.0 / Back Contact", "IBC / Back Contact"}.issubset(set(modules["technology_label"]))


def test_seed_module_datasheet_rows_are_internally_consistent():
    modules = _modules()
    validate_module_candidates(modules)
    residual = (modules["vmp_v"] * modules["imp_a"] - modules["pmax_w"]).abs() / modules["pmax_w"]
    assert (residual < 0.02).all()
    assert (modules["vmp_v"] < modules["voc_v"]).all()
    assert (modules["imp_a"] < modules["isc_a"]).all()
    assert modules["quote_usd_w"].isna().all()  # no invented market price


def test_bad_stc_point_is_rejected_before_nonlinear_fit():
    bad = _modules().iloc[[0]].copy()
    bad.loc[bad.index[0], "vmp_v"] = bad.iloc[0]["voc_v"] + 1
    with pytest.raises(ValueError, match="Vmp < Voc"):
        validate_module_candidates(bad)


def test_warranty_is_used_as_scenario_not_flat_annual_energy_floor():
    curve = warranty_retention_curve(98.0, 0.25, years=25)
    assert curve.iloc[0]["start_of_year_retention_pct"] == pytest.approx(100.0)
    assert curve.iloc[0]["end_of_year_warranty_retention_pct"] == pytest.approx(98.0)
    assert curve.iloc[0]["annual_energy_retention_scenario_pct"] == pytest.approx(99.0)
    assert curve.iloc[-1]["end_of_year_warranty_retention_pct"] == pytest.approx(92.0)

    result = lifetime_energy_from_warranty_scenario(1800.0, 98.0, 0.25, years=25)
    assert result["lifetime_energy_warranty_scenario_kwh_kwp"] < 1800.0 * 25
    assert "not_energy_guarantee" in result["basis"]


def test_epc_decision_refuses_winner_when_annual_and_lifetime_leaders_disagree():
    df = pd.DataFrame([
        {"module_id":"A", "manufacturer":"A", "model":"A1", "annual_yield_kwh_kwp":1900.0, "lifetime_energy_warranty_scenario_kwh_kwp":43000.0},
        {"module_id":"B", "manufacturer":"B", "model":"B1", "annual_yield_kwh_kwp":1850.0, "lifetime_energy_warranty_scenario_kwh_kwp":44000.0},
    ])
    if "decision_eligible" not in df:
        df["decision_eligible"] = True  # Isolate scenario stability from the evidence gate.
    d = epc_energy_decision(df, minimum_separation_pct=1.0)
    assert d["winner_module_id"] is None
    assert d["status"] == "scenario_sensitive"


def test_epc_decision_accepts_stable_leader_only_with_visible_separation():
    df = pd.DataFrame([
        {"module_id":"A", "manufacturer":"A", "model":"A1", "annual_yield_kwh_kwp":1900.0, "lifetime_energy_warranty_scenario_kwh_kwp":45000.0},
        {"module_id":"B", "manufacturer":"B", "model":"B1", "annual_yield_kwh_kwp":1800.0, "lifetime_energy_warranty_scenario_kwh_kwp":42000.0},
    ])
    if "decision_eligible" not in df:
        df["decision_eligible"] = True  # Isolate scenario stability from the evidence gate.
    d = epc_energy_decision(df, minimum_separation_pct=1.0)
    assert d["winner_module_id"] == "A"
    assert d["annual_lead_over_second_pct"] > 1.0
    assert d["lifetime_lead_over_second_pct"] > 1.0
    assert d["claim_scope"] == "deterministic_scenario_stability_policy_not_confidence_interval"


def test_switching_point_equation_uses_real_quote_and_area_bos():
    modules = pd.DataFrame([
        {
            "module_id":"BASE", "manufacturer":"Base", "model":"B", "module_area_m2":2.5, "pmax_w":500.0,
            "first_year_retention_pct":98.0, "annual_warranty_degradation_pct_year":0.5, "quote_usd_w":0.20,
        },
        {
            "module_id":"ALT", "manufacturer":"Alt", "model":"A", "module_area_m2":2.4, "pmax_w":500.0,
            "first_year_retention_pct":99.0, "annual_warranty_degradation_pct_year":0.4, "quote_usd_w":0.23,
        },
    ])
    results = pd.DataFrame([
        {"module_id":"BASE", "annual_yield_kwh_kwp":1800.0},
        {"module_id":"ALT", "annual_yield_kwh_kwp":1850.0},
    ])
    if "decision_eligible" not in results:
        results["decision_eligible"] = True  # Explicit eligibility for the equation fixture.
    out = switching_point_table(
        results, modules, "BASE", energy_value_usd_kwh=0.05,
        discount_rate_pct=7.0, area_bos_usd_m2=20.0, years=25,
    ).set_index("module_id")
    assert out.loc["BASE", "indifference_module_price_usd_w"] == pytest.approx(0.20)
    assert out.loc["ALT", "indifference_module_price_usd_w"] > 0.20
    assert out.loc["ALT", "economic_model_scope"] == "discounted_energy_value_plus_area_sensitive_BOS_switching_threshold"


def test_cec_fit_converts_datasheet_temperature_coefficients_to_pvlib_units(monkeypatch):
    import types
    import src.module_iv_engine as eng

    row = _modules().iloc[0].copy()
    captured = {}

    def fake_fit_cec_sam(**kwargs):
        captured.update(kwargs)
        return (9.0, 1e-10, 0.2, 500.0, 1.8, 1.0)

    fake_pvlib = types.SimpleNamespace(
        ivtools=types.SimpleNamespace(
            sdm=types.SimpleNamespace(fit_cec_sam=fake_fit_cec_sam)
        )
    )
    monkeypatch.setattr(eng, "pvlib", fake_pvlib)
    out = eng.fit_cec_from_datasheet(row)

    expected_alpha = float(row["isc_a"]) * float(row["alpha_isc_pct_c"]) / 100.0
    expected_beta = float(row["voc_v"]) * float(row["beta_voc_pct_c"]) / 100.0
    assert captured["alpha_sc"] == pytest.approx(expected_alpha)
    assert captured["beta_voc"] == pytest.approx(expected_beta)
    assert captured["gamma_pmp"] == pytest.approx(float(row["gamma_pmax_pct_c"]))
    assert captured["cells_in_series"] == int(row["cells_in_series"])
    assert out["alpha_sc_A_C"] == pytest.approx(expected_alpha)
    assert out["beta_voc_V_C"] == pytest.approx(expected_beta)


def test_epc_decision_refuses_winner_when_spectral_proxy_flips_leader():
    df = pd.DataFrame([
        {
            "module_id":"A", "manufacturer":"A", "model":"A1",
            "annual_dc_specific_energy_no_spectral_kwh_kwp":1900.0,
            "annual_yield_kwh_kwp":1840.0,
            "lifetime_energy_warranty_scenario_kwh_kwp":43000.0,
        },
        {
            "module_id":"B", "manufacturer":"B", "model":"B1",
            "annual_dc_specific_energy_no_spectral_kwh_kwp":1850.0,
            "annual_yield_kwh_kwp":1900.0,
            "lifetime_energy_warranty_scenario_kwh_kwp":44500.0,
        },
    ])
    if "decision_eligible" not in df:
        df["decision_eligible"] = True  # Isolate scenario stability from the evidence gate.
    d = epc_energy_decision(df, minimum_separation_pct=1.0)
    assert d["winner_module_id"] is None
    assert d["broadband_leader_module_id"] == "A"
    assert d["annual_leader_module_id"] == "B"
    assert d["spectral_proxy_policy"] == "unsupported_spectral_differentiation_cannot_change_primary_decision"
