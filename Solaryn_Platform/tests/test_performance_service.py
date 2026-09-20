"""Synthetic invariants and hand calculations; not external model validation."""
from copy import deepcopy
import base64
import hashlib
import json
import math

import numpy as np
import pytest
from auth_helpers import admin_client

from foundation import catalog, create_app
from performance_service import Configuration, AC, Lifetime, calculate, ac_output, lifetime_rows, rank, digest
from test_climate_service import fixture
from climate_service import normalize, GEOMETRY


def config(**changes):
    return dict(objective='annual_dc', tilt_deg=0, azimuth_deg=180, albedo=.2,
                soiling_pct=0, u0=25, u1=6.84, wind_factor=1, **changes)


def inputs():
    source = normalize('PVGIS', fixture('PVGIS', irradiance=100), 2023)
    source.update(year=2023, sample_duration_hours=1, time_standard='UTC',
                  requested_location={'latitude':0,'longitude':0}, canonical_units={'ghi_w_m2':'W/m²','air_temperature_c':'°C','wind_speed_m_s':'m/s'}, geometry=GEOMETRY)
    return {'site': {'latitude':0,'longitude':0}, 'source':source, 'modules':deepcopy(catalog()['modules'][:4])}


def test_horizontal_hand_calculation_monthly_and_existing_kernel():
    frozen = inputs()
    result = calculate(frozen, config())
    assert len(result['decision']['top_three']) == 3
    temperature = 20 + 100 / (25 + 6.84 * 3)
    for row in result['decision']['ranking']:
        module = next(m for m in frozen['modules'] if m['module_id'] == row['module_id'])
        expected = 8760 * .1 * (1 + module['temperature_coefficient_pct_per_c'] / 100 * (temperature - 25))
        assert row['annual_dc_kwh_kwp'] == pytest.approx(expected)
        assert sum(m['dc_kwh_kwp'] for m in row['monthly']) == pytest.approx(expected)
        assert row['annual_dc_kwh_module'] == pytest.approx(expected * module['rated_power_w'] / 1000)
        assert row['extrapolation_fraction'] is None
        assert row['lifetime_dc_kwh_kwp'] is None
        assert row['quote_eur_w'] is None
    assert result['decision']['strength'] == 'MARGINAL'
    assert result['manifest']['inputs_sha256'] == digest(frozen)
    assert calculate(frozen, config()) == result


def test_names_family_order_and_identical_input_invariance():
    frozen = inputs()
    first = calculate(frozen, config())
    original = {r['module_id']:r['annual_dc_kwh_kwp'] for r in first['decision']['ranking']}
    frozen['modules'].reverse()
    for m in frozen['modules']:
        m.update(manufacturer='Renamed',model='Renamed',technology='arbitrary family')
    changed = calculate(frozen, config())
    assert {r['module_id']:r['annual_dc_kwh_kwp'] for r in changed['decision']['ranking']} == original
    assert changed['decision']['recommended_candidate'] == first['decision']['recommended_candidate']
    for m in frozen['modules']:
        m['temperature_coefficient_pct_per_c'] = -.3
    tied = calculate(frozen, config())['decision']
    assert len(tied['co_leaders']) == 4
    assert tied['recommended_candidate'] == min(m['module_id'] for m in frozen['modules'])


def test_common_loss_and_hot_cold_crossover():
    frozen = inputs()
    clean = calculate(frozen, config())
    dirty_config = config()
    dirty_config['soiling_pct'] = 10
    dirty = calculate(frozen, dirty_config)
    assert [r['module_id'] for r in clean['decision']['ranking']] == [r['module_id'] for r in dirty['decision']['ranking']]
    for a,b in zip(clean['decision']['ranking'], dirty['decision']['ranking']):
        assert b['annual_dc_kwh_kwp'] == pytest.approx(a['annual_dc_kwh_kwp'] * .9)
    for hour in frozen['source']['hourly']:
        hour['air_temperature_c'] = 45
    hot = calculate(frozen, config())
    assert hot['decision']['recommended_candidate'] != clean['decision']['recommended_candidate']
    assert max(r['annual_dc_kwh_kwp'] for r in hot['decision']['ranking']) < min(r['annual_dc_kwh_kwp'] for r in clean['decision']['ranking'])


