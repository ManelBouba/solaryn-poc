"""Synthetic fixtures prove software behavior, not external scientific validation."""
from copy import deepcopy
import hashlib
import io
import json
import re
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

from catalog_service import catalog, families
from electrical_router import power
from performance_v2 import calculate, core
from performance_service import calculate as legacy_calculate
from report_service import html_report, evidence_package, csv_bytes
from replay_screening import replay
from foundation import create_app
from test_performance_service import inputs, config
from test_climate_service import fixture


def result(life=True, economics=False):
    frozen=inputs()
    cfg=config()
    if life:cfg['lifetime']={'years':25,'degradation_pct':.5}
    if economics:
        cfg['ac']=dict(dc_ac_ratio=1.2,efficiency=.96,availability=.99,curtailment=0)
        ids=[m['module_id'] for m in frozen['modules']]
        cfg['economics']=dict(reference_id=ids[0],energy_value_eur_kwh=.1,discount_rate_pct=5,quotes_eur_w={mid:.3 for mid in ids},incremental_cost_pv_eur_w={mid:0 for mid in ids})
    r=calculate(frozen,cfg)
    return {**r,'id':'synthetic-report-test','created_at':'2026-09-15','site':frozen['site'],'selected_modules':frozen['modules'],'frozen_inputs':frozen,'catalog_release':'synthetic-test','climate_snapshot':{'provider':'PVGIS','year':2023,'crosscheck':{'pvgis_annual_ghi_kwh_m2':876,'nasa_annual_ghi_kwh_m2':850,'difference_pct':-2.968,'status':'AVAILABLE'}}}


def test_catalog_count_sources_and_unknowns():
    records=catalog()['modules']
    assert len(records)>=12 and len({m['module_id'] for m in records})==len(records)
    assert sum(m['commercial_status']=='COMMERCIAL' for m in records)>=12
    assert len({m['technology_family'] for m in records})>=8
    assert all(m['source_url'].startswith('https://') and m['source_checked_at']=='2026-09-15' for m in records)
    assert all(m['decision_eligibility']=='SCREENING_ONLY' and m['electrical_evidence'] is None for m in records)
    assert any(g['decision_status']=='EVIDENCE_GATED' for g in families())
    assert all(m['application']=='BIPV_FACADE' for m in records if m['technology_family']=='CIGS')
    assert any(m['datasheet_revision'] is None for m in records)


def test_v2_neutrality_and_legacy_energy_preservation():
    f=inputs();old=legacy_calculate(f,config());new=calculate(f,config())
    assert [(r['module_id'],r['annual_dc_kwh_kwp']) for r in old['decision']['ranking']]==[(r['module_id'],r['annual_dc_kwh_kwp']) for r in new['decision']['ranking']]
    for m in f['modules']:
        m.update(manufacturer='arbitrary',model='renamed',technology_family='arbitrary',cell_architecture='arbitrary',technology_subtype='arbitrary')
    f['modules'].reverse()
    renamed=calculate(f,config())
    assert [(r['module_id'],r['annual_dc_kwh_kwp']) for r in renamed['decision']['ranking']]==[(r['module_id'],r['annual_dc_kwh_kwp']) for r in new['decision']['ranking']]
    assert new['decision']['strength_policy']=='conservative-evidence-ceiling-1.0'


def test_application_and_region_gates():
    f=inputs();cigs=deepcopy(catalog()['modules'][-1]);f['modules'].append(cigs)
    r=calculate(f,config())
    assert any(v['module_id']==cigs['module_id'] and 'Facade-only' in v['reason'] for v in r['candidate_failures'])
    r=calculate(f,config(application='BIPV_FACADE',market_region='AU'))
    assert [v['module_id'] for v in r['decision']['ranking']]==[cigs['module_id']]
    r=calculate(f,config(application='BIPV_FACADE',market_region='US'))
    assert not r['decision']['ranking']


def measured_module():
    return {'module_id':'SYNTHETIC_TEST_ONLY','rated_power_w':100.,'electrical_evidence':{
        'module_id':'SYNTHETIC_TEST_ONLY','review_status':'APPROVED','source_url':'https://example.invalid/synthetic-test',
        'reviewed_by':'synthetic fixture','reviewed_at':'2026-09-15','scope':'Synthetic software test only',
        'kind':'IEC61853','matrix':[{'irradiance_w_m2':g,'module_temperature_c':t,'pmax_w':100*g/1000*(1-.003*(t-25))} for g in [100,200,1000] for t in [25,50,75]]}}


