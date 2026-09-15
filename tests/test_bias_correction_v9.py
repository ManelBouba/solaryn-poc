from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.evidence_policy import (
    electrical_model_policy,
    spectral_evidence_policy,
    project_segment_compatible,
)
from src.iec61853_engine import (
    validate_iec61853_matrix,
    interpolate_iec61853_pmax,
)
from src.lifetime_engine import add_lifetime_metrics
from src.economics_engine import switching_point_table
from src.epc_decision import epc_energy_decision

ROOT = Path(__file__).resolve().parents[1]


def _synthetic_matrix(kind: str) -> pd.DataFrame:
    """Synthetic software fixture only; not measured PV validation data.

    A is deliberately stronger at low irradiance and more temperature-sensitive.
    B is deliberately weaker at low irradiance and less temperature-sensitive.
    Both are normalized to the same 500 W STC Pmax.
    """
    rows = []
    for g in [100, 200, 400, 600, 800, 1000, 1100]:
        for t in [15, 25, 50, 75]:
            x = g / 1000.0
            if kind == "A":
                low_light = 1.0 + 0.045 * (1.0 - min(x, 1.0))
                thermal = 1.0 - 0.0040 * (t - 25.0)
            elif kind == "B":
                low_light = 1.0 - 0.055 * (1.0 - min(x, 1.0))
                thermal = 1.0 - 0.0024 * (t - 25.0)
            else:
                raise ValueError(kind)
            # Keep exact shared STC anchor.
            p = 500.0 * x * low_light * thermal
            if g == 1000 and t == 25:
                p = 500.0
            rows.append({
                "irradiance_w_m2": float(g),
                "module_temperature_c": float(t),
                "pmax_w": max(0.0, p),
            })
    return pd.DataFrame(rows)


def _module_row(celltype: str = "monoSi") -> pd.Series:
    return pd.Series({
        "module_id": "M",
        "cec_celltype": celltype,
        "pmax_w": 500.0,
        "project_segment": "all",
        "spectral_evidence_level": "technology_class_proxy",
        "iec61853_matrix_file": "",
    })


def test_iec61853_matrix_validates_span_and_stc_anchor():
    matrix = _synthetic_matrix("A")
    val = validate_iec61853_matrix(matrix, module_pmax_w=500.0)
    assert val.measured_points == 28
    assert val.has_stc_anchor
    assert val.stc_relative_error_pct == pytest.approx(0.0)
    assert val.irradiance_min_w_m2 == 100.0
    assert val.irradiance_max_w_m2 == 1100.0
    assert val.temperature_min_c == 15.0
    assert val.temperature_max_c == 75.0


