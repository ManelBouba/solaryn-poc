from pathlib import Path
import sys, json, zipfile, io
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'Solaryn_Pilot'))
from src.module_offer_io import load_module_offer_csv
from src.module_iv_engine import simulate_module_hourly
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.evidence_policy import project_segment_compatible
from src.run_store import clean
PILOT=ROOT/'Solaryn_Pilot'
OUT=ROOT/'SOLARYN_FOUR_CLIMATE_TESTS_2026-09-14'/'BIAS_AUDIT'
catalog=load_module_offer_csv(PILOT/'data/raw/module_candidate_master.csv')
catalog=catalog[catalog.apply(lambda r:project_segment_compatible(r,'utility'),axis=1)]
results=[]
geometry={'enabled':True,'gcr':.4,'height_m':1.5,'pitch_m':5.,'albedo':.2,'rear_structure_loss_pct':2.}
for name in ['Leuven','Riyadh','Iqaluit','Singapore']:
    source=OUT.parent/name
    original=json.loads((source/'Result.json').read_text())
    with zipfile.ZipFile(source/(name+'_Analysis.zip')) as z:
        entry=next(p for p in z.namelist() if p.endswith('inputs/NASA-hourly.csv'))
        nasa=pd.read_csv(io.BytesIO(z.read(entry)),parse_dates=['time_utc'])
    project=original['project']; cfg=project['configuration']
    weather=nasa_hourly_to_pvlib_weather(nasa,project['latitude'],project['longitude'],cfg['tilt_deg'],cfg['azimuth_deg'],albedo=.2)
    summaries=[]
    for _,row in catalog.iterrows():
        summary,_=simulate_module_hourly(weather,row,cfg['soiling_pct'],PILOT,bifacial_config=geometry)
        summaries.append(summary)
    summaries=sorted(summaries,key=lambda s:s['annual_yield_kwh_kwp'],reverse=True)
    record=clean({'site':name,'scenario':'Common infinite-sheds row geometry, front shading and rear generation enabled; screening assumptions, not validated site design','geometry':geometry,'results':summaries})
    results.append(record)
    (OUT/(name+'_row_geometry.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(name+': '+summaries[0]['model']+' '+str(round(summaries[0]['annual_yield_kwh_kwp'],2)),flush=True)
(OUT/'geometry_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