def test_a_route_anchors_domain_and_missing_evidence():
    m=measured_module();p,meta=power(m,[0,1000,500,1200],[20,25,50,80],core.pvwatts_dc_power_kw_per_kwp)
    assert p[0]==0 and p[1]==pytest.approx(1)
    assert meta['model_path'].startswith('A_')
    assert meta['extrapolation_fraction']==pytest.approx(1/3)
    m['electrical_evidence']['module_id']='different'
    with pytest.raises(ValueError,match='SKU identity'):power(m,[1000],[25],core.pvwatts_dc_power_kw_per_kwp)
    m['electrical_evidence']=None
    with pytest.raises(ValueError,match='temperature coefficient'):power(m,[1000],[25],core.pvwatts_dc_power_kw_per_kwp)


def test_b_route_validated_parameters_not_datasheet_fit():
    import pvlib
    coefficients=dict(alpha_sc_A_C=.005,a_ref=1.5,I_L_ref=10.,I_o_ref=1e-10,R_sh_ref=500.,R_s=.3,Adjust=0.)
    params=pvlib.pvsystem.calcparams_cec(1000,25,alpha_sc=.005,a_ref=1.5,I_L_ref=10.,I_o_ref=1e-10,R_sh_ref=500.,R_s=.3,Adjust=0.)
    pmax=float(pvlib.pvsystem.singlediode(*params)['p_mp'])
    m=measured_module();m['rated_power_w']=pmax
    m['electrical_evidence'].update(kind='CEC_VALIDATED',coefficients=coefficients,validated_domain=dict(g_min=100,g_max=1100,t_min=15,t_max=75))
    p,meta=power(m,[0,1000,1200],[25,25,80],core.pvwatts_dc_power_kw_per_kwp)
    assert p[0]==0 and p[1]==pytest.approx(1)
    assert meta['model_path'].startswith('B_') and meta['extrapolation_fraction']==.5
    m['rated_power_w']*=2
    with pytest.raises(ValueError,match='STC output'):power(m,[1000],[25],core.pvwatts_dc_power_kw_per_kwp)


def test_report_offline_25_year_exact_values_and_package_integrity():
    r=result(economics=True);before=deepcopy(r);html=html_report(r)
    assert '25-year common degradation sensitivity' in html
    assert 'data:image/png;base64,' in html
    assert not re.search(r'<(?:script|link|iframe)\b',html,re.I)
    assert not re.search(r'(?:src|href)="https?://',html)
    assert len(re.findall(r'<svg\b',html))>=5
    for row in r['decision']['top_three']:
        for value in row['annual_lifetime']:
            assert f'data-y="{value["dc_kwh_kwp"]}"' in html
        assert row['cumulative_lifetime'][-1]['dc_kwh_kwp']==row['lifetime_dc_kwh_kwp']
    with zipfile.ZipFile(io.BytesIO(evidence_package(r))) as z:
        root='SOLARYN_synthetic-report-test/'
        manifest=json.loads(z.read(root+'manifest.json'))
        assert 'lifetime_25y.csv' in manifest['files'] and 'economics.csv' in manifest['files']
        assert json.loads(z.read(root+'result.json'))==r
        for name,checksum in manifest['files'].items():assert hashlib.sha256(z.read(root+name)).hexdigest()==checksum
    assert r==before
    assert replay(r)['status']=='REPRODUCED'


def test_omitted_scenarios_and_injection_escaping():
    r=result(life=False)
    r['decision']['ranking'][0]['model']='<script>alert(1)</script>'
    html=html_report(r)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '25-year common degradation sensitivity' not in html
    with zipfile.ZipFile(io.BytesIO(evidence_package(r))) as z:
        assert not any('lifetime_' in n or 'economics.csv' in n for n in z.namelist())
    assert "'=cmd" in csv_bytes(['x'],[['=cmd']]).decode('utf-8-sig')


def test_download_routes_preserve_completed_record(tmp_path):
    def fetch(provider,params):return json.dumps(fixture(provider)).encode()
    c=TestClient(create_app(tmp_path/'runs.db',climate_fetcher=fetch))
    site=c.post('/api/v1/sites',json={'latitude':0,'longitude':0}).json()
    c.post(f'/api/v1/sites/{site["id"]}/climate-snapshot',json={'year':2023})
    pending=c.post('/api/v1/analyses',json={'site_id':site['id'],'module_ids':[m['module_id'] for m in catalog()['modules'][:3]]}).json()
    assert c.get(f'/api/v1/analyses/{pending["id"]}/report').status_code==409
    r=c.post(f'/api/v1/analyses/{pending["id"]}/run',json=config(lifetime={'years':25,'degradation_pct':.5})).json()
    base=f'/api/v1/analyses/{r["id"]}'
    original=c.get(base+'/export').content
    assert c.get(base+'/visuals').status_code==200
    for path,content_type in [('report','text/html'),('package','application/zip')]:
        response=c.get(base+'/'+path)
        assert response.status_code==200,response.text
        assert response.headers['content-type'].startswith(content_type)
        assert response.headers['content-disposition'].startswith('attachment;')
    assert c.get(base+'/export').content==original
