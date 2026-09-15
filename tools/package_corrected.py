"""Package active source trees, without saved user data or installed dependencies."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'SOLARYN_CODE_CORRECTED_2026-09-15.zip'
TREES=('Solaryn_Platform','Solaryn_Pilot','src','tests','data','docs','tools','app','frontend','validation','external_validation')
SKIP={'workspace','node_modules','.packages','.venv','__pycache__','.pytest_cache','.git','outputs','examples','artifacts','review_work'}
SUFFIX_SKIP={'.pyc','.zip','.sqlite','.sqlite3','.db','.log','.sha256'}
files={}

def include(path):
    relative=path.relative_to(ROOT).as_posix()
    if path.suffix.lower() in SUFFIX_SKIP or path.name.startswith('.env') or path.name in {'.coverage','FILE_MANIFEST_SHA256.txt','COMPLETE_CODE_DIFF.patch'}:return
    files[relative]=path

for tree in TREES:
    for current,dirs,names in os.walk(ROOT/tree):
        dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith('.test') and not d.startswith('test-output')]
        for name in names:include(Path(current)/name)
for path in ROOT.iterdir():
    if path.is_file() and (path.suffix.lower() in {'.py','.md','.txt','.csv','.ini'} or path.name=='.gitignore'):include(path)

manifest={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sorted(files.items())}
with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,path in sorted(files.items()):z.write(path,name)
    z.writestr('CODE_MANIFEST_SHA256.json',json.dumps({'algorithm':'SHA-256','files':manifest,'note':'Manifest excludes itself. Source-only package; no saved workspace or installed dependencies.'},indent=2))
with zipfile.ZipFile(OUTPUT) as z:
    assert z.testzip() is None
    for name,checksum in manifest.items():
        assert hashlib.sha256(z.read(name)).hexdigest()==checksum,name
    for required in ('START_CORRECTED_CODE.md','Solaryn_Platform/report_service.py','Solaryn_Platform/performance_v2.py','data/catalog/commercial_modules.csv','frontend/public/brand/solaryn-logo.png'):
        assert required in z.namelist(),required
checksum=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
OUTPUT.with_suffix('.zip.sha256').write_text(f'{checksum}  {OUTPUT.name}\n',encoding='utf-8')
print(json.dumps({'path':str(OUTPUT),'files':len(files)+1,'bytes':OUTPUT.stat().st_size,'sha256':checksum,'verification':'All archive file checksums and ZIP integrity passed'},indent=2))
