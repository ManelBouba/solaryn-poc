from pathlib import Path

import pandas as pd
import pytest

from src.module_iv_engine import _pmp_from_cec, cec_stc_fit_residuals, fit_cec_from_datasheet


ROOT = Path(__file__).resolve().parents[1]


def _jinko():
    modules = pd.read_csv(ROOT / "data/raw/module_candidate_master.csv")
    return modules.loc[modules["manufacturer"].eq("JinkoSolar")].iloc[0]


def test_cec_fit_reproduces_jinko_stc_pmp_within_internal_one_percent_target():
    residuals = cec_stc_fit_residuals(_jinko())
    assert abs(residuals["residual_pmp_w_pct"]) <= 1.0
    assert abs(residuals["residual_voc_v_pct"]) <= 1.0
    assert abs(residuals["residual_isc_a_pct"]) <= 1.0


def test_negative_temperature_coefficient_module_loses_power_when_hotter():
    row = _jinko()
    fit = fit_cec_from_datasheet(row)
    irradiance = pd.Series([1000.0, 1000.0])
    temperature = pd.Series([25.0, 65.0])
    power = _pmp_from_cec(irradiance, temperature, fit)
    assert power.iloc[1] < power.iloc[0]


def test_lower_irradiance_reduces_pmp_and_night_is_zero():
    row = _jinko()
    fit = fit_cec_from_datasheet(row)
    irradiance = pd.Series([1000.0, 500.0, 0.0])
    temperature = pd.Series([25.0, 25.0, 25.0])
    power = _pmp_from_cec(irradiance, temperature, fit)
    assert power.iloc[0] > power.iloc[1] > power.iloc[2]
    assert power.iloc[2] == pytest.approx(0.0)
