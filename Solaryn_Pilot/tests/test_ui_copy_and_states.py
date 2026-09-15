from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
EPC = (ROOT / "app" / "epc_module_mode.py").read_text(encoding="utf-8")


def test_product_navigation_is_client_facing_and_compact():
    for label in ["Overview", "Module Recommendation", "Technology Library", "Downloads", "Method & Evidence"]:
        assert f'("{label}",' in APP
    for removed in ["Organization", "New Project"]:
        assert f'("{removed}",' not in APP
    assert "st.radio(" not in APP


def test_customer_surfaces_remove_internal_release_and_work_in_progress_language():
    combined = (APP + "\n" + EPC).lower()
    forbidden_status = "dra" + "ft"
    assert forbidden_status not in combined
    forbidden = "p" + "oc"
    assert forbidden not in combined
    assert "solaryn v" not in combined


def test_technology_library_is_explicitly_non_procurement():
    assert "Technology Intelligence" in APP
    assert "research hypotheses" in APP.lower()
    assert "procurement" in APP.lower()


def test_required_empty_and_failure_states_are_explicit():
    assert "real baseline supplier quote" in EPC.lower()
    assert "Climate data could not be reached" in EPC
    assert "No calculation was completed and no fallback climate data was substituted" in EPC
    assert "Commercial switching value unavailable" in EPC


def test_recommendation_and_progress_are_visible():
    assert "04  Recommendation" in EPC
    assert "P(best)" in EPC
    assert "Expected regret" in EPC
    assert "Preparing site climate" in EPC
    assert "PROJECT WORKFLOW" in EPC


def test_location_and_export_are_dynamic_not_city_hardcoded():
    combined = APP + "\n" + EPC
    assert "Riyadh" not in combined
    assert "City / project location" in EPC
    assert "Find city" in EPC
    assert 'package_name = f"Solaryn_{project_slug}_{leader_slug}.zip"' in EPC
    assert "Download complete Solaryn project (ZIP)" in EPC