@pytest.mark.parametrize('defect',['missing_temp','missing_hour','duplicate','wrong_site','units','zero_resource'])
def test_bad_resource_is_never_filled(defect):
    frozen = inputs()
    if defect == 'missing_temp': frozen['source']['hourly'][5]['air_temperature_c'] = None
    if defect == 'missing_hour': frozen['source']['hourly'].pop()
    if defect == 'duplicate': frozen['source']['hourly'][1] = frozen['source']['hourly'][0]
    if defect == 'wrong_site': frozen['site']['latitude'] = 1
    if defect == 'units': frozen['source']['canonical_units'] = {'ghi_w_m2':'kWh/m2'}
    if defect == 'zero_resource':
        for h in frozen['source']['hourly']: h['ghi_w_m2'] = 0
    with pytest.raises(ValueError): calculate(frozen, config())


def test_infeasible_modules_are_visible_and_all_invalid_cannot_recommend():
    frozen = inputs()
    frozen['modules'][0]['rated_power_w'] = None
    result = calculate(frozen, config())
    assert len(result['candidate_failures']) == 1
    assert len(result['decision']['ranking']) == 3
    for m in frozen['modules']: m['rated_power_w'] = None
    result = calculate(frozen, config())
    assert result['decision']['status'] == 'CANNOT_RECOMMEND'
    assert result['decision']['recommended_candidate'] is None


def test_ac_energy_balance_and_lifetime_hand_math():
    ac = AC(dc_ac_ratio=2,efficiency=.9,availability=.8,curtailment=.1)
    power = np.array([0,.2,1.2])
    net, losses = ac_output(power, ac)
    assert net.tolist() == pytest.approx([0,.1296,.36])
    assert power.sum() == pytest.approx(net.sum() + sum(losses.values()))
    rows = lifetime_rows(1000,800,Lifetime(years=3,degradation_pct=1))
    assert [r['dc_kwh_kwp'] for r in rows] == pytest.approx([1000,990,980.1])
    assert [r['ac_kwh_kwp'] for r in rows] == pytest.approx([800,792,784.08])


def test_economic_threshold_reference_invariance_and_quote_crossover():
    def candidates():
        return [{'module_id':mid,'annual_dc_kwh_kwp':annual,'annual_ac_kwh_kwp':annual,
                 'annual_lifetime':lifetime_rows(annual,annual,Lifetime(years=2,degradation_pct=0))}
                for mid,annual in [('a',1100),('b',1000),('c',900)]]
    cfg = config(ac=dict(dc_ac_ratio=1,efficiency=1,availability=1,curtailment=0),lifetime=dict(years=2,degradation_pct=0),
                 economics=dict(reference_id='b',energy_value_eur_kwh=.1,discount_rate_pct=0,quotes_eur_w={'a':.51,'b':.5,'c':.5},incremental_cost_pv_eur_w={'a':0,'b':0,'c':0}))
    cfg['objective'] = 'procurement_headroom'
    result = rank(candidates(),Configuration(**cfg))
    a = result['ranking'][0]
    assert a['max_premium_eur_w'] == pytest.approx(.02)
    assert a['headroom_eur_w'] == pytest.approx(.01)
    cfg['economics']['reference_id'] = 'c'
    assert rank(candidates(),Configuration(**cfg))['recommended_candidate'] == 'a'
    cfg['economics']['quotes_eur_w']['a'] = .55
    assert rank(candidates(),Configuration(**cfg))['recommended_candidate'] == 'b'
    cfg['economics']['discount_rate_pct'] = 10
    cfg['economics']['reference_id'] = 'b'
    result = rank(candidates(),Configuration(**cfg))
    a = next(r for r in result['ranking'] if r['module_id']=='a')
    assert a['max_premium_eur_w'] == pytest.approx(.01/1.1+.01/1.1**2)


@pytest.mark.parametrize('change',[{'objective':'annual_ac'},{'objective':'lifetime_dc'},{'objective':'procurement_headroom'},{'u0':0},{'wind_factor':float('nan')},{'azimuth_deg':360}])
def test_configuration_rejects_missing_dependencies_or_invalid_assumptions(change):
    cfg = config(); cfg.update(change)
    with pytest.raises(ValueError): Configuration(**cfg)