def test_iec61853_matrix_rejects_duplicate_and_bad_stc_anchor():
    matrix = _synthetic_matrix("A")
    duplicate = pd.concat([matrix, matrix.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        validate_iec61853_matrix(duplicate, module_pmax_w=500.0)

    bad = matrix.copy()
    bad.loc[(bad.irradiance_w_m2 == 1000) & (bad.module_temperature_c == 25), "pmax_w"] = 450.0
    with pytest.raises(ValueError, match="differs from module nameplate"):
        validate_iec61853_matrix(bad, module_pmax_w=500.0)


def test_matrix_interpolation_reproduces_measured_anchor_points():
    matrix = _synthetic_matrix("A")
    sample = matrix.sample(10, random_state=7).reset_index(drop=True)
    p, diagnostics = interpolate_iec61853_pmax(
        matrix, sample["irradiance_w_m2"], sample["module_temperature_c"]
    )
    assert np.allclose(p.to_numpy(), sample["pmax_w"].to_numpy(), rtol=1e-10, atol=1e-8)
    assert diagnostics["matrix_irradiance_extrapolation_fraction_pct"] == pytest.approx(0.0)
    assert diagnostics["matrix_temperature_extrapolation_fraction_pct"] == pytest.approx(0.0)


def test_bias_corrected_physics_surface_can_flip_leader_between_climates_without_weights():
    a = _synthetic_matrix("A")
    b = _synthetic_matrix("B")

    # Synthetic cool/diffuse-like operating distribution (software behavior test only).
    g_cool = pd.Series([200, 300, 400, 500, 600] * 100, dtype=float)
    t_cool = pd.Series([15, 18, 20, 23, 25] * 100, dtype=float)
    pa_cool, _ = interpolate_iec61853_pmax(a, g_cool, t_cool)
    pb_cool, _ = interpolate_iec61853_pmax(b, g_cool, t_cool)

    # Synthetic hot/arid-like operating distribution.
    g_hot = pd.Series([800, 900, 1000, 1050, 1100] * 100, dtype=float)
    t_hot = pd.Series([50, 55, 60, 65, 70] * 100, dtype=float)
    pa_hot, _ = interpolate_iec61853_pmax(a, g_hot, t_hot)
    pb_hot, _ = interpolate_iec61853_pmax(b, g_hot, t_hot)

    assert pa_cool.sum() > pb_cool.sum(), "Module A should lead in the synthetic cool/low-G distribution."
    assert pb_hot.sum() > pa_hot.sum(), "Module B should lead in the synthetic hot/high-G distribution."


def test_electrical_model_policy_fails_closed_for_non_csi_without_matrix(tmp_path):
    csi = _module_row("monoSi")
    csi_policy = electrical_model_policy(csi, tmp_path)
    assert csi_policy["decision_eligible"] is True
    assert csi_policy["electrical_model"] == "cec_single_diode_datasheet_fit"

    cdte = _module_row("cdte")
    cdte_policy = electrical_model_policy(cdte, tmp_path)
    assert cdte_policy["decision_eligible"] is False
    assert cdte_policy["electrical_model"] == "cec_single_diode_exploratory_only"


def test_module_specific_matrix_overrides_generic_model_class(tmp_path):
    matrix_path = tmp_path / "module_matrix.csv"
    _synthetic_matrix("B").to_csv(matrix_path, index=False)
    cdte = _module_row("cdte")
    cdte["iec61853_matrix_file"] = matrix_path.name
    policy = electrical_model_policy(cdte, tmp_path)
    assert policy["decision_eligible"] is True
    assert policy["electrical_model"] == "iec61853_module_specific_matrix"
    assert policy["model_evidence_level"] == "module_specific_measured_matrix"


def test_technology_class_spectral_proxy_is_sensitivity_only():
    row = _module_row("monoSi")
    policy = spectral_evidence_policy(row)
    assert policy["spectral_decision_eligible"] is False
    assert policy["spectral_policy"] == "technology_class_proxy_is_sensitivity_only"


def test_declaring_eqe_alone_does_not_enable_spectral_decision_without_time_resolved_spectral_engine():
    row = _module_row("monoSi")
    row["spectral_evidence_level"] = "module_specific_eqe"
    policy = spectral_evidence_policy(row)
    assert policy["spectral_decision_eligible"] is False
    assert "not_yet_implemented" in policy["spectral_policy"]


def test_common_degradation_primary_preserves_annual_ranking_while_warranty_is_separate_sensitivity():
    results = pd.DataFrame([
        {"module_id": "A", "annual_yield_kwh_kwp": 1800.0},
        {"module_id": "B", "annual_yield_kwh_kwp": 1780.0},
    ])
    modules = pd.DataFrame([
        {"module_id": "A", "first_year_retention_pct": 97.0, "annual_warranty_degradation_pct_year": 0.70},
        {"module_id": "B", "first_year_retention_pct": 100.0, "annual_warranty_degradation_pct_year": 0.05},
    ])
    out = add_lifetime_metrics(results, modules, years=25, common_degradation_pct_year=0.50)
    annual_leader = out.sort_values("annual_yield_kwh_kwp", ascending=False).iloc[0]["module_id"]
    common_leader = out.sort_values("lifetime_energy_common_degradation_scenario_kwh_kwp", ascending=False).iloc[0]["module_id"]
    warranty_leader = out.sort_values("lifetime_energy_warranty_scenario_kwh_kwp", ascending=False).iloc[0]["module_id"]
    assert annual_leader == "A"
    assert common_leader == "A"
    assert warranty_leader == "B"


def test_uncertainty_guardrail_blocks_small_numeric_advantage():
    df = pd.DataFrame([
        {
            "module_id": "A", "manufacturer": "A", "model": "A1", "decision_eligible": True,
            "annual_yield_kwh_kwp": 1818.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1818.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 43000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 43000.0,
        },
        {
            "module_id": "B", "manufacturer": "B", "model": "B1", "decision_eligible": True,
            "annual_yield_kwh_kwp": 1800.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1800.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 42575.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 42575.0,
        },
    ])
    d = epc_energy_decision(df, minimum_separation_pct=0.5, uncertainty_guardrail_pct=2.0)
    assert d["winner_module_id"] is None
    assert d["status"] == "no_robust_winner_under_uncertainty_guardrail"
    assert d["required_decision_gap_pct"] == pytest.approx(2.0)


def test_decision_blocks_cross_technology_winner_when_model_evidence_incomplete():
    df = pd.DataFrame([
        {
            "module_id": "CSI", "manufacturer": "C", "model": "C1", "decision_eligible": True,
            "annual_yield_kwh_kwp": 1900.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1900.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 45000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 45000.0,
        },
        {
            "module_id": "CDTE", "manufacturer": "D", "model": "D1", "decision_eligible": False,
            "annual_yield_kwh_kwp": 1800.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1800.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 42000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 42000.0,
        },
    ])
    d = epc_energy_decision(df, uncertainty_guardrail_pct=2.0)
    assert d["winner_module_id"] is None
    assert d["status"] == "incomplete_cross_technology_model_evidence"
    assert d["decision_ineligible_module_ids"] == ["CDTE"]


def test_spectral_proxy_flip_is_reported_but_does_not_create_primary_winner():
    df = pd.DataFrame([
        {
            "module_id": "A", "manufacturer": "A", "model": "A1", "decision_eligible": True,
            "annual_yield_kwh_kwp": 1900.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1900.0,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": 1850.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 45000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 45000.0,
        },
        {
            "module_id": "B", "manufacturer": "B", "model": "B1", "decision_eligible": True,
            "annual_yield_kwh_kwp": 1820.0,
            "annual_dc_specific_energy_broadband_kwh_kwp": 1820.0,
            "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": 1920.0,
            "lifetime_energy_common_degradation_scenario_kwh_kwp": 43000.0,
            "lifetime_energy_warranty_scenario_kwh_kwp": 43000.0,
        },
    ])
    d = epc_energy_decision(df, uncertainty_guardrail_pct=2.0)
    assert d["winner_module_id"] == "A"
    assert d["spectral_sensitivity_changes_leader"] is True
    assert d["spectral_sensitivity_leader_module_id"] == "B"


def test_switching_point_primary_uses_common_degradation_not_warranty_to_manufacture_premium():
    modules = pd.DataFrame([
        {
            "module_id": "BASE", "manufacturer": "Base", "model": "B", "module_area_m2": 2.5, "pmax_w": 500.0,
            "first_year_retention_pct": 97.0, "annual_warranty_degradation_pct_year": 0.9, "quote_usd_w": 0.20,
        },
        {
            "module_id": "ALT", "manufacturer": "Alt", "model": "A", "module_area_m2": 2.5, "pmax_w": 500.0,
            "first_year_retention_pct": 100.0, "annual_warranty_degradation_pct_year": 0.05, "quote_usd_w": 0.20,
        },
    ])
    results = pd.DataFrame([
        {"module_id": "BASE", "annual_yield_kwh_kwp": 1800.0},
        {"module_id": "ALT", "annual_yield_kwh_kwp": 1800.0},
    ])
    out = switching_point_table(
        results, modules, "BASE", energy_value_usd_kwh=0.05,
        discount_rate_pct=7.0, area_bos_usd_m2=0.0, years=25,
        common_degradation_pct_year=0.5,
    ).set_index("module_id")
    # Equal year-1 energy + equal common degradation + equal area => no primary premium.
    assert out.loc["ALT", "allowable_module_price_premium_vs_baseline_usd_w"] == pytest.approx(0.0)
    # Warranty sensitivity can differ, but it is explicitly separated from the primary threshold.
    assert out.loc["ALT", "indifference_module_price_warranty_sensitivity_usd_w"] != pytest.approx(0.20)


def test_project_segment_prevents_residential_seed_from_utility_comparison():
    modules = pd.read_csv(ROOT / "data/raw/module_candidate_master.csv")
    rec = modules.loc[modules["manufacturer"].eq("REC")].iloc[0]
    first_solar = modules.loc[modules["manufacturer"].eq("First Solar")].iloc[0]
    assert project_segment_compatible(rec, "utility") is False
    assert project_segment_compatible(rec, "residential") is True
    assert project_segment_compatible(first_solar, "utility") is True
    assert project_segment_compatible(first_solar, "residential") is False


def test_epc_production_path_does_not_import_legacy_recommendation_engine():
    source = (ROOT / "app/epc_module_mode.py").read_text(encoding="utf-8")
    assert "recommendation_engine" not in source
    assert "rank_technologies" not in source
    # Both location maps must avoid the CARTO API-key-gated background.
    for relative in ["app/epc_module_mode.py", "app/streamlit_app.py"]:
        map_source = (ROOT / relative).read_text(encoding="utf-8")
        assert 'tiles="OpenStreetMap"' in map_source
        assert 'tiles="CartoDB positron"' not in map_source


def test_legacy_resilience_scores_do_not_enter_epc_decision_source():
    source = "\n".join(
        (ROOT / rel).read_text(encoding="utf-8")
        for rel in [
            "src/module_iv_engine.py",
            "src/epc_decision.py",
            "src/economics_engine.py",
            "app/epc_module_mode.py",
        ]
    )
    forbidden = [
        "heat_resilience_score",
        "humidity_resilience_score",
        "soiling_resilience_score",
        "low_light_score",
        "physics_quality_score",
        "project_fit_score",
    ]
    for term in forbidden:
        assert term not in source


def test_switching_economics_cannot_revive_decision_ineligible_candidate():
    modules = pd.DataFrame([
        {"module_id":"BASE","manufacturer":"Base","model":"B","module_area_m2":2.5,"pmax_w":500.0,"first_year_retention_pct":98.0,"annual_warranty_degradation_pct_year":0.5,"quote_usd_w":0.20},
        {"module_id":"X","manufacturer":"X","model":"X1","module_area_m2":2.4,"pmax_w":500.0,"first_year_retention_pct":99.0,"annual_warranty_degradation_pct_year":0.3,"quote_usd_w":0.10},
    ])
    results = pd.DataFrame([
        {"module_id":"BASE","annual_yield_kwh_kwp":1800.0,"decision_eligible":True},
        {"module_id":"X","annual_yield_kwh_kwp":2200.0,"decision_eligible":False},
    ])
    out = switching_point_table(results, modules, "BASE", 0.05, 7.0, 20.0).set_index("module_id")
    assert out.loc["X", "economic_decision_eligible"] == False
    assert pd.isna(out.loc["X", "indifference_module_price_usd_w"])
    assert out.loc["X", "economic_evidence_note"] == "blocked_incomplete_energy_model_evidence"


def test_nasa_surface_pressure_unit_guard_handles_kpa_and_hpa(monkeypatch):
    import importlib
    import sys
    import types
    # pvlib_pipeline imports pvlib at module import time. A minimal stub is enough to
    # exercise the pure unit-conversion helper in this dependency-limited test env.
    monkeypatch.setitem(sys.modules, "pvlib", types.SimpleNamespace())
    sys.modules.pop("src.pvlib_pipeline", None)
    mod = importlib.import_module("src.pvlib_pipeline")
    pa, note = mod._pressure_to_pa(pd.Series([101.3, 100.8]))
    assert pa.iloc[0] == pytest.approx(101300.0)
    assert "kPa" in note
    pa2, note2 = mod._pressure_to_pa(pd.Series([1013.0, 1008.0]))
    assert pa2.iloc[0] == pytest.approx(101300.0)
    assert "hPa" in note2


def test_parameter_audit_covers_every_module_candidate_field():
    """Every field accepted by the commercial module master must be explicitly classified.

    This prevents new columns from silently becoming decision-driving parameters without an
    evidence/use policy review.
    """
    root = Path(__file__).resolve().parents[1]
    modules = pd.read_csv(root / "data" / "raw" / "module_candidate_master.csv")
    audit = pd.read_csv(root / "docs" / "PARAMETER_AUDIT_V9.csv")
    audited = set(audit["parameter"].astype(str))
    assert set(modules.columns).issubset(audited)


def test_spectral_proxy_partial_domain_is_nonfatal_for_sensitivity(monkeypatch):
    """Regression: a small unsupported spectral fraction must not stop broadband EPC physics."""
    import types
    import src.module_iv_engine as eng

    def fake_firstsolar(precipitable_water, airmass_absolute, module_type=None, **kwargs):
        out = np.ones(len(precipitable_water), dtype=float)
        out[0] = np.nan  # 1 of 100 daylight hours outside executable proxy domain
        return out

    fake_pvlib = types.SimpleNamespace(
        spectrum=types.SimpleNamespace(spectral_factor_firstsolar=fake_firstsolar)
    )
    monkeypatch.setattr(eng, "pvlib", fake_pvlib)

    weather = pd.DataFrame({
        "poa_w_m2": np.full(100, 500.0),
        "airmass_absolute": np.full(100, 1.5),
        "precipitable_water_cm": np.full(100, 2.0),
    })
    row = pd.Series({
        "module_id": "M",
        "manufacturer": "Example",
        "model": "Module",
        "cec_celltype": "monoSi",
    })

    factor = eng.spectral_factor_for_module(weather, row, strict=False)
    assert np.isfinite(factor).all()
    assert factor.iloc[0] == pytest.approx(1.0)
    assert factor.attrs["spectral_proxy_invalid_daylight_fraction_pct"] == pytest.approx(1.0)
    assert factor.attrs["spectral_proxy_valid_daylight_fraction_pct"] == pytest.approx(99.0)
    assert factor.attrs["spectral_proxy_status"] == "partial_validity_neutralized"


def test_spectral_proxy_partial_domain_still_fails_closed_if_decision_grade(monkeypatch):
    import types
    import src.module_iv_engine as eng

    def fake_firstsolar(precipitable_water, airmass_absolute, module_type=None, **kwargs):
        out = np.ones(len(precipitable_water), dtype=float)
        out[0] = np.nan
        return out

    fake_pvlib = types.SimpleNamespace(
        spectrum=types.SimpleNamespace(spectral_factor_firstsolar=fake_firstsolar)
    )
    monkeypatch.setattr(eng, "pvlib", fake_pvlib)

    weather = pd.DataFrame({
        "poa_w_m2": np.full(100, 500.0),
        "airmass_absolute": np.full(100, 1.5),
        "precipitable_water_cm": np.full(100, 2.0),
    })
    row = pd.Series({
        "module_id": "M",
        "manufacturer": "Example",
        "model": "Module",
        "cec_celltype": "monoSi",
    })

    with pytest.raises(ValueError, match="outside its valid input domain for 1.0%"):
        eng.spectral_factor_for_module(weather, row, strict=True)


def test_lifetime_metrics_preserve_missing_exploratory_energy_as_nan():
    results = pd.DataFrame([
        {"module_id": "INELIGIBLE", "annual_yield_kwh_kwp": np.nan},
    ])
    modules = pd.DataFrame([
        {
            "module_id": "INELIGIBLE",
            "first_year_retention_pct": 98.0,
            "annual_warranty_degradation_pct_year": 0.30,
        }
    ])
    out = add_lifetime_metrics(results, modules)
    assert np.isnan(out.iloc[0]["lifetime_energy_common_degradation_scenario_kwh_kwp"])
    assert np.isnan(out.iloc[0]["lifetime_energy_warranty_scenario_kwh_kwp"])
