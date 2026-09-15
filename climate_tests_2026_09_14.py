from pathlib import Path
import sys, json, io, zipfile, hashlib, secrets, time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'Solaryn_Platform/.packages'))
sys.path.insert(0, str(ROOT/'Solaryn_Platform'))
from fastapi.testclient import TestClient
from server import create_app

OUT = ROOT/'SOLARYN_FOUR_CLIMATE_TESTS_2026-09-14'
OUT.mkdir(exist_ok=True)
SITES = [('Leuven',50.879202,4.7011675,'Temperate maritime'),
         ('Riyadh',24.7136,46.6753,'Hot desert'),
         ('Iqaluit',63.7492738,-68.5213763,'Arctic tundra'),
         ('Singapore',1.3521,103.8198,'Tropical equatorial')]
IDS = ['MOD_TOPCON_JINKO_JKM575N_72HL4_V','MOD_PERC_LONGI_LR5_72HPH_550M','MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530']

def run(site):
    name,lat,lon,climate=site
    folder=OUT/name
    folder.mkdir(exist_ok=True)
    c=TestClient(create_app(folder/'runtime/platform.sqlite3'))
    r=c.post('/api/v1/auth/register',json={'email':name.lower()+'@example.test','password':secrets.token_urlsafe(24),'name':'Climate Test','organization':name+' climate test'})
    assert r.status_code==201,r.text
    c.headers['x-csrf-token']=r.json()['csrf']
    r=c.post('/api/v1/projects',json={'parameters':{'name':name+' climate test 2020','capacity_mwp':1},'latitude':lat,'longitude':lon})
    assert r.status_code==201,r.text
    project=r.json(); pid=project['id']
    body={'revision':1,'module_ids':IDS,'weather_source':'live_nasa','weather_year':2020,'quotes_eur_w':{mid:.12 for mid in IDS}}
    (folder/'test_inputs.json').write_text(json.dumps({'site':site,'project':project,'physics_request':body},indent=2))
    print(name+': running full physics API with NASA POWER 2020',flush=True)
    start=time.monotonic()
    r=c.post(f'/api/v1/projects/{pid}/physics',json=body)
    result={'site':name,'climate':climate,'latitude':lat,'longitude':lon,'http_status':r.status_code,'seconds':round(time.monotonic()-start,1)}
    (folder/'api_response.json').write_text(json.dumps(r.json(),indent=2),encoding='utf-8')
    if r.status_code==201:
        saved=r.json(); data=saved['result']; rid=saved['id']
        response=c.get(f'/api/v1/projects/{pid}/physics/{rid}/download')
        assert response.status_code==200,response.text
        (folder/(name+'_Analysis.zip')).write_bytes(response.content)
        z=zipfile.ZipFile(io.BytesIO(response.content)); assert z.testzip() is None
        manifest=json.loads(z.read('Manifest-platform.json'))
        assert all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in manifest.items())
        for entry in z.namelist():
            if entry.endswith('Decision.html'):
                (folder/(name+'_Decision.html')).write_bytes(z.read(entry))
        for filename in ['Hourly-DC-AC.csv','Measured-validation-monthly.csv','Result.json']:
            (folder/filename).write_bytes(z.read(filename))
        for row in data['ac_energy']:
            assert 0 < row['net_ac_kwh_kwp'] < row['dc_kwh_kwp']
            assert abs(sum(row['monthly_ac'].values())-row['net_ac_kwh_kwp'])<1e-6
            assert abs(sum(row[k] for k in ['conversion_loss_kwh_kwp','clipping_loss_kwh_kwp','availability_curtailment_loss_kwh_kwp','net_ac_kwh_kwp'])-row['dc_kwh_kwp'])<1e-6
        assert data['measured_validation']['status']=='REFERENCE_BENCHMARK_REPRODUCED'
        assert c.get(f'/api/v1/projects/{pid}/physics/{rid}').status_code==200
        result.update(status='PASS',energy=data['ac_energy'],validation=data['measured_validation'],decision=data['physics']['decision'],checks=['API run and persisted read','Measured benchmark reproduced','DC/AC energy conservation','Monthly/annual reconciliation','ZIP CRC and every manifest hash'])
    else:
        result.update(status='FAIL',error=r.json())
    (folder/'test_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(name+': '+result['status']+' in '+str(result['seconds'])+' s',flush=True)
    return result

if __name__=='__main__':
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(run,s):s for s in SITES}
        for future in as_completed(futures):
            try: results.append(future.result())
            except Exception as e:
                results.append({'site':futures[future][0],'status':'ERROR','error':repr(e)})
                print(repr(e),flush=True)
    (OUT/'test_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('FINISHED '+str(OUT),flush=True)
