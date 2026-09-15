# SOLARYN corrected code — Windows quick start

Extract the complete ZIP to a folder, then open PowerShell in that folder. Use Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Solaryn_Platform/requirements-lock.txt
.\.venv\Scripts\python.exe Solaryn_Platform/run_foundation.py
```

Open http://127.0.0.1:8766 in your browser. The server runs until you press Ctrl+C. Internet access is needed to fetch PVGIS/NASA POWER resource data and map tiles. EPC HTML reports open offline.

The current application is `Solaryn_Platform/run_foundation.py`. Other preserved entry points belong to earlier interfaces. The frontend is served directly; Node is needed only for development checks:

```powershell
npm.cmd --prefix Solaryn_Platform/web/foundation ci --ignore-scripts
npm.cmd --prefix Solaryn_Platform/web/foundation run build
.\.venv\Scripts\python.exe -m pytest Solaryn_Platform/tests -q
```

The ZIP contains source, catalog, assets, tests and documentation. Installed Python/npm dependencies, SQLite databases, account data, saved climate snapshots and historical output folders are excluded. Your existing working-folder data remain untouched. A fresh extraction starts an empty local workspace. Do not overwrite an existing workspace when extracting.

Read `docs/REPORT_CATALOG_DELIVERY.md` for changes, validation and limitations. Every packaged file is covered by `CODE_MANIFEST_SHA256.json`; that manifest excludes its own hash. The adjacent `.zip.sha256` file covers the complete archive.
