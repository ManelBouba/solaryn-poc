import numpy as np
import pandas as pd
import pytest

from src.climate_physics import simulate_site_technology


def _site():
    return pd.Series({
        'latitude': 32.2, 'ghi_kwh_m2_year': 2000.0, 'avg_temp_c': 24.0,
        'max_temp_c': 42.0, 'wind_speed_m_s': 2.0, 'humidity_pct': 45.0,
        'rainfall_mm_year': 200.0, 'soiling_loss_assumption_pct': 0.0,
        'degradation_scenario_pct_year': 0.5, 'salinity_risk': 0.0,
    })


def _tech(**kw):
    d={
        'technology_id':'T1','technology_name':'Mono Silicon','family':'Silicon','subfamily':'mono-Si',
        'temp_coefficient_pct_c':-0.35,'baseline_degradation_pct_year':0.8,
        'efficiency_commercial_percent':22.0,'humidity_resilience_score':3.0,
        'source_quality':'literature_range','pmax_w':1000.0,
    }
    d.update(kw)
    return pd.Series(d)


def _weather(n=24):
    idx=pd.RangeIndex(n)
    poa=np.array([0]*6 + [500]*12 + [0]*6, dtype=float)
    return pd.DataFrame({
        'date': pd.Timestamp('2025-01-01'),
        'days_weight': 365/1.0,
        'poa_w_m2':poa,
        'poa_optical_w_m2':poa*0.95,
        'aoi_deg':np.where(poa>0, 40.0, 90.0),
        'temp_air_c':25.0,'temp_cell_c':40.0,
        'temp_cell_is_measured':False,
        'temp_cell_source':'pvlib SAPM modeled cell temperature',
        'wind_speed_m_s':2.0,'relative_humidity':0.5,'rainfall_mm_day':0.0,
        'aod_55':np.nan,'uv_index_proxy':poa/1000.0,
    }, index=idx)


def test_precomputed_optical_poa_is_not_iam_corrected_twice():
    out=simulate_site_technology(_site(),_tech(),_weather())
    assert out['aoi_model_note'].startswith('component-wise common-glass IAM')
    assert out['aoi_effect_pct'] == pytest.approx(-5.0, abs=0.05)


def test_module_specific_faiman_overrides_generic_upstream_modeled_temperature():
    out=simulate_site_technology(_site(),_tech(thermal_u0_w_m2k=25.0, thermal_u1_w_s_m3k=6.84),_weather())
    assert out['thermal_model_basis'] == 'module-specific Faiman U0/U1'
    assert out['thermal_temperature_measured'] is False


def test_field_validated_degradation_can_drive_lifetime_but_literature_baseline_cannot():
    out=simulate_site_technology(_site(),_tech(),_weather())
    assert out['site_degradation_pct_year'] == pytest.approx(0.5)
    assert out['degradation_rate_measured'] is False
    validated=_tech(field_validated_degradation_pct_year=0.32,degradation_evidence_status='field_validated')
    out2=simulate_site_technology(_site(),validated,_weather())
    assert out2['site_degradation_pct_year'] == pytest.approx(0.32)
    assert out2['degradation_rate_measured'] is True


def test_bifacial_gain_requires_rear_irradiance_evidence():
    tech=_tech(bifaciality_factor=0.75)
    w=_weather()
    out=simulate_site_technology(_site(),tech,w)
    assert out['bifacial_model_applied'] is False
    w['poa_rear_w_m2']=w['poa_w_m2']*0.10
    out2=simulate_site_technology(_site(),tech,w)
    assert out2['bifacial_model_applied'] is True
    assert out2['annual_yield_kwh_kwp'] > out['annual_yield_kwh_kwp']
