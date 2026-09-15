# SOLARYN — map-first platform foundation

The new branded web foundation starts with:

```powershell
.\.venv\Scripts\python.exe Solaryn_Platform/run_foundation.py
```

Open **http://127.0.0.1:8766/**. It includes world-map site selection, saved coordinates, PVGIS and NASA POWER hourly climate snapshots, the existing module catalog, and seven navigable screens. PV performance and recommendation services are not yet connected. See [climate integration details](docs/CLIMATE_INTEGRATION.md).

See [the delivery and verification guide](docs/FOUNDATION.md), [stage plan](PLAN.md), and [v4.1 product requirements](docs/PRD.md).

## Preserved V9.2.1 — POC Validation Mode

This package is deliberately optimized for **startup/technical PoC validation**, not for a bankability opinion.

## What changed from V9.2

- EPC CSV upload path hardened: missing optional quote/evidence columns no longer crash the app.
- Header-only template uploads now explain that module rows are required.
- Added a populated three-module example CSV with blank supplier prices.
- Added candidate readiness diagnostics before simulation.

## What changed from V9.1.1

- The PoC now **always returns a provisional module leader** when at least two candidates simulate successfully.
- A candidate with incomplete decision-grade evidence (for example a non-c-Si module without a module-specific IEC 61853 matrix) **no longer blocks the entire comparison**. Its result stays clearly marked exploratory.
- The 2% uncertainty/evidence guardrail is now a **validation-confidence flag**, not a hard blocker.
- Procurement switching thresholds can be calculated in **exploratory PoC mode** for simulated candidates while preserving `economic_decision_eligible=False` where evidence is incomplete.
- Spectral proxy out-of-domain hours remain non-blocking and sensitivity-only.
- If one candidate genuinely fails IV simulation, the PoC continues as long as at least two candidates remain usable.
- Streamlit/Folium map calls no longer pass the deprecated `use_container_width` flag.

## What did NOT change

- NASA POWER hourly climate input.
- pvlib solar position / POA / AOI workflow.
- Module IV simulation path.
- Thermal model logic.
- Common soiling assumption.
- Lifetime common-degradation scenario.
- Module price switching-point equations.
- Evidence labels and scientific limitations.

## Interpretation

The main result is now **POC provisional leader**. A confidence label (`Strong`, `Moderate`, or `Exploratory`) tells you how much further validation is needed. The strict V9 evidence/bankability-style check is preserved as a secondary diagnostic only.

## Run

```powershell
python -m streamlit run app\streamlit_app.py
```

## Verification

- Python compile check: passed
- Automated tests: **50 passed**

## Site selection

The PoC is **not limited to preset cities**. The map click updates latitude/longitude, and those coordinates are passed directly to the NASA POWER hourly climate workflow (with PVGIS available as the secondary comparison path). Any supported project coordinate can therefore be tested.

Brussels, Algiers, Riyadh, or other cities are validation examples only; they are not hard-coded decision sites.
