import base64
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from server import create_app, model

PASSWORD = "test-password-long-enough"


@pytest.fixture
def platform(tmp_path):
    path = tmp_path / "platform.sqlite3"
    return create_app(path), path


def register(app, email="owner@example.test"):
    c = TestClient(app)
    r = c.post("/api/v1/auth/register", json={"email":email,"password":PASSWORD,"name":"Test Owner","organization":"Test Organization"})
    assert r.status_code == 201, r.text
    c.headers["x-csrf-token"] = r.json()["csrf"]
    return c


def create_project(c):
    r = c.post("/api/v1/projects", json={"parameters":{"name":"Test project", "capacity_mwp":1}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def detail(c,pid): return c.get(f"/api/v1/projects/{pid}").json()


def add_offer(c,pid,name="A",**kwargs):
    params={"name":name,"model":"Exact SKU","bom":"REV-1","quote_eur_w":.12,"net_ac_kwh_kwp":2000,"yield_source":"Study 1",**kwargs}
    r=c.post(f"/api/v1/projects/{pid}/offers",json={"parameters":params,"revision":detail(c,pid)["revision"]})
    assert r.status_code == 201,r.text
    return r.json()["id"]


def upload(c,pid):
    r=c.post(f"/api/v1/projects/{pid}/documents",json={"filename":"source.txt","content_base64":base64.b64encode(b"Independent source evidence").decode()})
    assert r.status_code==201,r.text
    return r.json()["id"]


def run(c,pid):
    r=c.post(f"/api/v1/projects/{pid}/runs",json={"revision":detail(c,pid)["revision"]})
    assert r.status_code==201,r.text
    return r.json()


def test_auth_csrf_logout_and_login(platform):
    app,_=platform
    c=register(app)
    assert c.get('/api/v1/auth/me').json()['user']['role']=='owner'
    csrf=c.headers.pop('x-csrf-token')
    assert c.post('/api/v1/projects',json={'parameters':{'name':'Invalid'}}).status_code==403
    c.headers['x-csrf-token']=csrf
    assert c.post('/api/v1/auth/logout').status_code==200
    assert c.get('/api/v1/projects').status_code==401
    r=c.post('/api/v1/auth/login',json={'email':'owner@example.test','password':PASSWORD})
    assert r.status_code==200
    assert 'HttpOnly' in r.headers['set-cookie']
    assert 'SameSite=strict' in r.headers['set-cookie']
    assert TestClient(app).post('/api/v1/auth/register',headers={'origin':'https://evil.test'},json={}).status_code==403


def test_organization_isolation_every_resource(platform):
    app,_=platform
    a,b=register(app),register(app,'other@example.test')
    pid=create_project(a)
    aid=add_offer(a,pid)
    add_offer(a,pid,'B')
    did=upload(a,pid)
    cid=a.post(f'/api/v1/projects/{pid}/claims',json={'candidate_id':aid,'document_id':did,'field':'bom','section':'p1','excerpt':'REV-1','classification':'Fact'}).json()['id']
    rid=run(a,pid)['id']
    assert b.get('/api/v1/projects').json()==[]
    for suffix in ['',f'/documents/{did}',f'/runs/{rid}']:
        assert b.get(f'/api/v1/projects/{pid}'+suffix).status_code==404
    assert b.put(f'/api/v1/projects/{pid}',json={'parameters':{'name':'Attempt'},'revision':1}).status_code==404
    assert b.post(f'/api/v1/projects/{pid}/claims/{cid}/review',json={'status':'Reviewed','comment':'Attempt'}).status_code==404
    assert b.post(f'/api/v1/projects/{pid}/runs/{rid}/approve',json={'status':'Reviewed','comment':'Attempt'}).status_code==404
    bp=create_project(b)
    bid=add_offer(b,bp)
    assert b.post(f'/api/v1/projects/{bp}/claims',json={'candidate_id':bid,'document_id':did,'field':'bom','section':'p1','excerpt':'Stolen','classification':'Fact'}).status_code==404
    assert all(e['entity']!=pid for e in b.get('/api/v1/audit').json())


@pytest.mark.parametrize('role',['editor','reviewer','viewer'])
def test_roles_cannot_escalate(platform,role):
    app,_=platform
    owner=register(app)
    pid=create_project(owner)
    assert owner.post('/api/v1/members',json={'name':'Team Member','email':f'{role}@example.test','password':PASSWORD,'role':role}).status_code==201
    c=TestClient(app)
    r=c.post('/api/v1/auth/login',json={'email':f'{role}@example.test','password':PASSWORD})
    c.headers['x-csrf-token']=r.json()['csrf']
    assert c.get(f'/api/v1/projects/{pid}').status_code==200
    assert c.post('/api/v1/members',json={'name':'Attempt','email':'attempt@example.test','password':PASSWORD,'role':'editor'}).status_code==403
    expected=201 if role=='editor' else 403
    assert c.post('/api/v1/projects',json={'parameters':{'name':'Role study'}}).status_code==expected
    if role!='reviewer':
        assert c.post(f'/api/v1/projects/{pid}/claims/unknown/review',json={'status':'Reviewed','comment':'Forbidden'}).status_code==403


def test_exact_model_parity_and_persistence(platform):
    app,path=platform
    c=register(app)
    pid=create_project(c)
    add_offer(c,pid)
    add_offer(c,pid,'B',net_ac_kwh_kwp=2050)
    output=run(c,pid)
    d=detail(c,pid)
    expected=model.compare(model.Project(**d['parameters']),[model.Candidate(**o['parameters']) for o in d['offers']])
    assert output['result']['results']==expected['results']
    assert c.post(f"/api/v1/projects/{pid}/runs/{output['id']}/approve",json={'status':'Reviewed','comment':'Cannot approve incomplete'}).status_code==409
    restarted=TestClient(create_app(path))
    restarted.cookies.update(c.cookies)
    assert restarted.get(f"/api/v1/projects/{pid}/runs/{output['id']}").json()['result']==output['result']


def test_evidence_review_approval_and_stale_run(platform):
    app,_=platform
    c=register(app)
    pid=create_project(c)
    ids=[add_offer(c,pid),add_offer(c,pid,'B')]
    did=upload(c,pid)
    assert c.get(f'/api/v1/projects/{pid}/documents/{did}').content==b'Independent source evidence'
    for oid in ids:
        for field in ['net_ac_kwh_kwp','quote_eur_w','degradation','bom']:
            r=c.post(f'/api/v1/projects/{pid}/claims',json={'candidate_id':oid,'document_id':did,'field':field,'section':'p1','excerpt':'Human-checked evidence','classification':'Assumption'})
            assert r.status_code==201,r.text
            cid=r.json()['id']
            assert c.post(f'/api/v1/projects/{pid}/claims/{cid}/review',json={'status':'Reviewed','comment':'Reviewed source and exact BOM'}).status_code==200
    result=run(c,pid)
    assert not any(r['evidence_gaps'] for r in result['result']['results'])
    rid=result['id']
    assert c.post(f'/api/v1/projects/{pid}/runs/{rid}/approve',json={'status':'Reviewed','comment':'Reviewed assumptions; conditional decision'}).status_code==201
    saved=c.get(f'/api/v1/projects/{pid}/runs/{rid}').json()
    assert saved['approval']['actor']==c.get('/api/v1/auth/me').json()['user']['id']
    assert c.post(f'/api/v1/projects/{pid}/runs/{rid}/approve',json={'status':'Reviewed','comment':'Duplicate'}).status_code==409
    newer=run(c,pid)['id']
    d=detail(c,pid)
    offer=d['offers'][0]
    offer['parameters']['quote_eur_w']=.2
    assert c.put(f"/api/v1/projects/{pid}/offers/{offer['id']}",json={'parameters':offer['parameters'],'revision':d['revision']}).status_code==200
    assert c.post(f'/api/v1/projects/{pid}/runs/{newer}/approve',json={'status':'Reviewed','comment':'Old result'}).status_code==409
    assert any('quote_eur_w' in r['evidence_gaps'] for r in run(c,pid)['result']['results'])
    assert c.get(f'/api/v1/projects/{pid}/runs/{rid}').json()['result']==result['result']


def test_conflicts_validation_and_upload_limits(platform):
    app,_=platform
    c=register(app)
    pid=create_project(c)
    add_offer(c,pid)
    assert c.post(f'/api/v1/projects/{pid}/runs',json={'revision':1}).status_code==409
    assert c.post('/api/v1/projects',json={'parameters':{'name':'Invalid','capacity_mwp':-1}}).status_code==422
    assert c.post('/api/v1/projects',json={'parameters':{'name':None}}).status_code==422
    assert c.post(f'/api/v1/projects/{pid}/documents',json={'filename':'../secret.txt','content_base64':'YQ=='}).status_code==422
    assert c.post(f'/api/v1/projects/{pid}/documents',json={'filename':'fake.pdf','content_base64':'YQ=='}).status_code==422
    assert c.post('/api/v1/auth/login',content=b'x'*8_000_001,headers={'Content-Type':'application/json'}).status_code==413


def test_login_rate_limit_persists(platform):
    app,_=platform
    c=register(app)
    for _ in range(8):
        assert c.post('/api/v1/auth/login',json={'email':'owner@example.test','password':'wrong-password-long'}).status_code==401
    assert c.post('/api/v1/auth/login',json={'email':'owner@example.test','password':PASSWORD}).status_code==429


def test_run_integrity_and_static_security_headers(platform):
    app,path=platform
    c=register(app)
    pid=create_project(c)
    add_offer(c,pid)
    add_offer(c,pid,'B')
    rid=run(c,pid)['id']
    with sqlite3.connect(path) as db: db.execute('UPDATE runs SET payload=? WHERE id=?',('{}',rid))
    assert c.get(f'/api/v1/projects/{pid}/runs/{rid}').status_code==409
    r=c.get('/')
    assert r.status_code==200
    assert "default-src 'self'" in r.headers['content-security-policy']
    assert c.get('/static/app.js').status_code==200
    assert c.get('/api/v1/projects').headers['cache-control']=='no-store'
