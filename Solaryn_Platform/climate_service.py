"""CLIM-001–005: hourly source snapshots and deterministic resource summaries.

No PV performance or recommendation calculations. See docs/CLIMATE_INTEGRATION.md.
"""
from calendar import isleap, monthrange
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3
from statistics import mean
from uuid import uuid4

import requests

VERSION = "climate-1.0.1"
DEFAULT_YEAR = 2023
ENDPOINTS = {
    "PVGIS": "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc",
    "NASA_POWER": "https://power.larc.nasa.gov/api/temporal/hourly/point",
}
UNITS = {"annual_ghi": "kWh/m²/year", "irradiance": "W/m²", "air_temperature": "°C",
         "wind_speed": "m/s", "relative_humidity": "%"}
FIELDS = ["ghi_w_m2", "air_temperature_c", "wind_speed_m_s", "relative_humidity_pct"]
GEOMETRY = {"plane": "horizontal", "tilt_deg": 0, "horizon_shading": False}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def query_for(provider, site, year):
    if provider == "PVGIS":
        return dict(lat=site["latitude"], lon=site["longitude"], startyear=year, endyear=year,
                    angle=0, aspect=0, usehorizon=0, components=1, pvcalculation=0, outputformat="json")
    return {"latitude": site["latitude"], "longitude": site["longitude"], "start": f"{year}0101",
            "end": f"{year}1231", "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,T2M,WS10M,RH2M",
            "community": "RE", "format": "JSON", "time-standard": "UTC"}


def fetch_raw(provider, query):
    response = requests.get(ENDPOINTS[provider], params=query, timeout=(10, 75))
    if not response.ok:
        try:
            payload = response.json()
            message = payload.get("message") or payload.get("messages") or response.reason
        except ValueError:
            message = response.reason
        raise ValueError(f"{provider} HTTP {response.status_code}: {str(message)[:400]}")
    if len(response.content) > 20_000_000:
        raise ValueError("Provider response exceeds the 20 MB limit")
    return response.content


def clean(value, minimum=None, maximum=None, fill=-999):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number == fill:
        return None
    if (minimum is not None and number < minimum) or (maximum is not None and number > maximum):
        return None
    return number


def require_unit(metadata, field, accepted):
    unit = metadata.get(field, {}).get("units")
    if unit not in accepted:
        raise ValueError(f"Unsupported or missing units for {field}: {unit}")
    return unit


