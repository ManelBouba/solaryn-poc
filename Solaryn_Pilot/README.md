# Solaryn

Evidence-based PV module comparison for a real project and site.

## Procurement workspace

Open **Procurement Workspace** in the sidebar for the new climate-aware lifecycle comparison: project and offer inputs, manual evidence register, climate checklist, deterministic degradation/event scenarios, net AC lifetime economics, NPV/LCOE/IRR, justified EUR/W premiums, and persistent JSON/Markdown decision snapshots. Examples are synthetic. See [model equations and implementation boundaries](docs/PROCUREMENT_MODEL.md). This remains a local single-user prototype, not a deployed multi-tenant SaaS.

From the parent delivery directory, using its existing environment:

```powershell
.venv\Scripts\python.exe -m streamlit run Solaryn_Pilot\app\streamlit_app.py --server.address 127.0.0.1
```

Offline example and replay, from this `Solaryn_Pilot` directory:

```powershell
..\.venv\Scripts\python.exe tools\procurement.py
..\.venv\Scripts\python.exe tools\procurement.py --input examples\procurement\decision.json
```

## Start

Use Python 3.12 on Windows, macOS or Linux. In this directory:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-lock.txt
.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

On macOS/Linux use `.venv/bin/python`. The server binds to localhost. This is a single-user local pilot, not a hosted service.

Open **Module Recommendation**. The saved Riyadh reference runs without weather API access. For another site choose **Live NASA POWER**, search a city or select coordinates, review geometry, choose exact modules, and run. Blank quotes keep physics available and disable procurement economics. USD and EUR are supported as consistent input currencies; no exchange-rate conversion is performed.

**Downloads** reopens persistent project analyses after application restarts. Changing inputs creates a new run; completed records are never overwritten through the application. Each export includes the deterministic report, exact JSON, original module/project inputs, climate snapshots, hourly results and a SHA-256 manifest. Result hashes are integrity checks, not signatures.

## What changed

The row/rear geometry path now preserves irradiance alignment. Invalid daytime physics and all-zero results stop ranking. Evidence is fail-closed and exact ties do not award the first row a winner. The active service returns **Robust modeled advantage**, **Provisional technical leader**, **Effectively tied**, or **Insufficient evidence**, with the status before the numerical leader.

The expanded ten-module catalog and thirty-technology research library are retained. Technology-library scores do not choose commercial module recommendations. Uncalibrated Monte Carlo probabilities do not appear as procurement confidence in the pilot.

## Reproduce and verify

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
.venv\Scripts\python tools/validate_measured.py
.venv\Scripts\python tools/regenerate_sites.py
.venv\Scripts\python tools/replay_run.py "path/to/extracted/analysis-folder"
```

The three site replays use saved real NASA POWER/PVGIS records for 2018-2020. They fetch from the providers only when the local fixtures are absent. `examples/` contains the corrected Iqaluit, Timokten and Leuven reports and complete analysis packages.

## Documentation

- `docs/PILOT_DELIVERY.md`: requirements implemented, verification, remaining stages.
- `docs/PILOT_MODEL_CARD.md`: equations, units, change rationale, scientific boundaries.
- `docs/IMPLEMENTATION_PLAN.md`: issue-sized implementation trace.
- `docs/PRD.md`: supplied product specification, including future platform stages.
- `docs/DEMO_GUIDE.md`: short recording walkthrough.

Earlier architecture/recommendation documents are preserved in `docs/historical/` as development context. They do not describe the active decision contract. The active path is `app/pilot_ui.py` -> `src/pilot_service.py` -> deterministic model/evidence services -> immutable run -> `src/pilot_report.py`.
