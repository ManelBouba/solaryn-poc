"""Create the client application archive with a clean Solaryn root and hashes."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED,ZIP_STORED
import hashlib

ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'workspace','.venv','.git','__pycache__','.pytest_cache','outputs'}

def main():
    files=[]
    # Prune runtime storage before walking; do not read unrelated local run records.
    import os
    for current,dirs,names in os.walk(ROOT):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDE)
        for name in sorted(names):
            p=Path(current)/name
            if p.suffix=='.pyc' or name=='FILE_MANIFEST_SHA256.txt':continue
            files.append(p)
    manifest=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in files)
    target=ROOT.parent/'Solaryn_Client_Delivery.zip'
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for p in files:
            z.write(p,'Solaryn/'+p.relative_to(ROOT).as_posix(),compress_type=ZIP_STORED if p.suffix=='.zip' else ZIP_DEFLATED)
        z.writestr('Solaryn/FILE_MANIFEST_SHA256.txt',manifest)
    print(target);print(f'{len(files)+1} files; {target.stat().st_size/1024**2:.1f} MB')

if __name__=='__main__':main()
