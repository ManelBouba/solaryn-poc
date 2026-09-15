import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from foundation import create_app, catalog


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "foundation.sqlite3"))


@pytest.mark.parametrize("latitude,longitude", [(90, 180), (-90, -180), (0, 0), (-12.123456789, 67.987654321)])
def test_coordinate_roundtrip(client, latitude, longitude):
    response = client.post('/api/v1/sites', json=dict(latitude=latitude, longitude=longitude))
    assert response.status_code == 201
    site = response.json()
    assert (site['latitude'], site['longitude']) == (latitude, longitude)
    assert client.get('/api/v1/sites/' + site['id']).json() == site
    snapshot = client.get(f"/api/v1/sites/{site['id']}/climate-snapshot").json()
    assert snapshot['site'] == site
    assert snapshot['status'] == 'NOT_REQUESTED'
    assert snapshot['provider'] is None
    assert all(v is None for v in snapshot['metrics'].values())
    assert snapshot['units']['wind_speed'] == 'm/s'


@pytest.mark.parametrize('payload', [dict(latitude=91, longitude=0), dict(latitude=0, longitude=-181), dict(latitude='', longitude=0), dict(latitude='NaN', longitude=0), dict(latitude='Infinity', longitude=0), dict(latitude=0), dict(latitude=0, longitude=0, city='ignored')])
def test_invalid_coordinates_rejected(client, payload):
    assert client.post('/api/v1/sites', json=payload).status_code == 422
    assert client.get('/api/v1/sites').json() == []


def test_persisted_request_has_no_fake_science_and_is_immutable(tmp_path):
    db = tmp_path / 'persistent.sqlite3'
    c = TestClient(create_app(db))
    site = c.post('/api/v1/sites', json=dict(latitude=0.1234, longitude=-78.4321)).json()
    ids = [m['module_id'] for m in catalog()['modules'][:3]]
    payload = dict(site_id=site['id'], module_ids=ids)
    response = c.post('/api/v1/analyses', json=payload)
    assert response.status_code == 201
    result = response.json()
    assert result['decision'] == dict(recommended_candidate=None, strength=None, ranking=[])
    assert result['contributions'] == []
    assert result['site'] == site
    assert len(result['catalog_release'].split('+')[-1]) == 64
    assert len(result['selected_modules']) == 3
    assert c.post('/api/v1/analyses', json=payload).json()['id'] != result['id']
    assert c.put('/api/v1/analyses/' + result['id'], json={}).status_code == 405
    restarted = TestClient(create_app(db))
    assert restarted.get('/api/v1/analyses/' + result['id']).json() == result
    exported = restarted.get('/api/v1/analyses/' + result['id'] + '/export')
    assert exported.json() == result
    assert exported.headers['content-disposition'].startswith('attachment;')
    assert restarted.get('/api/v1/sites').json() == [site]


def test_analysis_rejects_missing_site_unknown_and_duplicate_modules(client):
    ids = [m['module_id'] for m in catalog()['modules'][:3]]
    assert client.post('/api/v1/analyses', json=dict(site_id='missing', module_ids=ids)).status_code == 404
    site = client.post('/api/v1/sites', json=dict(latitude=0, longitude=0)).json()
    for modules in [ids[:2], [ids[0]] * 3, ['unknown', *ids[:2]], ids * 4]:
        assert client.post('/api/v1/analyses', json=dict(site_id=site['id'], module_ids=modules)).status_code == 422


def test_catalog_preserves_unknowns_and_sources(client):
    result = client.get('/api/v1/modules').json()
    assert len(result['modules']) >= 3
    assert any(m['commercial_status'] == 'UNKNOWN' for m in result['modules'])
    assert all(m['electrical_evidence'] is None for m in result['modules'])
    assert all(m['independent_field_data_available'] is None for m in result['modules'])
    assert all(m['source_url'] for m in result['modules'])
    assert len(client.get('/api/v1/technology-families').json()) >= 8


def test_routes_assets_origin_and_contract(client):
    for route in ['', 'site', 'conditions', 'candidates', 'processing', 'results', 'evidence']:
        assert client.get('/' + route).status_code == 200
    assert client.get('/missing').status_code == 404
    assert client.get('/api/v1/sites/missing/climate-snapshot').status_code == 404
    logo = Path(__file__).resolve().parents[2] / 'frontend/public/brand/solaryn-logo.png'
    assert client.get('/brand/solaryn-logo.png').content == logo.read_bytes()
    assert client.get('/assets/vendor/leaflet.js').status_code == 200
    assert client.post('/api/v1/sites', json=dict(latitude=0, longitude=0), headers={'Origin': 'https://unrelated.example'}).status_code == 403
    expected = json.loads((Path(__file__).resolve().parents[2] / 'docs/foundation-openapi.json').read_text(encoding='utf-8'))
    assert client.get('/openapi.json').json() == expected
