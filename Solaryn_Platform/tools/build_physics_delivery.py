"""Bundle the platform with its actual physics code and validation dependencies."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[2]
PLATFORM=ROOT/'Solaryn_Platform'
PILOT=ROOT/'Solaryn_Pilot'
ARCHIVE=ROOT/'Solaryn_Decision_Chain_2026-09-14.zip'
files=[]
for p in PLATFORM.iterdir():
    if p.is_file() and p.suffix in {'.py','.md','.txt','.ini'}: files.append(p)
for directory in ['web','tests','tools']:
    files.extend(p for p in (PLATFORM/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.html','.css','.js'})
files.extend((PILOT/'src').glob('*.py'))
for directory in ['data','validation']:
    files.extend(p for p in (PILOT/directory).rglob('*') if p.is_file() and p.suffix.lower() in {'.csv','.json','.md','.html','.txt'})
for name in ['PILOT_MODEL_CARD.md','PROCUREMENT_MODEL.md']:
    files.append(PILOT/'docs'/name)
for name in ['test_pilot_contract.py','test_outdoor_validation.py','test_physics_sanity.py']:
    files.append(PILOT/'tests'/name)
start='''# Solaryn — physics-driven platform delivery

This archive includes the web platform, the preserved hourly physics code, the module catalog, recorded resource inputs, measured SUPSI validation data, and tests. No accounts, passwords, customer uploads, databases or installed environments are included.

## Start (Windows, Python 3.12)

Extract the archive. Open PowerShell in the extracted Solaryn_Physics_Platform folder:

```powershell
python -m venv .venv
.venv\\Scripts\\python.exe -m pip install -r Solaryn_Platform\\requirements-lock.txt
.venv\\Scripts\\python.exe Solaryn_Platform\\run.py
```

On macOS/Linux use python3.12 and .venv/bin/python. Initial dependency installation requires internet access. The recorded Riyadh analysis then works offline.

Open http://127.0.0.1:8765 and create an organization. Keep the Solaryn_Platform and Solaryn_Pilot folders beside each other. Stop any older server on that port before starting this copy.

## Run the physical workflow

1. Create a project. For the recorded weather example use latitude 24.7136 and longitude 46.6753, or create the synthetic example project.
2. Open Physics & validation. Choose Recorded Riyadh 2020 and leave the default three modules selected.
3. Optional: enter a price for each selected module to enable exploratory economics. Prices are user assumptions or supplier quotes, not built-in facts.
4. Run physics & measured validation. View the original physical decision gates, DC/AC losses, measured residuals and derived economic outputs.
5. Download the complete physical analysis ZIP, including hourly results, weather, measured-validation data and hashes.

Live NASA POWER uses the project coordinates and requires network access. It was not exercised in this release's tests. Reference electrical validation does not validate all commercial technologies, the whole weather/thermal chain, the AC approximation or long-term economics.

## Tests

```powershell
.venv\\Scripts\\python.exe -m pytest Solaryn_Platform\\tests -q
```

See Solaryn_Platform/PHYSICS_INTEGRATION.md for validation scope and results. The original Streamlit UI is not included; the original Python physics core and its required data are included and invoked by the new web platform. The small earlier procurement-only ZIP is superseded by this delivery.
'''
prefix='Solaryn_Physics_Platform/'
manifest={}
with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        raw=path.read_bytes()
        if path.suffix=='.py': compile(raw,str(path),'exec')
        name=path.relative_to(ROOT).as_posix()
        archive.writestr(prefix+name,raw)
        manifest[name]=hashlib.sha256(raw).hexdigest()
    archive.writestr(prefix+'START_HERE.md',start)
    manifest['START_HERE.md']=hashlib.sha256(start.encode()).hexdigest()
    archive.writestr(prefix+'MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(ARCHIVE) as archive:
    assert archive.testzip() is None
    assert not any(x in name.split('/') for name in archive.namelist() for x in ['workspace','.packages','.venv','__pycache__'])
checksum=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
ARCHIVE.with_suffix('.zip.sha256').write_text(checksum+'  '+ARCHIVE.name+'\n')
print(json.dumps({'archive':str(ARCHIVE),'files':len(manifest)+1,'bytes':ARCHIVE.stat().st_size,'sha256':checksum}))