def test_api_immutable_completion_freezes_inputs_and_survives_restart(tmp_path):
    def fetch(provider, params): return json.dumps(fixture(provider)).encode()
    db = tmp_path/'runs.sqlite3'
    client = admin_client(db, climate_fetcher=fetch)
    site = client.post('/api/v1/sites',json={'latitude':0,'longitude':0}).json()
    mids = [m['module_id'] for m in catalog()['modules'][:4]]
    old = client.post('/api/v1/analyses',json={'site_id':site['id'],'module_ids':mids}).json()
    assert client.post(f"/api/v1/analyses/{old['id']}/run",json=config()).status_code == 422
    climate = client.post(f"/api/v1/sites/{site['id']}/climate-snapshot",json={'year':2023}).json()
    pending = client.post('/api/v1/analyses',json={'site_id':site['id'],'module_ids':mids}).json()
    response = client.post(f"/api/v1/analyses/{pending['id']}/run",json=config())
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['status'] == 'COMPLETED'
    assert result['id'] != pending['id']
    assert len(result['frozen_inputs']['source']['hourly']) == 8760
    assert result['climate_snapshot']['id'] == climate['id']
    assert client.get(f"/api/v1/analyses/{pending['id']}").json() == pending
    restarted = admin_client(db, climate_fetcher=fetch)
    assert restarted.get(f"/api/v1/analyses/{result['id']}/export").json() == result
    rerun = restarted.post(f"/api/v1/analyses/{result['id']}/run",json=config()).json()
    assert rerun['decision'] == result['decision']
    assert rerun['manifest'] == result['manifest']
    assert rerun['id'] != result['id']
    from replay_screening import replay
    assert replay(result)['status'] == 'REPRODUCED'
    for path, content in result['implementation_sources'].items():
        assert hashlib.sha256(base64.b64decode(content)).hexdigest() == result['manifest']['code_sha256'][path]
    corrupt = deepcopy(result)
    corrupt['configuration']['soiling_pct'] = 99
    with pytest.raises(ValueError, match='Configuration checksum'):
        replay(corrupt)


def test_tilted_pvgis_and_nasa_have_finite_monthly_outputs():
    for provider in ('PVGIS','NASA_POWER'):
        frozen = inputs()
        data = normalize(provider, fixture(provider),2023)
        frozen['source'].update(data)
        cfg = config(); cfg['tilt_deg']=25
        result = calculate(frozen,cfg)
        assert all(math.isfinite(r['annual_dc_kwh_kwp']) and r['annual_dc_kwh_kwp']>0 for r in result['decision']['ranking'])


def test_full_optional_calculation_uses_supplied_boundary():
    frozen = inputs()
    mids = [m['module_id'] for m in frozen['modules']]
    cfg = config(ac=dict(dc_ac_ratio=1.2,efficiency=.96,availability=.99,curtailment=.01),
                 lifetime=dict(years=2,degradation_pct=.5),
                 economics=dict(reference_id=mids[0],energy_value_eur_kwh=.1,discount_rate_pct=5,
                                quotes_eur_w={mid:.3 for mid in mids},incremental_cost_pv_eur_w={mid:0 for mid in mids}))
    cfg['objective'] = 'procurement_headroom'
    result = calculate(frozen,cfg)
    for row in result['decision']['ranking']:
        assert row['annual_ac_kwh_kwp'] < row['annual_dc_kwh_kwp']
        assert row['lifetime_dc_kwh_kwp'] == pytest.approx(row['annual_dc_kwh_kwp']*1.995)
        assert row['quote_eur_w'] == .3
        assert math.isfinite(row['headroom_eur_w'])
    reference = next(r for r in result['decision']['ranking'] if r['module_id']==mids[0])
    assert reference['headroom_eur_w'] == 0
    del cfg['economics']['quotes_eur_w'][mids[1]]
    with pytest.raises(ValueError, match='Supply a quote'):
        calculate(frozen,cfg)
