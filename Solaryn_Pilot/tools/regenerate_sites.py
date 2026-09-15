"""Rebuild the three user-reported cases from real, cached provider responses."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import json
import pandas as pd
from src.data_fetchers import fetch_nasa_power_hourly_dataframe, fetch_pvgis_hourly_dataframe
from src.module_offer_io import load_module_offer_csv
from src.evidence_policy import project_segment_compatible
from src.pilot_service import analyze
from src.pilot_report import package_run
from src.run_store import RunStore, json_bytes

SITES = [('Iqaluit',63.7492738,-68.5213763), ('Timokten',27.7485105,1.1845062), ('Leuven',50.879202,4.7011675)]

def main():
    cache=ROOT/'data/reference/site_replays';cache.mkdir(parents=True,exist_ok=True)
    examples=ROOT/'examples';examples.mkdir(exist_ok=True)
    modules=load_module_offer_csv(ROOT/'data/raw/module_candidate_master.csv')
    modules=modules[modules.apply(lambda r: project_segment_compatible(r,'utility'),axis=1)]
    for name,lat,lon in SITES:
        print(name+': preparing real provider snapshots',flush=True)
        path=cache/f'{name}_NASA.csv';meta=cache/f'{name}_NASA.json'
        if path.exists():
            nasa=pd.read_csv(path,parse_dates=['time_utc']);nasa.attrs.update(json.loads(meta.read_text(encoding='utf-8')))
        else:
            nasa=fetch_nasa_power_hourly_dataframe(lat,lon,'2018-01-01','2020-12-31')
            path.write_text(nasa.to_csv(index=False),encoding='utf-8');meta.write_bytes(json_bytes(nasa.attrs))
        pp=cache/f'{name}_PVGIS.csv';pm=cache/f'{name}_PVGIS.json'
        pv=None;warning=None
        try:
            if pp.exists():
                pv=pd.read_csv(pp,parse_dates=['date']);pv.attrs.update(json.loads(pm.read_text(encoding='utf-8')))
            else:
                pv=fetch_pvgis_hourly_dataframe(lat,lon,2018,2020,25,0)
                pp.write_text(pv.to_csv(index=False),encoding='utf-8');pm.write_bytes(json_bytes(pv.attrs))
        except Exception as exc:
            warning=str(exc);print(name+': independent provider unavailable: '+warning,flush=True)
        project=dict(project_name=name,latitude=lat,longitude=lon,tilt_deg=25,azimuth_deg=180,
            soiling_loss_pct=2,common_degradation_pct_year=.5,system_size_mw=100,target_lifetime_years=25,currency='USD',
            row_geometry_enabled=True,albedo=.2,gcr=.4,row_height_m=1.5,row_pitch_m=5.,
            geometry_confidence='screening_assumptions',provider_warning=warning)
        r=analyze(ROOT,project,modules,nasa,pv)
        store=RunStore(ROOT/'workspace/runs')
        filename,data=package_run(store,r['run_id']);(examples/filename).write_bytes(data)
        (examples/f'Solaryn_{name}_Decision.html').write_bytes((store.root/r['run_id']/'Decision.html').read_bytes())
        print(name+': '+r['decision']['headline'],flush=True)
        print([(c['model'],c['metrics'].get('annual_yield_kwh_kwp'),c['simulation_status']) for c in r['candidates']],flush=True)

if __name__=='__main__': main()
