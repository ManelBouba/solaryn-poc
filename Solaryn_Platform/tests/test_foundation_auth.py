import hashlib
import sqlite3
import pytest
from fastapi.testclient import TestClient
from foundation import create_app
from foundation_auth import COOKIE, password_hash
from auth_helpers import TEST_HASH, TEST_PASSWORD


@pytest.fixture
def protected(tmp_path, monkeypatch):
    monkeypatch.setenv('SOLARYN_ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('SOLARYN_ADMIN_PASSWORD_HASH', TEST_HASH)
    path = tmp_path / 'auth.db'
    return TestClient(create_app(path), base_url='https://testserver'), path


def login(client):
    return client.post('/api/v1/auth/login', json={'username':'admin', 'password':TEST_PASSWORD})


@pytest.mark.parametrize('path', ['/site','/conditions','/candidates','/processing','/economics','/results','/evidence','/profile','/docs'])
def test_guests_cannot_open_private_pages(protected, path):
    client, _ = protected
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/login'


@pytest.mark.parametrize('path', ['/api/v1/sites','/api/v1/modules','/api/v1/technology-families','/api/v1/geocode/reverse?lat=0&lon=0','/api/v1/sites/secret','/api/v1/sites/secret/climate-snapshot','/api/v1/analyses/secret','/api/v1/analyses/secret/export','/api/v1/analyses/secret/report','/api/v1/analyses/secret/package','/api/v1/analyses/secret/visuals','/api/v1/climate-sources/secret/export','/openapi.json'])
def test_guests_cannot_read_private_api(protected, path):
    client, _ = protected
    r = client.get(path)
    assert r.status_code == 401
    assert r.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('path', ['/api/v1/sites','/api/v1/analyses','/api/v1/analyses/secret/run','/api/v1/sites/secret/climate-snapshot'])
def test_guests_cannot_run_or_create(protected, path):
    assert protected[0].post(path, json={}).status_code == 401


def test_home_login_assets_and_profile(protected):
    c, _ = protected
    for path in ['/', '/login', '/assets/app.js', '/brand/solaryn-logo.png', '/api/v1/health']:
        assert c.get(path).status_code == 200
    assert c.get('/api/v1/auth/session').json() == {'authenticated':False, 'profile':None}
    r = login(c)
    assert r.status_code == 200
    cookie = r.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie
    assert c.get('/profile').status_code == 200
    assert c.get('/api/v1/auth/session').json()['profile']['role'] == 'admin'
    assert c.post('/api/v1/sites', json={'latitude':0,'longitude':0}).status_code == 201
    assert len(c.get('/api/v1/sites').json()) == 1


def test_wrong_credentials_forgery_and_throttling(protected):
    c, _ = protected
    c.cookies.set(COOKIE, 'forged-admin-token')
    assert c.get('/api/v1/sites').status_code == 401
    for _ in range(10):
        assert c.post('/api/v1/auth/login',json={'username':'visitor','password':'wrong'}).status_code == 401
    assert login(c).status_code == 429


def test_logout_revokes_copied_session(protected):
    c, _ = protected
    login(c)
    old = c.cookies.get(COOKIE)
    assert c.post('/api/v1/auth/logout').status_code == 200
    c.cookies.set(COOKIE, old)
    assert c.get('/api/v1/sites').status_code == 401


def test_expiry_and_password_rotation(protected, monkeypatch):
    c, path = protected
    login(c)
    token = c.cookies.get(COOKIE)
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT token_hash FROM admin_sessions').fetchone()
        assert row[0] == hashlib.sha256(token.encode()).hexdigest()
        db.execute('UPDATE admin_sessions SET expires=0')
    assert c.get('/api/v1/sites').status_code == 401
    login(c)
    token = c.cookies.get(COOKIE)
    monkeypatch.setenv('SOLARYN_ADMIN_PASSWORD_HASH', password_hash('a-new-test-password'))
    restarted = TestClient(create_app(path), base_url='https://testserver')
    restarted.cookies.set(COOKIE, token)
    assert restarted.get('/api/v1/sites').status_code == 401


def test_fail_closed_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv('SOLARYN_ADMIN_PASSWORD_HASH', raising=False)
    c = TestClient(create_app(tmp_path/'closed.db'))
    assert c.get('/').status_code == 200
    assert c.get('/api/v1/sites').status_code == 401
    assert login(c).status_code == 503


def test_cross_site_login_and_logout_rejected(protected):
    c, _ = protected
    assert c.post('/api/v1/auth/login',json={'username':'admin','password':TEST_PASSWORD},headers={'Origin':'https://evil.example'}).status_code == 403
    login(c)
    assert c.post('/api/v1/auth/logout',headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
    assert c.get('/api/v1/auth/session').json()['authenticated']
