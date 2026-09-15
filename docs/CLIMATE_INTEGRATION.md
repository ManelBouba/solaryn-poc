# PVGIS + NASA POWER climate integration

Requirements: CLIM-001, CLIM-002, CLIM-003, CLIM-004, CLIM-005, UI-002. Implemented in the existing FastAPI service and static browser client. The local start command and port 8766 are unchanged.

## Behavior

- Enter Site Conditions: an unsampled site automatically retrieves both sources for 2023, the explicit default reference year. It is not a current-weather feed or a claim that 2023 is the latest year available everywhere.
- Choose a different historical year with the year control. Provider year/coordinate limits are returned as errors; the app never substitutes a different coordinate or year.
- **Load PVGIS + NASA POWER** reuses saved successful provider responses by exact request parameters, endpoint and normalizer version. **Refresh sources** retrieves fresh responses and creates new records. Failed requests are retryable and do not enter the source cache.
- Sources are fetched concurrently with bounded HTTP timeouts. The UI remains navigable and displays retrieval status. This local slice uses synchronous FastAPI worker threads, not a production job queue.
- PVGIS supplies primary GHI/temperature/wind. NASA supplies humidity when PVGIS does not provide it. Each metric names its source.
- If complete PVGIS solar data are unavailable but NASA is complete, NASA becomes the explicitly labeled fallback. Partial provider data remain visible with coverage warnings. Providers are never averaged into one series.
- Monthly chart shows both sources; the expandable table exposes their exact displayed values. Scientific totals and comparison numbers are calculated in Python. JavaScript only formats numbers and scales chart bars.
- Evidence displays source details and raw/hourly export links. New analysis requests freeze the latest site climate snapshot at submission. Historical analysis requests remain unchanged and keep their original climate linkage (or lack of it).

## Provider requests and geometry

PVGIS: `https://re.jrc.ec.europa.eu/api/v5_3/seriescalc`, exact lat/lon, same start/end year, `angle=0`, `aspect=0`, `usehorizon=0`, `components=1`, `pvcalculation=0`. The provider selects the radiation database; its returned database/meteo information is preserved. No module technology is passed to the resource service.

NASA POWER: `https://power.larc.nasa.gov/api/temporal/hourly/point`, same exact coordinates/year, `community=RE`, `time-standard=UTC`. Requested parameters: `ALLSKY_SFC_SW_DWN`, `ALLSKY_SFC_SW_DNI`, `ALLSKY_SFC_SW_DIFF`, `T2M`, `WS10M`, `RH2M`.

The cross-check is annual horizontal GHI without horizon shading, not project-plane POA. Its definition is `100 × (NASA − PVGIS) / PVGIS`. It is unavailable if either annual total is missing or PVGIS is zero. No arbitrary discrepancy threshold, probability or validation pass claim is introduced. Provider grids, solar sampling conventions and resource methods differ.

## Numerical rules and units

Normalizer: `climate-1.0.1`.

- Canonical UTC timestamps preserve the provider's minute offset. A PVGIS `:04` sample is not relabeled as a NASA `:00` sample. Only monthly/annual aggregates are compared here; no instantaneous alignment or interpolation is performed.
- NASA hourly radiation metadata reports Wh/m² in the inspected responses. Dividing energy per hour by the declared one-hour duration yields the numerically equal hourly mean in W/m². Unsupported or missing unit labels are rejected.
- PVGIS beam + diffuse + reflected components at verified zero tilt produce horizontal global irradiance. Horizontal beam is never mislabeled as DNI. PVGIS DNI remains null in this adapter.
- Annual/monthly irradiation = sum of valid W/m² × 1 hour / 1000, in kWh/m². Annual totals require exactly 8760/8784 unique in-year hours and nonmissing GHI for every hour. Incomplete months/years have null totals; no zero filling or interpolation occurs.
- Mean irradiance, temperature, wind and humidity use available valid samples, with per-variable coverage recorded. Mean irradiance includes valid nighttime samples. Invalid negative irradiance/wind, out-of-range humidity, nonfinite values and provider fill values remain missing.
- Air temperature is °C at 2 m; wind is m/s at 10 m; NASA relative humidity is % at 2 m.
- Duplicate hourly slots, inconsistent timestamp offsets, wrong years, non-UTC NASA timestamps, and incompatible PVGIS geometry are rejected.
- PVGIS reconstruction flags are preserved in warnings. Provider reconstruction is distinguished from application interpolation, which is disabled.

## Persistence and API

Additive SQLite tables `climate_sources` and `climate_snapshots` in the existing foundation database. Source rows store original response bytes, SHA-256, exact request, requested/returned locations, provider/API metadata, units, retrieval time, normalizer release, coverage and normalized hourly arrays. Snapshot rows store immutable presentation data and source IDs. Refresh appends; no source or completed analysis is overwritten.

- `GET /api/v1/sites/{id}/climate-snapshot`: latest saved snapshot or explicit NOT_REQUESTED.
- `POST /api/v1/sites/{id}/climate-snapshot`: `{ "year": 2023, "refresh": false }`.
- `GET /api/v1/climate-sources/{id}/export`: normalized data with provenance.
- Same endpoint with `?raw=true`: original provider bytes.
- Source downloads use attachment headers. OpenAPI snapshot updated and regression-tested.

## Baseline, validation and limits

Before edits, foundation tests: **15 passed**. Inspected existing `src/data_fetchers.py`: NASA requests and fields are reusable conventions, but its older summary includes zero filling and derived climate proxies. This integration uses a separate strict normalizer; no old scientific equations or decision code were modified.

Platform regression: **49 passed**, including 16 new climate cases. Cases cover independently hand-calculated totals, leap years, missing data, invalid units/geometry/UTC/timestamps, exact request coordinates, source hashes/exports, cache reuse, refresh immutability, restart persistence, frozen analysis linkage, independent provider errors and zero-denominator cross-checks. These generated fixtures are synthetic software tests, not measured scientific validation. Initial leap-year assertions were corrected to use floating-point tolerance; the aggregation formula was unchanged.

Live verification at the user's selected coordinate returned all 8760 hours for 2023 from both providers. Displayed annual GHI: PVGIS 2069.8 kWh/m²; NASA 1984.5 kWh/m²; difference −4.1%. Browser conditions cards/chart and provider provenance were populated from the saved response. Provider availability elsewhere remains dependent on coverage and network conditions.

Remaining work: project-specific POA/solar geometry, integration with candidate physics, scientific recommendation, data-quality eligibility for physics (resource availability alone is not physics readiness), explicit historical snapshot selection, and durable production retrieval jobs. No forecasts, panel rankings, degradation effects or economics are fabricated.

## Sources

- [JRC PVGIS API reference](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en): versioned endpoint, hourly inputs and horizontal geometry.
- [NASA POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/): UTC selection, hourly sampling, parameters and provider limits. Exact units are checked against each returned payload.

## Changed files

New: `Solaryn_Platform/climate_service.py`, `Solaryn_Platform/tests/test_climate_service.py`, this guide.

Updated: `Solaryn_Platform/foundation.py`, `tests/test_foundation.py`, `web/foundation/app.js`, `api.js`, `contracts.d.ts`, `style.css`, root README/PLAN, `docs/FOUNDATION.md`, `docs/foundation-openapi.json`.

Checks: existing platform pytest command, frontend `npm run build` (ESLint, syntax, API type checks), targeted final climate regressions. Source tests run offline; live HTTP verification is separate from CI.
