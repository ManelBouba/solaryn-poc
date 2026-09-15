"""Run the corrected platform with the preserved local workspace database."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'Solaryn_Platform/.packages'))
sys.path.insert(0, str(ROOT/'Solaryn_Platform'))
os.environ['SOLARYN_DB'] = str(ROOT/'Solaryn_Platform/workspace/migrated-live-20260914/platform.sqlite3')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('server:create_app', factory=True, host='127.0.0.1', port=8765)
