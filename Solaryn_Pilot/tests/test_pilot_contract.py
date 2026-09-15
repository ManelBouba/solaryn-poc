from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from src.pilot_decision import decide
from src.pilot_service import analyze, validate_project
from src.run_store import RunStore, sha
from src.pilot_report import render_report, package_run
from src.module_offer_io import load_module_offer_csv
from src.module_iv_engine import simulate_module_hourly, validate_module_candidates
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.uncertainty_engine import compare_candidates_correlated
from src.benchmark_regression import REFERENCE_THREE_CANDIDATE_IDS

ROOT = Path(__file__).resolve().parents[1]

def rows(gap=10):
    return pd.DataFrame([dict(module_id=x, manufacturer=x, model=x, annual_yield_kwh_kwp=y,
        lifetime_energy_common_degradation_scenario_kwh_kwp=y*20, decision_eligible=True,
        electrical_model="iec61853_module_specific_matrix", model_evidence_level="module_specific_measured_matrix",
        thermal_evidence_level="module_specific_u0_u1", claim_evidence_reviewed=True) for x,y in [("A",2000*(1+gap/100)),("B",2000)]])

@pytest.mark.parametrize("gap,evidence,resource,geometry,expected", [
    (10,True,"adequate","measured","ROBUST_MODELED_ADVANTAGE"),
    (10,True,"warning","measured","PROVISIONAL_TECHNICAL_LEADER"),
    (1,True,"adequate","measured","EFFECTIVELY_TIED"),
    (10,False,"adequate","measured","INSUFFICIENT_EVIDENCE"),
])
def test_four_states(gap,evidence,resource,geometry,expected):
    f=rows(gap);f['decision_eligible']=evidence
    assert decide(f,resource_status=resource,geometry_confidence=geometry)['status']==expected

@pytest.mark.parametrize("value", [False, "False", None, np.nan, "unknown"])
def test_evidence_fails_closed(value):
    f=rows();f['decision_eligible']=value
    assert decide(f)['status']=='INSUFFICIENT_EVIDENCE'

def test_missing_evidence_and_failed_competitor():
    assert decide(rows().drop(columns='decision_eligible'))['status']=='INSUFFICIENT_EVIDENCE'
    assert decide(rows(),failed_candidates=[{'module_id':'C'}])['status']=='INSUFFICIENT_EVIDENCE'

def test_declared_coefficients_without_review_cannot_unlock_robust():
    f=rows().drop(columns='claim_evidence_reviewed')
    assert decide(f,resource_status='adequate',geometry_confidence='measured')['status']=='PROVISIONAL_TECHNICAL_LEADER'

@pytest.mark.parametrize("bad", [0,-1,np.nan,np.inf])
def test_bad_energy_cannot_rank(bad):
    f=rows();f['annual_yield_kwh_kwp']=bad
    with pytest.raises(ValueError,match='no ranking'): decide(f)

def test_exact_tie_has_no_unique_leader_and_fair_probability():
    f=rows(0)
    assert decide(f)['provisional_leader_module_id'] is None
    for order in [f, f.iloc[::-1]]:
        p=compare_candidates_correlated(order,candidate_sigma_pct={'A':0,'B':0},n=1000)
        assert p['probability_of_best_pct']=={'A':50.,'B':50.}

def test_uncertainty_reordering_is_deterministic():
    f=rows(1)
    a=compare_candidates_correlated(f,n=1000)
    b=compare_candidates_correlated(f.iloc[::-1],n=1000)
    assert a==b

@pytest.fixture(scope='module')
def weather():
    n=pd.read_csv(ROOT/'data/reference/riyadh_hourly.csv',parse_dates=['time_utc'])
    n.attrs['time_standard']='UTC'
    return n

def project():
    return dict(project_name='Riyadh regression',latitude=24.7136,longitude=46.6753,
        tilt_deg=25,azimuth_deg=180,soiling_loss_pct=2,common_degradation_pct_year=.5,
        system_size_mw=100,target_lifetime_years=25,currency='USD')

def modules():
    m=load_module_offer_csv(ROOT/'data/raw/module_candidate_master.csv')
    return m[m.module_id.isin(REFERENCE_THREE_CANDIDATE_IDS)]

def test_real_weather_row_model_positive_and_index_invariant(weather):
    w=nasa_hourly_to_pvlib_weather(weather,24.7136,46.6753,25,180)
    m=modules().query("technology_label=='Mono PERC'").iloc[0]
    a,h=simulate_module_hourly(w,m,root=ROOT,bifacial_config={'enabled':True})
    w.index=pd.DatetimeIndex(w.time_utc)
    b,_=simulate_module_hourly(w,m,root=ROOT,bifacial_config={'enabled':True})
    assert a['annual_yield_kwh_kwp'] > 1500
    assert a['annual_yield_kwh_kwp']==pytest.approx(b['annual_yield_kwh_kwp'],abs=1e-8)
    assert np.isfinite(a['p95_cell_temperature_c_daylight'])

