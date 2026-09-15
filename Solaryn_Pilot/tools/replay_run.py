"""Replay a delivered run folder offline and compare numerical outputs/status."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import argparse,json
import numpy as np
import pandas as pd
from src.run_store import sha
from src.pilot_service import analyze

def main():
    parser=argparse.ArgumentParser();parser.add_argument('run_folder',type=Path);args=parser.parse_args()
    folder=args.run_folder.resolve()
    manifest=json.loads((folder/'Manifest.json').read_text(encoding='utf-8'))
    for name,checksum in manifest.items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder) or sha(file.read_bytes())!=checksum: raise ValueError('Artifact integrity failure: '+name)
    original=json.loads((folder/'Result.json').read_text(encoding='utf-8'))
    project=json.loads((folder/'inputs/Project.json').read_text(encoding='utf-8'))
    modules=pd.read_csv(folder/'inputs/Modules.csv')
    nasa=pd.read_csv(folder/'inputs/NASA-hourly.csv',parse_dates=['time_utc'])
    nasa.attrs.update(json.loads((folder/'inputs/NASA-metadata.json').read_text(encoding='utf-8')))
    pv=None
    if (folder/'inputs/PVGIS-hourly.csv').exists():
        pv=pd.read_csv(folder/'inputs/PVGIS-hourly.csv',parse_dates=['date'])
        pv.attrs.update(json.loads((folder/'inputs/PVGIS-metadata.json').read_text(encoding='utf-8')))
    result=analyze(ROOT,project,modules,nasa,pv,store_root=ROOT/'workspace/replays')
    expected={c['module_id']:c for c in original['candidates']}
    for candidate in result['candidates']:
        old=expected[candidate['module_id']]
        assert old['simulation_status']==candidate['simulation_status']
        for key in ['annual_yield_kwh_kwp','lifetime_energy_common_degradation_scenario_kwh_kwp']:
            a,b=old['metrics'].get(key),candidate['metrics'].get(key)
            if a is not None: assert b is not None and np.isclose(a,b,rtol=1e-9),key
    assert result['decision']['status']==original['decision']['status']
    print('PASS: offline replay reproduces annual/lifetime energy and decision status.')
    print('Original:',original['run_id']);print('Replay:',result['run_id'])

if __name__=='__main__': main()
