import io
import zipfile
import numpy as np
import pytest
from physics_worker import ac_from_dc
from test_platform import register, create_project, detail
from server import create_app


def test_ac_hand_calculation_and_conservation():
    ac, loss=ac_from_dc([0,1,2],[1,1,1],2,.9,.8,.1)
    assert np.allclose(ac,[0,.36,.36])
    assert loss['net_ac_kwh_kwp']==pytest.approx(.72)
    assert loss['dc_kwh_kwp']==pytest.approx(sum(v for k,v in loss.items() if k!='dc_kwh_kwp'))
    with pytest.raises(ValueError): ac_from_dc([np.nan],[1],1,.9,1,0)


def test_real_physics_api_preserves_validation_and_tenant_scope(tmp_path):
    app=create_app(tmp_path/'db.sqlite3')
    c=register(app)
    other=register(app,'other-physics@example.test')
    pid=create_project(c)
    d=detail(c,pid)
    c.put(f'/api/v1/projects/{pid}',json={'parameters':d['parameters'],'latitude':24.7136,'longitude':46.6753,'revision':d['revision']})
    ids=['MOD_TOPCON_JINKO_JKM575N_72HL4_V','MOD_PERC_LONGI_LR5_72HPH_550M','MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530']
    body={'revision':detail(c,pid)['revision'],'module_ids':ids,'quotes_eur_w':{m:.12 for m in ids}}
    response=c.post(f'/api/v1/projects/{pid}/physics',json=body)
    assert response.status_code==201,response.text
    result=response.json()['result']
    expected={ids[0]:2073.433038,ids[1]:2034.997755,ids[2]:2048.638261}
    for r in result['ac_energy']:
        assert r['dc_kwh_kwp']==pytest.approx(expected[r['module_id']],abs=.001)
        assert 0<r['net_ac_kwh_kwp']<r['dc_kwh_kwp']
        assert sum(r['monthly_ac'].values())==pytest.approx(r['net_ac_kwh_kwp'])
    assert result['measured_validation']['retained_rows']==28286
    assert result['measured_validation']['rmse_w']==pytest.approx(18.163253,abs=.00001)
    assert len(result['measured_validation']['input_hashes'])==13
    assert result['physics']['decision']['status']=='INSUFFICIENT_EVIDENCE'
    assert result['physics']['validation_gates']['bankability']=='NOT_CLAIMED'
    assert result['economics']['status'].startswith('Exploratory')
    chain=result['decision_chain']
    assert chain['schema_version']=='decision-chain-2.0'
    assert len(chain['physical']['ranking'])==3
    assert len(chain['commercial']['ranking'])==3
    assert chain['physical']['status']=='UNRESOLVED_WITHIN_GUARDRAIL'
    assert chain['recommendation']['recommended_module_id'] is None
    assert chain['physical']['ranking'][0]['temperature_response_pct'] is not None
    for candidate in result['economics']['candidates']:
        match=next(r for r in result['ac_energy'] if r['module_id']==candidate['name'])
        assert candidate['net_ac_kwh_kwp']==match['net_ac_kwh_kwp']
    rid=response.json()['id']
    url=f'/api/v1/projects/{pid}/physics/{rid}'
    assert c.get(url).json()['result']==result
    assert other.get(url).status_code==404
    assert other.get(url+'/download').status_code==404
    assert other.get(f'/api/v1/projects/{pid}/physics').status_code==404
    z=zipfile.ZipFile(io.BytesIO(c.get(url+'/download').content))
    assert z.testzip() is None
    assert 'Hourly-DC-AC.csv' in z.namelist()
    assert 'Measured-validation-monthly.csv' in z.namelist()
    assert any(n.endswith('inputs/NASA-hourly.csv') for n in z.namelist())
    with pytest.raises(KeyError): z.getinfo('../outside')
    folder=next((tmp_path/'physics').glob(f'*/{pid}/{rid}'))
    (folder/'Hourly-DC-AC.csv').write_text('tampered')
    assert c.get(url).status_code==409
    assert c.get(url+'/download').status_code==409


def test_recorded_weather_not_relocated(tmp_path):
    c=register(create_app(tmp_path/'db.sqlite3'))
    pid=create_project(c)
    r=c.post(f'/api/v1/projects/{pid}/physics',json={'revision':1,'module_ids':['MOD_TOPCON_JINKO_JKM575N_72HL4_V','MOD_PERC_LONGI_LR5_72HPH_550M']})
    assert r.status_code==422
    assert 'coordinates' in r.json()['detail']
