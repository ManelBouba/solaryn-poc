"""Map-first platform with immutable climate and provisional screening runs."""
from contextlib import closing
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import uuid4
from climate_service import ClimateService, DEFAULT_YEAR, empty_snapshot
from performance_v2 import Configuration, calculate
from catalog_service import catalog, families as catalog_families
from report_service import html_report, evidence_package, dashboard, STYLE

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web/foundation"
CATALOG = ROOT.parent / "data/raw/module_candidate_master.csv"
FAMILIES = ["PERC / PERC+", "TOPCon", "HJT / SHJ", "Back-contact / IBC / HPBC / ABC", "CdTe", "CIGS"]


class SiteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, description="WGS84 decimal degrees")
    longitude: float = Field(ge=-180, le=180, description="WGS84 decimal degrees")


class Site(SiteInput):
    id: str
    created_at: str


class AnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site_id: str
    module_ids: list[str] = Field(min_length=3, max_length=10)


class ClimateSnapshot(BaseModel):
    status: Literal["NOT_REQUESTED", "AVAILABLE", "PARTIAL", "UNAVAILABLE"]
    site: Site
    provider: str | None = None
    period: str | None = None
    metrics: dict[str, float | None]
    units: dict[str, str]
    warnings: list[str]
    id: str | None = None
    year: int = DEFAULT_YEAR
    metric_sources: dict[str, str | None] = Field(default_factory=dict)
    monthly: list[dict] = Field(default_factory=list)
    providers: list[dict] = Field(default_factory=list)
    crosscheck: dict = Field(default_factory=dict)
    geometry: dict = Field(default_factory=dict)
    created_at: str | None = None
    normalizer_version: str | None = None


class ClimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int = Field(default=DEFAULT_YEAR, ge=2005, le=datetime.now(timezone.utc).year - 1)
    refresh: bool = False


class ModuleRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    module_id: str
    manufacturer: str
    model: str
    technology: str
    rated_power_w: float | None
    efficiency_pct: float | None
    temperature_coefficient_pct_per_c: float | None
    bifacial: bool | None
    commercial_status: Literal["UNKNOWN", "COMMERCIAL", "COMMERCIAL_LEGACY", "COMMERCIAL_NICHE", "LIMITED_COMMERCIAL"]
    evidence: str
    source_url: str | None
    source_note: str | None
    source_checked_at: str | None


class CatalogResponse(BaseModel):
    modules: list[ModuleRecord]
    release: str
    source: str
    warning: str


class Stage(BaseModel):
    name: str
    status: Literal["SAVED", "READY", "SELECTED", "NOT_IMPLEMENTED", "AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_REQUESTED"]


class PendingDecision(BaseModel):
    recommended_candidate: None = None
    strength: None = None
    ranking: list = Field(default_factory=list, max_length=0)


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    schema_version: Literal["foundation-1", "screening-1"]
    status: Literal["NOT_IMPLEMENTED", "SAVED", "COMPLETED", "CANNOT_RECOMMEND"]
    created_at: str
    site: Site
    selected_modules: list[ModuleRecord]
    catalog_release: str
    catalog_source: str
    stages: list[Stage]
    decision: dict
    contributions: list
    model_path: str | None
    model_version: str | None
    validation_status: str
    extrapolation: str | None
    assumptions: list[str]
    warnings: list[str]
    climate_snapshot: dict | None = None
    parent_request_id: str | None = None
    frozen_inputs: dict | None = None
    configuration: dict | None = None
    manifest: dict | None = None
    candidate_failures: list = Field(default_factory=list)
    explanation: str | None = None
    implementation_sources: dict[str, str] | None = None
    visual_data: dict | None = None


