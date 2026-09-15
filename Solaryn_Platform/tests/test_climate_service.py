"""Synthetic software fixtures; not measured scientific validation data."""
from calendar import isleap
from datetime import datetime, timedelta
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from climate_service import ClimateService, normalize
from foundation import create_app


def fixture(provider, year=2023, irradiance=100):
    dates = [datetime(year, 1, 1) + timedelta(hours=i) for i in range((366 if isleap(year) else 365) * 24)]
    if provider == 'NASA_POWER':
        values = {'ALLSKY_SFC_SW_DWN': irradiance, 'ALLSKY_SFC_SW_DNI': 50, 'ALLSKY_SFC_SW_DIFF': 50, 'T2M': 20, 'WS10M': 3, 'RH2M': 70}
        return {'header': {'time_standard': 'UTC', 'fill_value': -999, 'api': {'version': 'synthetic'}, 'sources': ['SYNTHETIC_TEST_ONLY']},
                'parameters': {key: {'units': 'Wh/m^2' if key.startswith('ALLSKY') else {'T2M':'C','WS10M':'m/s','RH2M':'%'}[key]} for key in values},
                'properties': {'parameter': {key: {date.strftime('%Y%m%d%H'): value for date in dates} for key,value in values.items()}}}
    return {'inputs': {'location': {'latitude': 0, 'longitude': 0}, 'meteo_data': {'use_horizon': False, 'radiation_db': 'SYNTHETIC_TEST_ONLY'}, 'mounting_system': {'fixed': {'slope': {'value': 0}}}},
            'meta': {'outputs': {'hourly': {'variables': {key: {'units':unit} for key,unit in [('Gb(i)','W/m2'),('Gd(i)','W/m2'),('Gr(i)','W/m2'),('T2m','degree Celsius'),('WS10m','m/s')]}}}},
            'outputs': {'hourly': [{'time': date.strftime('%Y%m%d:%H04'), 'Gb(i)':irradiance/2, 'Gd(i)':irradiance/2, 'Gr(i)':0, 'T2m':20, 'WS10m':3, 'Int':0} for date in dates]}}


@pytest.mark.parametrize('provider', ['PVGIS', 'NASA_POWER'])
@pytest.mark.parametrize('year', [2023,2024])
def test_hourly_units_leap_year_and_hand_calculated_totals(provider, year):
    result = normalize(provider, fixture(provider, year), year)
    hours = 8784 if year == 2024 else 8760
    assert result['metrics']['annual_ghi'] == pytest.approx(hours * .1)
    assert result['monthly'][0]['ghi_kwh_m2'] == 74.4
    assert result['monthly'][1]['ghi_kwh_m2'] == pytest.approx((29 if year == 2024 else 28) * 2.4)
    assert result['metrics']['air_temperature'] == 20
    assert result['metrics']['wind_speed'] == 3
    assert result['metrics']['relative_humidity'] == (70 if provider == 'NASA_POWER' else None)
    assert result['hourly'][0]['timestamp_utc'].endswith('04:00+00:00' if provider == 'PVGIS' else '00:00:00+00:00')
    assert result['complete_ghi'] is True


def test_missing_hours_and_sentinels_never_become_zero():
    payload = fixture('NASA_POWER')
    payload['properties']['parameter']['ALLSKY_SFC_SW_DWN']['2023010100'] = -999
    result = normalize('NASA_POWER', payload, 2023)
    assert result['metrics']['annual_ghi'] is None
    assert result['monthly'][0]['ghi_kwh_m2'] is None
    assert result['monthly'][1]['ghi_kwh_m2'] == 67.2
    assert result['hourly'][0]['ghi_w_m2'] is None
    assert result['coverage']['valid_hours']['ghi_w_m2'] == 8759
    pvgis = fixture('PVGIS')
    pvgis['outputs']['hourly'].pop(0)
    assert normalize('PVGIS', pvgis, 2023)['metrics']['annual_ghi'] is None


@pytest.mark.parametrize('change', ['duplicate', 'year', 'geometry', 'units', 'offset'])
def test_invalid_provider_response_rejected(change):
    payload = fixture('PVGIS')
    if change == 'duplicate': payload['outputs']['hourly'].append(payload['outputs']['hourly'][0])
    if change == 'year': payload['outputs']['hourly'][0]['time'] = '20220101:0004'
    if change == 'geometry': payload['inputs']['mounting_system']['fixed']['slope']['value'] = 30
    if change == 'units': payload['meta']['outputs']['hourly']['variables']['Gb(i)']['units'] = 'kWh/m2/day'
    if change == 'offset': payload['outputs']['hourly'][0]['time'] = '20230101:0030'
    with pytest.raises(ValueError): normalize('PVGIS', payload, 2023)


