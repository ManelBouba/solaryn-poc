"""Local content-addressed runs. Atomic publication; reads verify every artifact."""
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import uuid
import logging
import numpy as np

def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value): return None
    if value is None or isinstance(value, (str, int, float, bool)): return value
    return str(value)

def json_bytes(value):
    return json.dumps(clean(value), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")

def sha(data): return hashlib.sha256(data).hexdigest()

class RunStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def read(self, run_id):
        if len(run_id) != 64 or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("Invalid run identifier.")
        folder = self.root / run_id
        manifest = json.loads((folder / "Manifest.json").read_text(encoding="utf-8"))
        for name, checksum in manifest.items():
            path = (folder / name).resolve()
            if not path.is_relative_to(folder.resolve()) or sha(path.read_bytes()) != checksum:
                raise ValueError("Stored run integrity check failed.")
        result = json.loads((folder / "Result.json").read_text(encoding="utf-8"))
        if result["run_id"] != run_id: raise ValueError("Run identity mismatch.")
        return result

    def publish(self, result, artifacts):
        run_id = result["run_id"]
        target = self.root / run_id
        if target.exists():
            self.read(run_id)
            return target
        temporary = self.root / (".pending-" + uuid.uuid4().hex)
        temporary.mkdir()
        try:
            files = {**artifacts, "Result.json": json_bytes(result)}
            for name, data in files.items():
                path = (temporary / name).resolve()
                if not path.is_relative_to(temporary.resolve()): raise ValueError("Unsafe artifact path.")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (temporary / "Manifest.json").write_bytes(json_bytes({n: sha(d) for n, d in files.items()}))
            try: os.rename(temporary, target)
            except OSError:
                if not target.exists(): raise
                self.read(run_id)
            logging.getLogger("solaryn.audit").info("analysis_published run_id=%s", run_id)
            return target
        finally:
            if temporary.exists():
                if not temporary.resolve().is_relative_to(self.root.resolve()):
                    raise ValueError("Unsafe temporary directory.")
                shutil.rmtree(temporary)

    def list_runs(self):
        runs = []
        self.unreadable_runs = []
        for p in sorted(self.root.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                try: runs.append(self.read(p.name))
                except PermissionError:
                    self.unreadable_runs.append(p.name)
        return runs