def create_app(db_path=None, climate_fetcher=None):
    db_path = Path(db_path or ROOT / "workspace/foundation.sqlite3")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)")
        db.commit()

    climate_service = ClimateService(db_path, climate_fetcher) if climate_fetcher else ClimateService(db_path)

    def save(kind, payload):
        if kind == "analysis":
            payload = AnalysisResponse.model_validate(payload).model_dump()
        with closing(sqlite3.connect(db_path)) as db:
            db.execute("INSERT INTO records VALUES (?, ?, ?)", (payload["id"], kind, json.dumps(payload, allow_nan=False)))
            db.commit()
        return payload

    def read(kind, identifier):
        with closing(sqlite3.connect(db_path)) as db:
            row = db.execute("SELECT payload FROM records WHERE id=? AND kind=?", (identifier, kind)).fetchone()
        if row is None:
            raise HTTPException(404, "Record not found")
        return json.loads(row[0])

    app = FastAPI(title="SOLARYN Foundation", version="0.1.0", docs_url="/api/docs")

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": "0.3.0", "climate": "PVGIS + NASA_POWER", "science": "PROVISIONAL_DATASHEET_SCREENING"}

    @app.post("/api/v1/sites", response_model=Site, status_code=201)
    def create_site(site: SiteInput):
        return save("site", {**site.model_dump(), "id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat()})

    @app.get("/api/v1/sites", response_model=list[Site])
    def sites():
        with closing(sqlite3.connect(db_path)) as db:
            rows = db.execute("SELECT payload FROM records WHERE kind='site' ORDER BY rowid DESC LIMIT 20").fetchall()
        return [json.loads(row[0]) for row in rows]

    @app.get("/api/v1/sites/{site_id}", response_model=Site)
    def get_site(site_id: str):
        return read("site", site_id)

    @app.get("/api/v1/sites/{site_id}/climate-snapshot", response_model=ClimateSnapshot)
    def climate(site_id: str):
        site = read("site", site_id)
        return climate_service.latest(site_id) or empty_snapshot(site)

    @app.post("/api/v1/sites/{site_id}/climate-snapshot", response_model=ClimateSnapshot, status_code=201)
    def retrieve_climate(site_id: str, request: ClimateRequest):
        return climate_service.retrieve(read("site", site_id), request.year, request.refresh)

    @app.get("/api/v1/climate-sources/{source_id}/export")
    def export_climate_source(source_id: str, raw: bool = False):
        record = climate_service.source(source_id)
        if record is None:
            raise HTTPException(404, "Climate source not found")
        payload, original = record
        from fastapi.responses import Response
        return Response(original if raw else json.dumps(payload, allow_nan=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="solaryn-climate-{payload["id"]}{"-raw" if raw else ""}.json"'})

    @app.get("/api/v1/technology-families", response_model=list[str])
    def families():
        return [group["name"] for group in catalog_families()]

    @app.get("/api/v1/modules", response_model=CatalogResponse)
    def modules():
        return catalog()

    @app.post("/api/v1/analyses", response_model=AnalysisResponse, status_code=201)
    def analyse(inputs: AnalysisInput):
        site = read("site", inputs.site_id)
        source = catalog()
        if len(set(inputs.module_ids)) != len(inputs.module_ids):
            raise HTTPException(422, "Select distinct modules")
        lookup = {row["module_id"]: row for row in source["modules"]}
        if any(identifier not in lookup for identifier in inputs.module_ids):
            raise HTTPException(422, "Unknown module")
        frozen_climate = climate_service.latest(inputs.site_id)
        return save("analysis", {
            "id": str(uuid4()), "schema_version": "foundation-1", "status": "SAVED",
            "created_at": datetime.now(timezone.utc).isoformat(), "site": site,
            "selected_modules": [lookup[identifier] for identifier in inputs.module_ids],
            "catalog_release": source["release"], "catalog_source": source["source"],
            "climate_snapshot": frozen_climate,
            "stages": [{"name": name, "status": status} for name, status in [
                ("SITE", "SAVED"), ("CLIMATE", frozen_climate["status"] if frozen_climate else "NOT_REQUESTED"), ("TECHNOLOGIES", "SELECTED"),
                ("PHYSICS", "READY"), ("LIFETIME", "NOT_REQUESTED"),
                ("ECONOMICS", "NOT_REQUESTED"), ("RECOMMENDATION", "NOT_REQUESTED")]],
            "decision": {"recommended_candidate": None, "strength": None, "ranking": []},
            "contributions": [], "model_path": None, "model_version": None,
            "validation_status": "NOT_RUN", "extrapolation": None, "assumptions": [],
            "warnings": ["This request is saved. Review the project assumptions and run the provisional comparison.", source["warning"]],
        })

    @app.post("/api/v1/analyses/{analysis_id}/run", response_model=AnalysisResponse, status_code=201)
    def run_analysis(analysis_id: str, configuration: Configuration):
        request = read("analysis", analysis_id)
        frozen = request.get("frozen_inputs")
        if frozen is None:
            snapshot = request.get("climate_snapshot")
            if not snapshot:
                raise HTTPException(422, "Load site conditions, then prepare a new request to freeze its climate data.")
            summary = next((p for p in snapshot["providers"] if p["provider"] == snapshot["provider"]), None)
            stored = climate_service.source(summary["source_id"]) if summary and summary.get("source_id") else None
            if stored is None:
                raise HTTPException(422, "The frozen primary hourly climate source is unavailable. Load conditions and prepare a new request.")
            source, raw = stored
            if hashlib.sha256(raw).hexdigest() != source["raw_sha256"]:
                raise HTTPException(422, "Climate source integrity check failed")
            frozen = {"source": source, "site": request["site"], "modules": request["selected_modules"],
                      "catalog_release": request["catalog_release"], "catalog_source": request["catalog_source"]}
        try:
            output = calculate(frozen, configuration.model_dump())
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        feasible = bool(output["decision"]["ranking"])
        result = {**request, **output, "id": str(uuid4()), "parent_request_id": analysis_id,
                  "schema_version": "screening-1", "status": "COMPLETED" if feasible else "CANNOT_RECOMMEND",
                  "created_at": datetime.now(timezone.utc).isoformat(), "frozen_inputs": frozen,
                  "stages": [{"name": name, "status": status} for name, status in [
                      ("SITE", "SAVED"), ("CLIMATE", "AVAILABLE"), ("TECHNOLOGIES", "SELECTED"),
                      ("PHYSICS", "UNAVAILABLE" if not feasible else "PARTIAL" if output["candidate_failures"] else "AVAILABLE"),
                      ("LIFETIME", ("AVAILABLE" if feasible else "UNAVAILABLE") if configuration.lifetime else "NOT_REQUESTED"),
                      ("ECONOMICS", ("AVAILABLE" if feasible else "UNAVAILABLE") if configuration.economics else "NOT_REQUESTED"),
                      ("RECOMMENDATION", "AVAILABLE" if feasible else "UNAVAILABLE")]]}
        return save("analysis", result)

    @app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse)
    def analysis(analysis_id: str):
        return read("analysis", analysis_id)

    @app.get("/api/v1/analyses/{analysis_id}/export", response_model=AnalysisResponse)
    def export_analysis(analysis_id: str):
        result = read("analysis", analysis_id)
        return JSONResponse(result, headers={"Content-Disposition": f'attachment; filename="solaryn-request-{result["id"]}.json"'})

    @app.get("/api/v1/analyses/{analysis_id}/visuals")
    def visuals(analysis_id: str):
        result = read("analysis", analysis_id)
        if not result.get("decision", {}).get("ranking"):
            raise HTTPException(409, "A ranked calculation is required")
        return {"html": '<style>'+STYLE+'</style><div class="epc">'+dashboard(result)+'</div>'}

    @app.get("/api/v1/analyses/{analysis_id}/report")
    def report(analysis_id: str, inline: bool = False):
        result = read("analysis", analysis_id)
        try:
            body = html_report(result)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return Response(body, media_type="text/html", headers={"Content-Disposition":
            f'{"inline" if inline else "attachment"}; filename="SOLARYN-{result["id"]}-EPC.html"'})

    @app.get("/api/v1/analyses/{analysis_id}/package")
    def package(analysis_id: str):
        result = read("analysis", analysis_id)
        try:
            body = evidence_package(result)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return Response(body, media_type="application/zip", headers={"Content-Disposition":
            f'attachment; filename="SOLARYN-{result["id"]}-evidence.zip"'})

    app.mount("/assets", StaticFiles(directory=WEB), name="assets")
    app.mount("/brand", StaticFiles(directory=ROOT.parent / "frontend/public/brand"), name="brand")

    @app.get("/{route:path}", include_in_schema=False)
    def page(route: str):
        if route not in {"", "site", "conditions", "candidates", "processing", "results", "evidence"}:
            raise HTTPException(404, "Page not found")
        return FileResponse(WEB / "index.html")

    return app
