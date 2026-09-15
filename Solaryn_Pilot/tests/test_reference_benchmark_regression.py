from pathlib import Path

import pandas as pd
import pytest

from src.benchmark_regression import (
    REFERENCE_FOUR_CANDIDATE_IDS,
    REFERENCE_THREE_CANDIDATE_IDS,
    candidate_set_sha256,
    load_frozen_reference_benchmarks,
)
from src.epc_decision import recommendation_decision


ROOT = Path(__file__).resolve().parents[1]
THREE_HASH = "704a9bb0030e0540678094eaeea7ce6204cf74fbf232b02a92182e3a6143ac80"
FOUR_HASH = "e7163ed495f0cb6aa98d2e003f4139249d9172243bac141df3a9d4348b8a2b94"


def _modules():
    return pd.read_csv(ROOT / "data/raw/module_candidate_master.csv")


def _decision(case: pd.DataFrame):
    results = case.copy()
    results["annual_dc_specific_energy_broadband_kwh_kwp"] = results["annual_yield_kwh_kwp"]
    results["annual_dc_specific_energy_spectral_sensitivity_kwh_kwp"] = results["annual_yield_kwh_kwp"]
    results["lifetime_energy_common_degradation_scenario_kwh_kwp"] = results["annual_yield_kwh_kwp"] * 23.55
    results["lifetime_energy_warranty_scenario_kwh_kwp"] = results["annual_yield_kwh_kwp"] * 23.55
    return recommendation_decision(results, uncertainty_guardrail_pct=2.0, n_samples=3000)


def test_frozen_reference_three_candidate_benchmark_and_candidate_hash():
    modules = _modules()
    selected = modules[modules.module_id.isin(REFERENCE_THREE_CANDIDATE_IDS)]
    assert tuple(sorted(selected.module_id)) == tuple(sorted(REFERENCE_THREE_CANDIDATE_IDS))
    assert candidate_set_sha256(selected) == THREE_HASH

    case = load_frozen_reference_benchmarks(ROOT).query("case == 'three_candidate'")
    assert case.candidate_set_sha256.unique().tolist() == [THREE_HASH]
    expected = dict(zip(case.module_id, case.annual_yield_kwh_kwp))
    assert expected["MOD_TOPCON_JINKO_JKM575N_72HL4_V"] == pytest.approx(2073.433038, abs=1e-6)
    assert expected["MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530"] == pytest.approx(2048.638261, abs=1e-6)
    assert expected["MOD_PERC_LONGI_LR5_72HPH_550M"] == pytest.approx(2034.997755, abs=1e-6)
    decision = _decision(case)
    assert decision["technical_leader_module_id"] == "MOD_TOPCON_JINKO_JKM575N_72HL4_V"
    assert decision["annual_lead_over_second_pct"] == pytest.approx(1.2103052741519815, abs=1e-6)
    assert decision["winner_module_id"] is None


def test_frozen_reference_four_candidate_fixture_remains_stable_inside_expanded_catalog():
    modules = _modules()
    selected = modules[modules.module_id.isin(REFERENCE_FOUR_CANDIDATE_IDS)]
    assert tuple(sorted(selected.module_id)) == tuple(sorted(REFERENCE_FOUR_CANDIDATE_IDS))
    assert candidate_set_sha256(selected) == FOUR_HASH
    # The commercial catalog is intentionally allowed to expand without mutating the
    # frozen four-candidate regression fixture.
    assert len(modules) >= len(REFERENCE_FOUR_CANDIDATE_IDS)

    case = load_frozen_reference_benchmarks(ROOT).query("case == 'four_candidate'")
    assert case.candidate_set_sha256.unique().tolist() == [FOUR_HASH]
    decision = _decision(case)
    assert decision["technical_leader_module_id"] == "MOD_HJT_REC_ALPHA_PURE_RX_470"
    assert decision["annual_lead_over_second_pct"] == pytest.approx(1.4839640627860653, abs=1e-6)
    assert decision["winner_module_id"] is None