def normalize(provider, payload, year):
    """Preserve timestamps; each provider sample represents a one-hour interval.

    NASA hourly Wh/m² divided by 1 h is numerically W/m². PVGIS components on
    requested tilt=0 sum to GHI; beam-on-horizontal is never mislabeled DNI.
    """
    rows, warnings = [], []
    if provider == "PVGIS":
        inputs = payload["inputs"]
        slope = inputs["mounting_system"]["fixed"]["slope"]["value"]
        if slope != 0 or inputs["meteo_data"]["use_horizon"]:
            raise ValueError("PVGIS returned incompatible geometry")
        meta = payload["meta"]["outputs"]["hourly"]["variables"]
        for field in ["Gb(i)", "Gd(i)", "Gr(i)"]:
            require_unit(meta, field, {"W/m2", "W/m^2"})
        require_unit(meta, "T2m", {"degree Celsius", "°C"})
        require_unit(meta, "WS10m", {"m/s"})
        for row in payload["outputs"]["hourly"]:
            components = [clean(row.get(k), minimum=0) for k in ["Gb(i)", "Gd(i)", "Gr(i)"]]
            rows.append({"timestamp_utc": datetime.strptime(row["time"], "%Y%m%d:%H%M").replace(tzinfo=timezone.utc).isoformat(),
                         "ghi_w_m2": sum(components) if all(v is not None for v in components) else None,
                         "dhi_w_m2": components[1], "dni_w_m2": None,
                         "air_temperature_c": clean(row.get("T2m"), minimum=-273.15),
                         "wind_speed_m_s": clean(row.get("WS10m"), minimum=0),
                         "relative_humidity_pct": None})
        reconstructed = sum(row.get("Int") == 1 for row in payload["outputs"]["hourly"])
        if reconstructed:
            warnings.append(f"PVGIS flags {reconstructed} solar samples as reconstructed by the provider.")
        warnings.append("PVGIS sample minute offsets are preserved; annual/monthly cross-checks do not imply aligned instantaneous samples.")
        provenance = {"database": inputs["meteo_data"], "returned_location": inputs["location"],
                      "api_version": "5.3", "source_units": meta}
    else:
        if payload["header"]["time_standard"] != "UTC":
            raise ValueError("NASA POWER did not return UTC timestamps")
        meta = payload["parameters"]
        for field in ["ALLSKY_SFC_SW_DWN", "ALLSKY_SFC_SW_DNI", "ALLSKY_SFC_SW_DIFF"]:
            require_unit(meta, field, {"Wh/m^2", "Wh/m2", "W/m^2", "W/m2"})
        require_unit(meta, "T2M", {"C", "°C"})
        require_unit(meta, "WS10M", {"m/s"})
        require_unit(meta, "RH2M", {"%"})
        parameters = payload["properties"]["parameter"]
        times = sorted(set().union(*(set(values) for values in parameters.values())))
        fill = payload["header"].get("fill_value", -999)
        for key in times:
            def field(name, low=None, high=None):
                return clean(parameters.get(name, {}).get(key), low, high, fill)
            rows.append({"timestamp_utc": datetime.strptime(key, "%Y%m%d%H").replace(tzinfo=timezone.utc).isoformat(),
                         "ghi_w_m2": field("ALLSKY_SFC_SW_DWN", 0), "dni_w_m2": field("ALLSKY_SFC_SW_DNI", 0),
                         "dhi_w_m2": field("ALLSKY_SFC_SW_DIFF", 0), "air_temperature_c": field("T2M", -273.15),
                         "wind_speed_m_s": field("WS10M", 0), "relative_humidity_pct": field("RH2M", 0, 100)})
        warnings.extend(str(message) for message in payload.get("messages", []))
        provenance = {"database": payload["header"].get("sources"), "returned_location": payload.get("geometry"),
                      "api_version": payload["header"].get("api", {}).get("version"), "source_units": meta}
    if not rows:
        raise ValueError("Provider returned no hourly records")
    rows.sort(key=lambda row: row["timestamp_utc"])
    times = [datetime.fromisoformat(row["timestamp_utc"]) for row in rows]
    if any(time.year != year for time in times):
        raise ValueError("Provider returned records outside the requested year")
    hour_keys = [time.replace(minute=0, second=0, microsecond=0) for time in times]
    if len(set(hour_keys)) != len(hour_keys):
        raise ValueError("Duplicate hourly timestamps in provider response")
    offsets = {(time.minute, time.second) for time in times}
    if len(offsets) != 1:
        raise ValueError("Inconsistent provider hourly timestamp offsets")
    expected = (366 if isleap(year) else 365) * 24
    counts = {field: sum(row[field] is not None for row in rows) for field in FIELDS}
    def avg(field, subset=rows):
        values = [row[field] for row in subset if row[field] is not None]
        return mean(values) if values else None
    complete = len(rows) == expected and counts["ghi_w_m2"] == expected
    monthly = []
    for month in range(1, 13):
        group = [row for row in rows if datetime.fromisoformat(row["timestamp_utc"]).month == month]
        valid = [row["ghi_w_m2"] for row in group if row["ghi_w_m2"] is not None]
        monthly.append({"month": month, "ghi_kwh_m2": sum(valid) / 1000 if len(valid) == monthrange(year, month)[1] * 24 else None,
                        "valid_ghi_hours": len(valid), "air_temperature_c": avg("air_temperature_c", group)})
    metrics = {"annual_ghi": sum(row["ghi_w_m2"] for row in rows) / 1000 if complete else None,
               "irradiance": avg("ghi_w_m2"), "air_temperature": avg("air_temperature_c"),
               "wind_speed": avg("wind_speed_m_s"), "relative_humidity": avg("relative_humidity_pct")}
    if not complete:
        warnings.append(f"Incomplete solar series: {counts['ghi_w_m2']} valid hours of {expected}. Annual GHI is withheld; no missing values were filled.")
    for field in FIELDS[1:]:
        if counts[field] != expected:
            warnings.append(f"{field}: {counts[field]} valid samples of {expected}; any displayed mean uses available samples only.")
    return {"hourly": rows, "metrics": metrics, "monthly": monthly, "coverage": {"expected_hours": expected, "received_hours": len(rows), "valid_hours": counts},
            "warnings": warnings, "provenance": provenance, "complete_ghi": complete}


