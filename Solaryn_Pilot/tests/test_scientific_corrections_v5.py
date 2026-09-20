import numpy as np
import pandas as pd

from src.site_qualification import qualification_for_candidate
from src.uncertainty_engine import candidate_model_sigma_pct


def test_t98_qualification_prefers_iec_all_hours_statistic():
    module = {"module_id": "x", "certifications": "IEC 61215"}
    result = {
        "p98_module_temperature_c_all_hours": 69.5,
        "p98_module_temperature_c_daylight": 82.0,
    }
    weather = pd.DataFrame({
        "poa_w_m2": [0.0, 800.0],
        "relative_humidity_pct": [50.0, 50.0],
        "temp_air_c": [20.0, 35.0],
        "rainfall_mm_hour": [0.0, 0.0],
    })
    q = qualification_for_candidate(module, result, weather, {"salinity_stress": "low"})
    assert q.t98_module_c == 69.5
    assert "T98 ≤70°C" in q.temperature_level
    assert "high_temperature_qualification" not in q.requirements


def test_empirical_model_uncertainty_overrides_generic_evidence_prior():
    row = {
        "electrical_model": "iec61853",
        "model_evidence_level": "module_specific_measured_matrix",
        "validated_model_sigma_pct": 1.2,
        "thermal_validation_rmse_pct": 0.8,
        "rear_irradiance_model_active": False,
    }
    sigma = candidate_model_sigma_pct(row)
    assert np.isclose(sigma, np.sqrt(1.2**2 + 0.8**2))


def test_missing_salt_mist_evidence_is_conditional_not_universal_material_fail():
    module = {
        "module_id": "eva-product",
        "packaging": "glass-backsheet EVA",
        "certifications": "IEC 61215",
    }
    result = {"p98_module_temperature_c_all_hours": 55.0}
    weather = pd.DataFrame({
        "poa_w_m2": [500.0, 600.0],
        "relative_humidity_pct": [90.0, 92.0],
        "temp_air_c": [30.0, 31.0],
        "rainfall_mm_hour": [0.0, 0.0],
    })
    q = qualification_for_candidate(module, result, weather, {
        "salinity_stress": "coastal",
        "hard_qualification_gates": False,
    })
    assert q.status == "conditional"
    assert "IEC_61701_salt_mist" in q.missing
