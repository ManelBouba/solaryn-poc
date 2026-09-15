from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
EPC = (ROOT / "app" / "epc_module_mode.py").read_text(encoding="utf-8")


def test_persistent_product_navigation_replaces_workspace_radio():
    for label in ["Projects", "New Project", "Technology & Materials", "Reports", "Organization", "Help"]:
        assert f'("{label}",' in APP
    assert "st.radio(" not in APP


def test_customer_surfaces_remove_legacy_version_language():
    assert "V8" not in APP
    assert "V8" not in EPC
    # The only V9 reference is permitted analysis-provenance metadata.
    assert APP.count("V9") == 1
    assert '"model_version": "V9.2.1"' in APP
    assert "V9" not in EPC


def test_research_workspace_uses_non_commercial_language():
    assert "Technology & Material Screening" in APP
    assert "Leading research hypotheses" in APP
    assert "Research-screening score" in APP
    assert "cannot be approved as procurement decisions" in APP


def test_required_empty_and_failure_states_are_explicit():
    assert "Add a real baseline supplier quote" in EPC
    assert "Climate data could not be reached" in EPC
    assert "No calculation was completed and no fallback climate data was substituted" in EPC
    assert "Maximum justified price premium unavailable" in EPC


def test_commercial_decision_and_progress_are_visible():
    assert "04  Commercial decision" in EPC
    assert "Maximum justified price premium" in EPC
    assert "Preparing site climate" in EPC
    assert "PROJECT WORKFLOW" in EPC