def test_invalid_daylight_is_failure(weather):
    w=nasa_hourly_to_pvlib_weather(weather,24.7136,46.6753,25,180)
    w.loc[w.ghi_w_m2>100,'solar_zenith_deg']=np.nan
    with pytest.raises(ValueError): simulate_module_hourly(w,modules().iloc[0],root=ROOT,bifacial_config={'enabled':True})

def test_frozen_end_to_end_and_immutable_exports(weather,tmp_path):
    r=analyze(ROOT,project(),modules(),weather,store_root=tmp_path)
    expected={'MOD_TOPCON_JINKO_JKM575N_72HL4_V':2073.433038,'MOD_PERC_LONGI_LR5_72HPH_550M':2034.997755,'MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530':2048.638261}
    for c in r['candidates']: assert c['metrics']['annual_yield_kwh_kwp']==pytest.approx(expected[c['module_id']],abs=.001)
    assert r['decision']['status']=='INSUFFICIENT_EVIDENCE'
    assert r['decision']['provisional_leader_module_id']=='MOD_TOPCON_JINKO_JKM575N_72HL4_V'
    assert r['economics']['switching_threshold'] is None
    assert analyze(ROOT,project(),modules(),weather,store_root=tmp_path)==r
    store=RunStore(tmp_path)
    assert (tmp_path/r['run_id']/'Decision.html').read_text(encoding='utf-8')==render_report(r)
    assert package_run(store,r['run_id'])==package_run(store,r['run_id'])
    monthly=pd.DataFrame(r['monthly']).groupby('module_id').energy_kwh_kwp.sum()
    for c in r['candidates']: assert monthly[c['module_id']]==pytest.approx(c['metrics']['annual_yield_kwh_kwp'])
    (tmp_path/r['run_id']/'Comparison.csv').write_text('tampered')
    with pytest.raises(ValueError,match='integrity'): store.read(r['run_id'])

def test_nonfinite_catalog_area():
    m=modules().copy();m.iloc[0,m.columns.get_loc('module_area_m2')]=np.inf
    with pytest.raises(ValueError): validate_module_candidates(m)

def test_zero_outputs_persist_failure_without_leader(weather,tmp_path,monkeypatch):
    def fail(*args,**kwargs): raise ValueError('invalid daytime physics')
    monkeypatch.setattr('src.pilot_service.simulate_module_hourly',fail)
    r=analyze(ROOT,project(),modules(),weather,store_root=tmp_path)
    assert r['status']=='failed'
    assert r['decision']['provisional_leader_module_id'] is None
    assert len(r['candidates'])==3
    assert all(c['simulation_status']=='failed' for c in r['candidates'])

def test_lifetime_is_integer():
    p=project();p['target_lifetime_years']=25.5
    with pytest.raises(ValueError): validate_project(p)

def test_switching_threshold_independent_hand_calculation():
    from src.economics_engine import switching_point_table
    m=pd.DataFrame([dict(module_id=mid,manufacturer=mid,model=mid,pmax_w=500.,module_area_m2=area,
        quote_usd_w=.2,first_year_retention_pct=100.,annual_warranty_degradation_pct_year=0.)
        for mid,area in [('BASE',2.5),('ALT',2.4)]])
    f=pd.DataFrame([dict(module_id='BASE',annual_yield_kwh_kwp=2000.,decision_eligible=True),
                    dict(module_id='ALT',annual_yield_kwh_kwp=2100.,decision_eligible=True)])
    out=switching_point_table(f,m,'BASE',energy_value_usd_kwh=.1,discount_rate_pct=0,
                            area_bos_usd_m2=20,years=2,common_degradation_pct_year=0).set_index('module_id')
    # 100 kWh/kWp extra/year /1000 W/kW *0.1 currency/kWh *2 years =0.020 currency/W.
    # Area saving (2.5-2.4) m2 *20 currency/m2 /500 W =0.004 currency/W.
    assert out.loc['ALT','indifference_module_price_usd_w']==pytest.approx(.224)
    f['decision_eligible']='False'
    with pytest.raises(ValueError,match='evidence-limited'):
        switching_point_table(f,m,'BASE',energy_value_usd_kwh=.1,discount_rate_pct=0,area_bos_usd_m2=20)