def test_nasa_requires_utc_and_invalid_values_are_missing():
    payload = fixture('NASA_POWER')
    payload['header']['time_standard'] = 'LST'
    with pytest.raises(ValueError): normalize('NASA_POWER', payload, 2023)
    payload['header']['time_standard'] = 'UTC'
    payload['properties']['parameter']['RH2M']['2023010100'] = 101
    payload['properties']['parameter']['WS10M']['2023010100'] = -1
    result = normalize('NASA_POWER', payload, 2023)
    assert result['hourly'][0]['relative_humidity_pct'] is None
    assert result['hourly'][0]['wind_speed_m_s'] is None


def test_cached_sources_raw_hashes_crosscheck_and_frozen_analysis(tmp_path):
    calls = []
    raw = {p: json.dumps(fixture(p, irradiance=100 if p=='PVGIS' else 110)).encode() for p in ['PVGIS','NASA_POWER']}
    def fetch(provider, query):
        calls.append((provider, query))
        return raw[provider]
    path = tmp_path / 'climate.sqlite3'
    c = TestClient(create_app(path, climate_fetcher=fetch))
    site = c.post('/api/v1/sites',json={'latitude':-11.23456789,'longitude':22.987654321}).json()
    url = f"/api/v1/sites/{site['id']}/climate-snapshot"
    assert c.get(url).json()['status'] == 'NOT_REQUESTED'
    first = c.post(url,json={'year':2023}).json()
    assert first['status'] == 'AVAILABLE'
    assert first['provider'] == 'PVGIS'
    assert first['metrics']['annual_ghi'] == 876
    assert first['metrics']['relative_humidity'] == 70
    assert first['metric_sources']['relative_humidity'] == 'NASA_POWER'
    assert first['crosscheck']['difference_pct'] == pytest.approx(10)
    assert len(calls) == 2
    for provider, query in calls:
        assert query.get('lat', query.get('latitude')) == site['latitude']
        assert query.get('lon', query.get('longitude')) == site['longitude']
    modules = [m['module_id'] for m in c.get('/api/v1/modules').json()['modules'][:3]]
    analysis = c.post('/api/v1/analyses', json={'site_id':site['id'],'module_ids':modules}).json()
    assert analysis['climate_snapshot']['id'] == first['id']
    second = c.post(url,json={'year':2023}).json()
    assert second['id'] != first['id']
    assert len(calls) == 2
    assert all(p['cache_hit'] for p in second['providers'])
    c.post(url,json={'year':2023,'refresh':True})
    assert len(calls) == 4
    assert c.get('/api/v1/analyses/'+analysis['id']).json()['climate_snapshot'] == analysis['climate_snapshot']
    for p in first['providers']:
        source = c.get('/api/v1/climate-sources/'+p['source_id']+'/export?raw=true')
        assert source.content == raw[p['provider']]
        assert hashlib.sha256(source.content).hexdigest() == p['raw_sha256']
        hourly = c.get('/api/v1/climate-sources/'+p['source_id']+'/export').json()
        assert len(hourly['hourly']) == 8760
        assert hourly['canonical_units']['ghi_w_m2'] == 'W/m²'
    restarted = TestClient(create_app(path, climate_fetcher=fetch))
    assert restarted.get(url).json()['id'] != first['id']
    assert restarted.get('/api/v1/climate-sources/'+first['providers'][0]['source_id']+'/export').status_code == 200
    assert c.post(url,json={'year':1900}).status_code == 422


@pytest.mark.parametrize('failed', [['PVGIS'],['NASA_POWER'],['PVGIS','NASA_POWER']])
def test_provider_errors_are_independent_and_retryable(tmp_path, failed):
    raw = {p:json.dumps(fixture(p)).encode() for p in ['PVGIS','NASA_POWER']}
    def fetch(provider, query):
        if provider in failed: raise ValueError('Provider unavailable for requested coordinate')
        return raw[provider]
    path = tmp_path/'sources.sqlite3'
    service = ClimateService(path,fetch)
    result = service.retrieve({'id':'anonymous','latitude':0,'longitude':0},2023)
    assert result['status'] == ('UNAVAILABLE' if len(failed)==2 else 'PARTIAL')
    assert result['crosscheck']['difference_pct'] is None
    if failed == ['PVGIS']: assert result['provider'] == 'NASA_POWER'
    assert all(p['source_id'] is None for p in result['providers'] if p['provider'] in failed)
    service.fetcher = lambda provider,query: raw[provider]
    assert service.retrieve({'id':'anonymous','latitude':0,'longitude':0},2023)['status'] == 'AVAILABLE'


def test_zero_annual_reference_does_not_divide_by_zero(tmp_path):
    raw = {p:json.dumps(fixture(p,irradiance=0)).encode() for p in ['PVGIS','NASA_POWER']}
    result = ClimateService(tmp_path/'zero.sqlite3',lambda provider,query:raw[provider]).retrieve({'id':'zero','latitude':0,'longitude':0},2023)
    assert result['crosscheck']['difference_pct'] is None
    assert result['metrics']['annual_ghi'] == 0