class ClimateService:
    def __init__(self, db_path, fetcher=fetch_raw):
        self.db_path, self.fetcher = db_path, fetcher
        with closing(sqlite3.connect(db_path)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS climate_sources (id TEXT PRIMARY KEY, request_key TEXT NOT NULL, payload TEXT NOT NULL, raw BLOB NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS climate_request_key ON climate_sources(request_key)")
            db.execute("CREATE TABLE IF NOT EXISTS climate_snapshots (id TEXT PRIMARY KEY, site_id TEXT NOT NULL, payload TEXT NOT NULL)")
            db.commit()

    def latest(self, site_id):
        with closing(sqlite3.connect(self.db_path)) as db:
            row = db.execute("SELECT payload FROM climate_snapshots WHERE site_id=? ORDER BY rowid DESC LIMIT 1", (site_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def source(self, identifier):
        with closing(sqlite3.connect(self.db_path)) as db:
            row = db.execute("SELECT payload,raw FROM climate_sources WHERE id=?", (identifier,)).fetchone()
        return (json.loads(row[0]), row[1]) if row else None

    def provider(self, provider, site, year, refresh):
        query = query_for(provider, site, year)
        request_key = hashlib.sha256(encoded([VERSION, ENDPOINTS[provider], query]).encode()).hexdigest()
        if not refresh:
            with closing(sqlite3.connect(self.db_path)) as db:
                row = db.execute("SELECT payload FROM climate_sources WHERE request_key=? ORDER BY rowid DESC LIMIT 1", (request_key,)).fetchone()
            if row:
                payload = json.loads(row[0])
                return {**self.summary(payload), "cache_hit": True}
        try:
            raw = self.fetcher(provider, query)
            payload = normalize(provider, json.loads(raw), year)
            payload.update({"id": str(uuid4()), "provider": provider, "year": year, "request": query,
                            "endpoint": ENDPOINTS[provider], "requested_location": {"latitude": site["latitude"], "longitude": site["longitude"]},
                            "raw_sha256": hashlib.sha256(raw).hexdigest(), "retrieved_at": timestamp(), "normalizer_version": VERSION,
                            "geometry": GEOMETRY, "time_standard": "UTC", "sample_duration_hours": 1,
                            "canonical_units": {"ghi_w_m2": "W/m²", "dni_w_m2": "W/m²", "dhi_w_m2": "W/m²",
                                                "air_temperature_c": "°C", "wind_speed_m_s": "m/s", "relative_humidity_pct": "%"}})
            with closing(sqlite3.connect(self.db_path)) as db:
                db.execute("INSERT INTO climate_sources VALUES (?,?,?,?)", (payload["id"], request_key, encoded(payload), raw))
                db.commit()
            return {**self.summary(payload), "cache_hit": False}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            return {"provider": provider, "status": "UNAVAILABLE", "error": str(exc)[:500], "metrics": dict.fromkeys(UNITS), "monthly": [], "warnings": [], "source_id": None}

    @staticmethod
    def summary(payload):
        result = {key: val for key, val in payload.items() if key != "hourly"}
        result["source_id"] = result.pop("id")
        result["status"] = "AVAILABLE" if payload["complete_ghi"] else "INCOMPLETE"
        return result

    def retrieve(self, site, year, refresh=False):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda name: self.provider(name, site, year, refresh), ENDPOINTS))
        by_name = {item["provider"]: item for item in results}
        primary = by_name["PVGIS"]
        if primary["status"] != "AVAILABLE":
            primary = by_name["NASA_POWER"] if by_name["NASA_POWER"]["status"] == "AVAILABLE" else primary
        if primary["status"] == "UNAVAILABLE":
            primary = next((item for item in results if item["status"] != "UNAVAILABLE"), primary)
        metrics = dict(primary["metrics"])
        metric_sources = {key: primary["provider"] if val is not None else None for key, val in metrics.items()}
        if metrics["relative_humidity"] is None and by_name["NASA_POWER"]["metrics"]["relative_humidity"] is not None:
            metrics["relative_humidity"] = by_name["NASA_POWER"]["metrics"]["relative_humidity"]
            metric_sources["relative_humidity"] = "NASA_POWER"
        pvgis = by_name["PVGIS"]["metrics"]["annual_ghi"]
        nasa = by_name["NASA_POWER"]["metrics"]["annual_ghi"]
        delta = 100 * (nasa - pvgis) / pvgis if pvgis is not None and pvgis > 0 and nasa is not None else None
        crosscheck = {"status": "AVAILABLE" if delta is not None else "UNAVAILABLE", "pvgis_annual_ghi_kwh_m2": pvgis,
                      "nasa_annual_ghi_kwh_m2": nasa, "difference_pct": delta,
                      "definition": "100 × (NASA POWER − PVGIS) / PVGIS; same calendar year, horizontal plane, no horizon shading.",
                      "warning": "Resource discrepancy is descriptive, not an uncertainty estimate or pass/fail validation. Provider grids and sampling differ."}
        warnings = ["Historical reference year; these are gridded resource estimates, not current weather or on-site measurements.", crosscheck["warning"]]
        for item in results:
            if item["status"] == "UNAVAILABLE":
                warnings.append(f"{item['provider']}: {item['error']}")
        if primary["provider"] != "PVGIS":
            warnings.append("NASA POWER is displayed as the fallback because complete PVGIS solar data are unavailable. Sources are not averaged.")
        status = "AVAILABLE" if all(item["status"] == "AVAILABLE" for item in results) else "PARTIAL" if any(item["status"] != "UNAVAILABLE" for item in results) else "UNAVAILABLE"
        snapshot = {"id": str(uuid4()), "status": status, "site": site, "year": year, "period": str(year),
                    "provider": primary["provider"] if primary["status"] != "UNAVAILABLE" else None,
                    "metrics": metrics, "metric_sources": metric_sources, "units": UNITS, "monthly": primary["monthly"],
                    "providers": results, "crosscheck": crosscheck, "warnings": warnings, "geometry": GEOMETRY,
                    "created_at": timestamp(), "normalizer_version": VERSION}
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute("INSERT INTO climate_snapshots VALUES (?,?,?)", (snapshot["id"], site["id"], encoded(snapshot)))
            db.commit()
        return snapshot


def empty_snapshot(site):
    return {"status": "NOT_REQUESTED", "site": site, "provider": None, "period": None, "year": DEFAULT_YEAR,
            "metrics": dict.fromkeys(UNITS), "units": UNITS, "warnings": [], "providers": [], "monthly": [],
            "metric_sources": {}, "crosscheck": {"status": "NOT_REQUESTED", "difference_pct": None}}
