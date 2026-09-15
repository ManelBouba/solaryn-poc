from dataclasses import replace
import json
import math
import sqlite3
import pytest
from src.procurement_model import Project, Candidate, lifecycle, compare, screening_physics, evidence_gaps, irr
from src.procurement_store import save, read, history


def offer(**kwargs):
    return replace(Candidate("A", "SKU", "R1", .1, 2000., "Independent study", event_year=1), **kwargs)


def test_hand_calculated_one_year_and_units():
    p = Project(capacity_mwp=1, years=1, discount_rate=0, ppa_eur_mwh=50,
                bos_eur_w=.4, om_eur_kw_year=10, cleaning_eur_kw_year=0)
    r = lifecycle(p, offer())
    assert r["year1_mwh"] == 2000
    assert r["capex_eur"] == 500000
    assert r["npv_eur"] == -410000
    assert r["lcoe_eur_mwh"] == 255
    assert r["irr"] == pytest.approx(-.82)


def test_discount_and_compound_degradation():
    p = Project(capacity_mwp=1, years=2, discount_rate=.1, om_eur_kw_year=0, cleaning_eur_kw_year=0)
    r = lifecycle(p, offer(degradation=.1))
    assert [a["energy_mwh"] for a in r["annual"]] == [2000, 1800]
    assert r["npv_eur"] == pytest.approx(-500000 + 90000 / 1.1 + 81000 / 1.1**2)


def test_replacement_cost_recovery_and_outage():
    p = Project(capacity_mwp=1, years=1, om_eur_kw_year=0, cleaning_eur_kw_year=0)
    r = lifecycle(p, offer(event_fraction=.2, downtime_days=365, replacement_eur_w=.3, warranty_recovery=.5))
    a = r["annual"][0]
    assert a["energy_mwh"] == 1600
    assert a["replacement_eur"] == 60000
    assert a["cost_eur"] == 30000


def test_premium_sets_equal_npv_and_is_not_quote_difference():
    p = Project()
    a, b = offer(), offer(name="B", quote_eur_w=.14, net_ac_kwh_kwp=2100.)
    r = compare(p, [a, b])
    rb = next(x for x in r["results"] if x["candidate"] == "B")
    adjusted = lifecycle(p, replace(b, quote_eur_w=rb["break_even_quote_eur_w"]))
    assert adjusted["npv_eur"] == pytest.approx(lifecycle(p, a)["npv_eur"], abs=1e-7)
    assert rb["justified_premium_eur_w_vs_first"] > 0


def test_ties_and_scenario_monotonicity():
    p = Project()
    a, b = offer(), offer(name="B")
    assert compare(p, [a, b])["leader"] is None
    assert compare(p, [a, b], degradation_add=.01, yield_haircut=.05)["results"][0]["npv_eur"] < lifecycle(p, a)["npv_eur"]
    with pytest.raises(ValueError, match="unique"):
        compare(p, [a, a])


@pytest.mark.parametrize("field,value", [("degradation", float("nan")), ("quote_eur_w", -1),
                                        ("net_ac_kwh_kwp", 0), ("event_year", 1.5), ("warranty_recovery", 1.1)])
def test_invalid_candidates_fail(field, value):
    with pytest.raises(ValueError):
        lifecycle(Project(), offer(**{field: value}))


def test_evidence_binding_invalidates_changed_value_or_bom():
    c = offer()
    claims = [dict(candidate=c.name, model=c.model, bom=c.bom, field=f, value=str(getattr(c, f)),
                   source="report.pdf", section="p. 2", status="Reviewed", reviewer="Engineer", date="2026-09-12")
              for f in ["net_ac_kwh_kwp", "quote_eur_w", "degradation", "bom"]]
    assert evidence_gaps(c, claims) == []
    assert evidence_gaps(replace(c, quote_eur_w=.2), claims) == ["quote_eur_w"]
    assert len(evidence_gaps(replace(c, bom="R2"), claims)) == 4


def test_physics_night_temperature_and_clipping():
    assert screening_physics(0, 20, 0)["ac_kwh_kwp"] == 0
    r = screening_physics(1000, 25, 0, gamma=0, loss=0, efficiency=1, dc_ac_ratio=2)
    assert r["module_c"] == 65
    assert r["cell_c"] == 68
    assert r["ac_kwh_kwp"] == .5
    assert screening_physics(800, 30, 5)["module_c"] < screening_physics(800, 30, 0)["module_c"]


def test_nonconventional_irr_not_reported():
    assert irr([-100, 230, -132]) is None
    assert irr([-100, -5]) is None


def test_zero_lifetime_energy_rejected():
    with pytest.raises(ValueError, match="no lifetime energy"):
        lifecycle(Project(years=1), offer(event_fraction=1, downtime_days=365))


def test_snapshot_roundtrip_and_tampering(tmp_path):
    path = tmp_path / "store.sqlite3"
    result = compare(Project(), [offer(), offer(name="B")])
    key = save(path, result)
    assert read(path, key) == result
    assert len(history(path)) == 1
    with sqlite3.connect(path) as db:
        db.execute("UPDATE decisions SET payload = ? WHERE id = ?", ("{}", key))
    with pytest.raises(ValueError, match="integrity"):
        read(path, key)


def test_workspace_ui(tmp_path):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PROCUREMENT_MODEL.md").write_text((root / "docs" / "PROCUREMENT_MODEL.md").read_text(encoding="utf-8"), encoding="utf-8")
    script = f"from pathlib import Path\nfrom app.procurement_ui import render_procurement\nrender_procurement(Path({str(tmp_path)!r}))"
    at = AppTest.from_string(script).run(timeout=30)
    assert not at.exception
    assert at.metric[0].label == "Scenario leader"
    at.button[0].click().run()
    assert not at.exception
    assert len(history(tmp_path / "workspace" / "procurement.sqlite3")) == 1
    at.slider[0].set_value(1.).run()
    assert not at.exception
