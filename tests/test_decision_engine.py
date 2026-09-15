import pandas as pd
from pathlib import Path

from src.climate_fingerprint import compute_climate_fingerprint
from src.recommendation_engine import (
    decision_leaders,
    filter_candidate_universe,
    project_decision_summary,
    rank_technologies,
)

ROOT = Path(__file__).resolve().parents[1]


def _data():
    tech = pd.read_csv(ROOT / "data/raw/technology_master.csv")
    sites = pd.read_csv(ROOT / "data/raw/sites.csv")
    sites["degradation_scenario_pct_year"] = 0.50
    sites["soiling_loss_assumption_pct"] = 2.0
    sites = compute_climate_fingerprint(sites)
    return tech, sites


def test_original_solaryn_database_is_preserved():
    tech, _ = _data()
    assert len(tech) == 30
    assert {"Mono PERC", "TOPCon", "HJT", "CdTe Thin Film", "CIGS Thin Film"}.issubset(set(tech["technology_name"]))
    assert {"bandgap_eV", "carrier_lifetime_ns", "defect_density_cm-3", "absorber_thickness_um"}.issubset(tech.columns)


def test_three_decision_lenses_still_exist():
    tech, sites = _data()
    commercial = filter_candidate_universe(tech)
    ranking = rank_technologies(sites.iloc[0], commercial)
    leaders = decision_leaders(ranking)
    assert set(leaders) == {"best_lifetime", "best_value", "lowest_risk"}
    assert all(c in ranking for c in ["best_lifetime_score", "best_value_score", "lowest_risk_score"])


def test_commercial_poc_excludes_research_and_unmodelled_bifacial_variants():
    tech, _ = _data()
    commercial = filter_candidate_universe(tech)
    assert not commercial.empty
    assert commercial["commercialization_status"].str.lower().eq("commercial").all()
    assert (commercial["TRL_level"] >= 8).all()
    assert not commercial["technology_name"].str.contains("bifacial", case=False).any()


def test_project_decision_returns_top3_without_fake_confidence_probability():
    tech, sites = _data()
    commercial = filter_candidate_universe(tech)
    ranking = rank_technologies(sites.iloc[0], commercial, objective="Lifetime energy")
    summary = project_decision_summary(ranking)
    assert len(summary["top3"]) == 3
    assert "project_fit_score" in ranking.columns
    assert ranking.iloc[0]["project_rank"] == 1
    assert "decision_confidence_score" not in summary
    assert summary["scientific_status"].startswith("screening result")


def test_same_project_soiling_assumption_is_applied_to_every_commercial_technology():
    tech, sites = _data()
    commercial = filter_candidate_universe(tech)
    ranking = rank_technologies(sites.iloc[3], commercial, objective="Lifetime energy")
    assert ranking["soiling_loss_pct"].max() - ranking["soiling_loss_pct"].min() < 0.02


def test_common_degradation_scenario_does_not_use_database_rate_to_manufacture_winner():
    tech, sites = _data()
    commercial = filter_candidate_universe(tech)
    ranking = rank_technologies(sites.iloc[5], commercial, objective="Lifetime energy")
    assert ranking["adjusted_degradation_pct_year"].nunique() == 1
    assert abs(ranking["adjusted_degradation_pct_year"].iloc[0] - 0.50) < 1e-9
    assert ranking["database_degradation_pct_year"].nunique() > 1


def test_material_physics_quality_is_diagnostic_not_a_project_score_input():
    tech, sites = _data()
    # Build two otherwise-identical records and alter only deep material fields.
    a = tech.iloc[0].copy()
    b = a.copy()
    b["technology_id"] = "TEST_B"
    b["technology_name"] = "Same commercial behavior, different material proxy"
    b["carrier_lifetime_ns"] = float(a["carrier_lifetime_ns"]) * 1e-6
    b["defect_density_cm-3"] = float(a["defect_density_cm-3"]) * 1e8
    pair = pd.DataFrame([a, b])
    ranking = rank_technologies(sites.iloc[0], pair, objective="Lifetime energy")
    assert ranking["project_fit_score"].nunique() == 1
    assert ranking["physics_quality_score"].nunique() > 1
