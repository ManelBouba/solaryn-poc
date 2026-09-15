from pathlib import Path

import pytest

from src.outdoor_validation import validate_iec61853_pmax_layer


ROOT = Path(__file__).resolve().parents[1]
DVP = ROOT / "validation/external/iea_pvps_task13_supsi_csi"


@pytest.fixture(scope="module")
def validation():
    return validate_iec61853_pmax_layer(
        DVP / "data",
        DVP / "IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv",
    )


def test_external_dvp_reproduces_published_primary_metrics(validation):
    summary, monthly, retained = validation
    assert summary["status"] == "PASS_EXTERNAL_MEASURED_LAYER"
    assert summary["raw_rows"] == 36449
    assert summary["complete_rows"] == 34763
    assert summary["excluded_physical_rows"] == 12
    assert summary["retained_rows"] == 28286
    assert summary["nearest_fallback_rows"] == 783
    assert summary["rmse_w"] == pytest.approx(18.163253018950357, abs=1e-10)
    assert summary["rmse_pct_stc"] == pytest.approx(6.357769813109597, abs=1e-10)
    assert summary["mbe_w"] == pytest.approx(-0.013909974408691886, abs=1e-10)
    assert summary["r2"] == pytest.approx(0.9358773628221518, abs=1e-10)
    assert summary["cumulative_sampled_energy_bias_pct"] == pytest.approx(
        -0.00838739452795334, abs=1e-10
    )
    assert len(monthly) == 12
    assert len(retained) == 28286


def test_external_dvp_scope_cannot_be_misread_as_full_decision_validation(validation):
    summary, _, _ = validation
    assert summary["validation_scope"] == "iec61853_measured_pmax_gt_interpolation_layer_only"
    assert summary["full_decision_engine_validated"] is False
    assert summary["commercial_candidate_specific_validation"] is False
