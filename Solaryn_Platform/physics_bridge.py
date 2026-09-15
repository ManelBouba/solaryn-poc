"""Process boundary and integrity checks for the preserved scientific engine."""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys
import zipfile
import io

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent/'Solaryn_Pilot'


def catalog():
    with (PILOT/'data/raw/module_candidate_master.csv').open(encoding='utf-8-sig',newline='') as f:
        return [{k:r.get(k,'') for k in ['module_id','manufacturer','model','technology_label','pmax_w','source_url']} for r in csv.DictReader(f)]


def run_physics(payload,folder):
    folder.mkdir(parents=True,exist_ok=False)
    request=folder/'Request.json'
    request.write_text(json.dumps(payload,allow_nan=False),encoding='utf-8')
    try:
        proc=subprocess.run([sys.executable,str(ROOT/'physics_worker.py'),str(request),str(folder)],
                            cwd=PILOT,capture_output=True,text=True,timeout=300)
    except subprocess.TimeoutExpired:
        raise ValueError('Physics execution exceeded five minutes; no completed result saved') from None
    (folder/'Execution.log').write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
    if proc.returncode:
        raise ValueError('Physics execution failed. Check the weather source, site, module evidence and server execution log.')
    return read_result(folder)


def read_result(folder):
    manifest=json.loads((folder/'Manifest-platform.json').read_text(encoding='utf-8'))
    if 'Result.json' not in manifest: raise ValueError('Missing result integrity record')
    for name,checksum in manifest.items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest()!=checksum:
            raise ValueError('Physics artifact integrity check failed')
    return json.loads((folder/'Result.json').read_text(encoding='utf-8'))


def package(folder):
    read_result(folder)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        manifest=json.loads((folder/'Manifest-platform.json').read_text(encoding='utf-8'))
        for name in [*manifest,'Manifest-platform.json']:
            z.write(folder/name,name)
    return output.getvalue()
