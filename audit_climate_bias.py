from pathlib import Path
import sys, json, zipfile, io, itertools
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'Solaryn_Pilot'))
from src.module_offer_io import load_module_offer_csv
from src.module_iv_engine import simulate_module_hourly
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.evidence_policy import project_segment_compatible
from src.pilot_decision import decide
from src.run_store import clean

PILOT=ROOT/'Solaryn_Pilot'
OUT=ROOT/'SOLARYN_FOUR_CLIMATE_TESTS_2026-09-14'/'BIAS_AUDIT'
OUT.mkdir(exist_ok=True)
catalog=load_module_offer_csv(PILOT/'data/raw/module_candidate_master.csv')
catalog=catalog[catalog.apply(lambda r:project_segment_compatible(r,'utility'),axis=1)]
all_results=[]
for name in ['Leuven','Riyadh','Iqaluit','Singapore']:
    source=OUT.parent/name
    original=json.loads((source/'Result.json').read_text())
    rows=pd.DataFrame([c['metrics'] for c in original['physics']['candidates']])
    baseline=decide(rows)
    for permutation in itertools.permutations(range(len(rows))):
        current=decide(rows.iloc[list(permutation)])
        for key in ['status','provisional_leader_module_id','robust_winner_module_id','annual_lead_over_second_pct']:
            assert current[key]==baseline[key],(name,key)
    csi=rows[rows.decision_eligible.astype(bool)]
    csi_decision=decide(csi)
    with zipfile.ZipFile(source/(name+'_Analysis.zip')) as z:
        nasa_entry=next(p for p in z.namelist() if p.endswith('inputs/NASA-hourly.csv'))
        nasa=pd.read_csv(io.BytesIO(z.read(nasa_entry)),parse_dates=['time_utc'])
    project=original['project']
    cfg=project['configuration']
    weather=nasa_hourly_to_pvlib_weather(nasa,project['latitude'],project['longitude'],cfg['tilt_deg'],cfg['azimuth_deg'],albedo=cfg['albedo'])
    outputs=[]
    for _,row in catalog.iterrows():
        try:
            summary,_=simulate_module_hourly(weather,row,cfg['soiling_pct'],PILOT,bifacial_config={'enabled':False})
            outputs.append(summary)
        except Exception as exc:
            outputs.append({'module_id':row.module_id,'error':str(exc)})
    brand_checks=[]
    for _,row in catalog[catalog.module_id.isin(csi.module_id)].iterrows():
        clone=row.copy()
        clone['module_id']='ANONYMOUS_'+str(len(brand_checks))
        clone['manufacturer']='Anonymous maker'
        clone['model']='Anonymous model'
        summary,_=simulate_module_hourly(weather,clone,cfg['soiling_pct'],PILOT,bifacial_config={'enabled':False})
        actual=next(s['annual_yield_kwh_kwp'] for s in outputs if s['module_id']==row.module_id)
        delta=summary['annual_yield_kwh_kwp']-actual
        assert abs(delta)<1e-9,(name,delta)
        brand_checks.append({'original_id':row.module_id,'anonymous_minus_original_kwh_kwp':delta})
    # Identical physical/evidence metrics under distinct IDs must not pick a winner.
    twins=pd.concat([csi.iloc[[0]],csi.iloc[[0]]],ignore_index=True)
    twins.loc[0,'module_id']='A';twins.loc[1,'module_id']='Z'
    tie=decide(twins)
    assert tie['provisional_leader_module_id'] is None
    ordered=sorted([s for s in outputs if 'error' not in s],key=lambda s:s['annual_yield_kwh_kwp'],reverse=True)
    result=clean({'site':name,'row_order_permutations_passed':6,'brand_name_checks':brand_checks,'identical_candidate_tie':tie,'original_csi_pair_decision':csi_decision,'expanded_same_geometry_results':ordered,'failed_expanded_candidates':[s for s in outputs if 'error' in s]})
    (OUT/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    all_results.append(result)
    print(name+': '+str(len(ordered))+' candidates; highest modeled DC '+ordered[0]['model']+'; original silicon pair '+csi_decision['status'],flush=True)
(OUT/'audit_results.json').write_text(json.dumps(all_results,indent=2),encoding='utf-8')
print('AUDIT COMPLETE',flush=True)
