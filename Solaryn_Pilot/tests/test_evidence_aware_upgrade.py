import numpy as np
import pandas as pd

from src.evidence_hierarchy import assess_candidate_evidence
from src.site_qualification import classify_site_exposure, qualification_for_candidate
from src.lifetime_engine import lifetime_energy_distribution
from src.uncertainty_engine import compare_candidates_correlated


def _weather(temp=25, rh=50, precip=0):
    return pd.DataFrame({
        'poa_w_m2':[800.0]*100,
        'relative_humidity_pct':[rh]*100,
        'temp_air_c':[temp]*100,
        'rainfall_mm_hour':[precip]*100,
    })


def test_evidence_grade_does_not_modify_energy():
    module={'source_url':'https://example.com/datasheet.pdf','annual_warranty_degradation_pct_year':0.4,
            'thermal_construction':'glass_glass','bom_evidence_status':'not_provided'}
    result={'electrical_model':'cec_single_diode_datasheet_fit','model_evidence_level':'datasheet_fit_crystalline',
            'spectral_evidence_level':'technology_class_proxy','annual_yield_kwh_kwp':1800}
    ev=assess_candidate_evidence(module,result,'conditional')
    assert ev.grade in {'B','C','D'}
    assert result['annual_yield_kwh_kwp']==1800
    assert ev.gaps


def test_hot_t98_and_coastal_create_evidence_gates_not_bonus_points():
    module={'certifications':'IEC 61215; IEC 61701','source_url':'https://example.com'}
    result={'p98_module_temperature_c_daylight':82.0}
    q=qualification_for_candidate(module,result,_weather(temp=35,rh=85),
                                  {'salinity_stress':'coastal','hard_qualification_gates':False})
    assert 'IEC_61701_salt_mist' in q.satisfied
    assert 'high_temperature_qualification' in q.missing
    assert q.status=='conditional'


def test_hard_gate_can_block_missing_coastal_evidence():
    q=qualification_for_candidate({}, {'p98_module_temperature_c_daylight':65.0}, _weather(rh=60),
                                  {'salinity_stress':'high','hard_qualification_gates':True})
    assert q.status=='blocked'
    assert 'IEC_61701_salt_mist' in q.missing


def test_lifetime_distribution_p90_below_p50():
    d=lifetime_energy_distribution(1800,0.5,0.2,3.0,25,n=2000,seed=1)
    assert d['p90_lifetime_kwh_kwp'] < d['p50_lifetime_kwh_kwp']
    assert d['p50_lifetime_kwh_kwp'] > 0


def test_correlated_uncertainty_can_expose_no_clear_separation():
    f=pd.DataFrame([
        {'module_id':'A','annual_yield_kwh_kwp':1800,'model_evidence_level':'datasheet_fit_crystalline','electrical_model':'cec_single_diode_datasheet_fit','thermal_evidence_level':'generic'},
        {'module_id':'B','annual_yield_kwh_kwp':1798,'model_evidence_level':'datasheet_fit_crystalline','electrical_model':'cec_single_diode_datasheet_fit','thermal_evidence_level':'generic'},
    ])
    out=compare_candidates_correlated(f,n=3000,seed=4)
    assert 0 < out['probability_of_best_pct']['A'] < 100
    assert abs(sum(out['probability_of_best_pct'].values())-100) < 1e-6
