"""Solaryn platform foundation: authenticated organization-scoped workflows."""
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import Literal
import base64
import hashlib
import hmac
import importlib.util
import json
import os
import secrets
import sqlite3
import sys
import time
import uuid

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from physics_bridge import catalog as physics_catalog, run_physics, read_result as read_physics, package as package_physics

ROOT = Path(__file__).resolve().parent
# Load the existing scientific module directly, avoiding collisions with older src packages.
spec = importlib.util.spec_from_file_location("solaryn_procurement", ROOT.parent / "Solaryn_Pilot/src/procurement_model.py")
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)


def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
def pack(value): return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))
def digest(value): return hashlib.sha256(value.encode()).hexdigest()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Credentials(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def email_shape(cls, value):
        value = value.lower()
        if "@" not in value or any(c.isspace() for c in value):
            raise ValueError("Enter an email address")
        return value


class Register(Credentials):
    organization: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=120)


class Member(Credentials):
    name: str = Field(min_length=2, max_length=120)
    role: Literal["editor", "reviewer", "viewer"]


class ProjectInput(Input):
    parameters: dict
    latitude: float = Field(default=24.71, ge=-90, le=90)
    longitude: float = Field(default=46.67, ge=-180, le=180)
    climate: list[Literal["Heat", "Dust", "Humidity", "Salt", "Hail / wind", "UV"]] = Field(default_factory=list, max_length=6)
    revision: int | None = None


class OfferInput(Input):
    parameters: dict
    revision: int


class DocumentInput(Input):
    filename: str = Field(min_length=1, max_length=180)
    content_base64: str = Field(max_length=7_000_000)


class ClaimInput(Input):
    candidate_id: str
    document_id: str
    field: Literal["net_ac_kwh_kwp", "quote_eur_w", "degradation", "bom"]
    section: str = Field(min_length=1, max_length=250)
    excerpt: str = Field(min_length=1, max_length=4000)
    classification: Literal["Fact", "Assumption", "Model output", "Expert judgment"]


class ReviewInput(Input):
    status: Literal["Reviewed", "Rejected"]
    comment: str = Field(min_length=3, max_length=4000)


class ScenarioInput(Input):
    degradation_add: float = Field(default=0, ge=0, le=.2)
    yield_haircut: float = Field(default=0, ge=0, le=.99)
    revision: int


class PhysicsInput(Input):
    revision: int
    module_ids: list[str] = Field(min_length=2,max_length=5)
    weather_source: Literal['riyadh_reference','live_nasa'] = 'riyadh_reference'
    weather_year: int = Field(default=2020,ge=2001,le=2025)
    tilt_deg: float = Field(default=25,ge=0,le=90)
    azimuth_deg: float = Field(default=180,ge=0,le=360)
    soiling_pct: float = Field(default=2,ge=0,le=50)
    row_geometry: bool = False
    albedo: float = Field(default=.2,ge=0,le=1)
    gcr: float = Field(default=.4,gt=0,lt=1)
    height_m: float = Field(default=1.5,gt=0,le=10)
    pitch_m: float = Field(default=5,gt=0,le=30)
    dc_ac_ratio: float = Field(default=1.3,ge=.5,le=3)
    inverter_efficiency: float = Field(default=.97,ge=.5,le=1)
    availability: float = Field(default=.99,ge=.01,le=1)
    curtailment: float = Field(default=0,ge=0,le=.99)
    degradation: float = Field(default=.005,ge=0,le=.2)
    yield_log_sigma: float | None = Field(default=None,ge=0,le=.5)
    quotes_eur_w: dict[str,float] = Field(default_factory=dict)

    @field_validator('quotes_eur_w')
    @classmethod
    def quotes(cls,value):
        if any(not 0<=v<=100 for v in value.values()): raise ValueError('Prices must be EUR/W between 0 and 100')
        return value


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, org TEXT NOT NULL REFERENCES organizations(id), email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts(email TEXT PRIMARY KEY, count INTEGER NOT NULL, until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, org TEXT NOT NULL REFERENCES organizations(id), payload TEXT NOT NULL, revision INTEGER NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offers(id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id), payload TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id), filename TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id), payload TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, run TEXT UNIQUE NOT NULL REFERENCES runs(id), actor TEXT NOT NULL REFERENCES users(id), comment TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS physics_runs(id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, org TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, entity TEXT NOT NULL, details TEXT NOT NULL, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS projects_org ON projects(org);
CREATE INDEX IF NOT EXISTS offers_project ON offers(project);
CREATE INDEX IF NOT EXISTS audit_org ON audit(org,id);
"""


def create_app(db_path=None):
    path = Path(db_path or os.environ.get("SOLARYN_DB", ROOT / "workspace/platform.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    @contextmanager
    def db():
        connection = sqlite3.connect(path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()
    with db() as conn: conn.executescript(SCHEMA)
    app = FastAPI(title="Solaryn Platform", version="0.1.0", docs_url=None, redoc_url=None)
    secure = os.environ.get("SOLARYN_SECURE_COOKIES", "0") == "1"

    @app.middleware("http")
    async def boundaries(request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin writes are forbidden"}, status_code=403)
            # A bounded receive prevents chunked requests bypassing a Content-Length check.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 8_000_000:
                    return JSONResponse({"detail": "Request exceeds 8 MB"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith("/api/"): response.headers["Cache-Control"] = "no-store"
        return response

    def actor(request: Request):
        token = request.cookies.get("solaryn_session", "")
        with db() as conn:
            row = conn.execute("SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?", (digest(token), time.time())).fetchone()
        if not row: raise HTTPException(401, "Sign in to continue")
        if request.method not in ("GET", "HEAD") and not hmac.compare_digest(request.headers.get("x-csrf-token", ""), row["csrf"]):
            raise HTTPException(403, "Invalid session CSRF token")
        return dict(row)

    def role(user, *roles):
        if user["role"] not in roles: raise HTTPException(403, "Your role cannot perform this action")

    def project(conn, pid, user):
        row = conn.execute("SELECT * FROM projects WHERE id=? AND org=?", (pid, user["org"])).fetchone()
        if not row: raise HTTPException(404, "Project not found")
        return row

    def revision(row, expected):
        if row["revision"] != expected: raise HTTPException(409, "Project changed. Refresh before saving or running.")

    def bump(conn, pid): conn.execute("UPDATE projects SET revision=revision+1 WHERE id=?", (pid,))
    def audit(conn, user, action, entity, details=None):
        conn.execute("INSERT INTO audit(org,actor,action,entity,details,created) VALUES(?,?,?,?,?,?)", (user["org"], user["id"], action, entity, pack(details or {}), now()))

    def validated(cls, parameters, years=None):
        try:
            obj = cls(**parameters)
            for key, value in asdict(obj).items():
                if key in ("name", "model", "bom", "yield_source") and (not isinstance(value, str) or not value.strip() or len(value) > 1000):
                    raise ValueError(f"{key} must be nonempty text of at most 1000 characters")
            obj.validate() if years is None else obj.validate(years)
            pack(asdict(obj))
            return obj
        except (TypeError, ValueError) as exc: raise HTTPException(422, str(exc)) from None

    def public_user(user):
        return {k: user[k] for k in ("id", "email", "name", "role", "org")}

    def password_hash(password, salt):
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

    def add_user(conn, org, data, role_name):
        ident, salt = uid(), secrets.token_hex(16)
        conn.execute("INSERT INTO users(id,org,email,name,role,salt,password) VALUES(?,?,?,?,?,?,?)", (ident, org, data.email, data.name, role_name, salt, password_hash(data.password, salt)))
        return dict(conn.execute("SELECT * FROM users WHERE id=?", (ident,)).fetchone())

    def session(conn, user, response):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        conn.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        conn.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest(token), user["id"], csrf, time.time()+8*3600))
        response.set_cookie("solaryn_session", token, max_age=8*3600, httponly=True, secure=secure, samesite="strict", path="/")
        return {"user": public_user(user), "csrf": csrf}

    @app.get("/api/v1/health")
    def health(): return {"status": "ok", "model_version": model.MODEL_VERSION}

    @app.post("/api/v1/auth/register", status_code=201)
    def register(data: Register, response: Response):
        try:
            with db() as conn:
                org = uid()
                conn.execute("INSERT INTO organizations VALUES(?,?)", (org, data.organization))
                user = add_user(conn, org, data, "owner")
                audit(conn, user, "organization.created", org)
                return session(conn, user, response)
        except sqlite3.IntegrityError: raise HTTPException(409, "Account already exists")

    @app.post("/api/v1/auth/login")
    def login(data: Credentials, response: Response):
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            attempt = conn.execute("SELECT * FROM login_attempts WHERE email=?", (data.email,)).fetchone()
            if attempt and attempt["count"] >= 8 and attempt["until"] > time.time():
                raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
            user = conn.execute("SELECT * FROM users WHERE email=?", (data.email,)).fetchone()
            calculated = password_hash(data.password, user["salt"] if user else "00"*16)
            valid = user is not None and hmac.compare_digest(calculated, user["password"])
            if not valid:
                count = attempt["count"]+1 if attempt and attempt["until"] > time.time() else 1
                conn.execute("INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)", (data.email, count, time.time()+900))
            else:
                conn.execute("DELETE FROM login_attempts WHERE email=?", (data.email,))
                return session(conn, dict(user), response)
        raise HTTPException(401, "Invalid email or password")

    @app.get("/api/v1/auth/me")
    def me(user=Depends(actor)):
        with db() as conn:
            org = conn.execute("SELECT name FROM organizations WHERE id=?", (user["org"],)).fetchone()[0]
        return {"user": public_user(user), "csrf": user["csrf"], "organization": org}

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response, user=Depends(actor)):
        with db() as conn: conn.execute("DELETE FROM sessions WHERE token=?", (digest(request.cookies["solaryn_session"]),))
        response.delete_cookie("solaryn_session", path="/")
        return {"ok": True}

    @app.get("/api/v1/members")
    def members(user=Depends(actor)):
        with db() as conn:
            return [public_user(dict(r)) for r in conn.execute("SELECT * FROM users WHERE org=? ORDER BY name", (user["org"],))]

    @app.post("/api/v1/members", status_code=201)
    def member(data: Member, user=Depends(actor)):
        role(user, "owner")
        try:
            with db() as conn:
                created = add_user(conn, user["org"], data, data.role)
                audit(conn, user, "member.created", created["id"], {"role": data.role})
                return public_user(created)
        except sqlite3.IntegrityError: raise HTTPException(409, "Account already exists")

    @app.get("/api/v1/projects")
    def projects(user=Depends(actor)):
        with db() as conn:
            return [{"id": r["id"], "revision": r["revision"], "created": r["created"], **json.loads(r["payload"]),
                     "candidate_count": conn.execute("SELECT count(*) FROM offers WHERE project=?", (r["id"],)).fetchone()[0]}
                    for r in conn.execute("SELECT * FROM projects WHERE org=? ORDER BY created DESC", (user["org"],)).fetchall()]

    @app.post("/api/v1/projects", status_code=201)
    def create_project(data: ProjectInput, user=Depends(actor)):
        role(user, "owner", "editor")
        parameters = asdict(validated(model.Project, data.parameters))
        payload = {**data.model_dump(exclude={"revision"}), "parameters": parameters}
        with db() as conn:
            pid = uid()
            conn.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (pid, user["org"], pack(payload), 1, now()))
            audit(conn, user, "project.created", pid)
        return {"id": pid, "revision": 1, **payload}

    @app.put("/api/v1/projects/{pid}")
    def update_project(pid: str, data: ProjectInput, user=Depends(actor)):
        role(user, "owner", "editor")
        parameters = asdict(validated(model.Project, data.parameters))
        payload = {**data.model_dump(exclude={"revision"}), "parameters": parameters}
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = project(conn, pid, user)
            revision(current, data.revision)
            for offer in conn.execute("SELECT payload FROM offers WHERE project=?", (pid,)):
                validated(model.Candidate, json.loads(offer[0]), parameters["years"])
            conn.execute("UPDATE projects SET payload=?,revision=revision+1 WHERE id=?", (pack(payload), pid))
            audit(conn, user, "project.updated", pid)
        return {"id": pid}

    @app.get("/api/v1/projects/{pid}")
    def detail(pid: str, user=Depends(actor)):
        with db() as conn:
            p = project(conn, pid, user)
            return {"id": pid, "revision": p["revision"], **json.loads(p["payload"]),
                    "offers": [{"id": r["id"], "parameters": json.loads(r["payload"])} for r in conn.execute("SELECT * FROM offers WHERE project=? ORDER BY created,id", (pid,))],
                    "documents": [dict(r) for r in conn.execute("SELECT id,filename,sha256,created,length(content) AS bytes FROM documents WHERE project=? ORDER BY created", (pid,))],
                    "claims": [{"id": r["id"], **json.loads(r["payload"])} for r in conn.execute("SELECT * FROM claims WHERE project=? ORDER BY created", (pid,))],
                    "runs": [dict(r) for r in conn.execute("SELECT r.id,r.revision,r.sha256,r.created,a.id AS approval_id FROM runs r LEFT JOIN approvals a ON a.run=r.id WHERE r.project=? ORDER BY r.created DESC", (pid,))]}

    @app.post("/api/v1/projects/{pid}/offers", status_code=201)
    def create_offer(pid: str, data: OfferInput, user=Depends(actor)):
        return write_offer(pid, None, data, user)

    @app.put("/api/v1/projects/{pid}/offers/{oid}")
    def update_offer(pid: str, oid: str, data: OfferInput, user=Depends(actor)):
        return write_offer(pid, oid, data, user)

    def write_offer(pid, oid, data, user):
        role(user, "owner", "editor")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p = project(conn, pid, user)
            revision(p, data.revision)
            value = asdict(validated(model.Candidate, data.parameters, json.loads(p["payload"])["parameters"]["years"]))
            existing = conn.execute("SELECT id,payload FROM offers WHERE project=?", (pid,)).fetchall()
            if any(json.loads(r["payload"])["name"] == value["name"] and r["id"] != oid for r in existing):
                raise HTTPException(409, "Candidate names must be unique within a project")
            if oid:
                if not any(r["id"] == oid for r in existing): raise HTTPException(404, "Offer not found")
                conn.execute("UPDATE offers SET payload=? WHERE id=? AND project=?", (pack(value), oid, pid))
            else:
                if len(existing) >= 20: raise HTTPException(422, "Maximum 20 offers per project")
                oid = uid()
                conn.execute("INSERT INTO offers VALUES(?,?,?,?)", (oid, pid, pack(value), now()))
            bump(conn, pid)
            audit(conn, user, "offer.saved", oid)
        return {"id": oid}

    @app.post("/api/v1/projects/{pid}/documents", status_code=201)
    def upload(pid: str, data: DocumentInput, user=Depends(actor)):
        role(user, "owner", "editor")
        ext = Path(data.filename).suffix.lower()
        if ext not in (".pdf", ".csv", ".txt", ".json") or "/" in data.filename or "\\" in data.filename or any(ord(c)<32 for c in data.filename):
            raise HTTPException(422, "Use a plain PDF, CSV, TXT or JSON filename")
        try: content = base64.b64decode(data.content_base64, validate=True)
        except ValueError: raise HTTPException(422, "Invalid base64 content")
        if not 0 < len(content) <= 5_000_000: raise HTTPException(422, "Document must be 1 byte to 5 MB")
        if ext == ".pdf" and not content.startswith(b"%PDF-"): raise HTTPException(422, "Invalid PDF header")
        if ext != ".pdf":
            try: content.decode("utf-8")
            except UnicodeDecodeError: raise HTTPException(422, "Text documents must use UTF-8")
        with db() as conn:
            project(conn, pid, user)
            did = uid()
            conn.execute("INSERT INTO documents VALUES(?,?,?,?,?,?)", (did, pid, data.filename, hashlib.sha256(content).hexdigest(), content, now()))
            bump(conn, pid)
            audit(conn, user, "document.uploaded", did, {"filename": data.filename})
        return {"id": did}

    @app.get("/api/v1/projects/{pid}/documents/{did}")
    def download(pid: str, did: str, user=Depends(actor)):
        with db() as conn:
            project(conn, pid, user)
            row = conn.execute("SELECT * FROM documents WHERE id=? AND project=?", (did, pid)).fetchone()
            if not row: raise HTTPException(404, "Document not found")
        return Response(bytes(row["content"]), media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="source-document' + Path(row["filename"]).suffix.lower() + '"'})

    @app.post("/api/v1/projects/{pid}/claims", status_code=201)
    def claim(pid: str, data: ClaimInput, user=Depends(actor)):
        role(user, "owner", "editor")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            project(conn, pid, user)
            offer = conn.execute("SELECT payload FROM offers WHERE id=? AND project=?", (data.candidate_id, pid)).fetchone()
            doc = conn.execute("SELECT filename,sha256 FROM documents WHERE id=? AND project=?", (data.document_id, pid)).fetchone()
            if not offer or not doc: raise HTTPException(404, "Candidate or source document not found in this project")
            c = json.loads(offer[0])
            payload = {**data.model_dump(), "candidate": c["name"], "model": c["model"], "bom": c["bom"],
                       "value": str(c[data.field]), "source": doc["filename"], "source_sha256": doc["sha256"],
                       "status": "Unreviewed", "reviewer": "", "date": ""}
            cid = uid()
            conn.execute("INSERT INTO claims VALUES(?,?,?,?)", (cid, pid, pack(payload), now()))
            bump(conn, pid)
            audit(conn, user, "claim.created", cid)
        return {"id": cid}

    @app.post("/api/v1/projects/{pid}/claims/{cid}/review")
    def review(pid: str, cid: str, data: ReviewInput, user=Depends(actor)):
        role(user, "owner", "reviewer")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            project(conn, pid, user)
            row = conn.execute("SELECT payload FROM claims WHERE id=? AND project=?", (cid, pid)).fetchone()
            if not row: raise HTTPException(404, "Claim not found")
            payload = {**json.loads(row[0]), "status": data.status, "reviewer": user["id"], "date": now(), "review_comment": data.comment}
            conn.execute("UPDATE claims SET payload=? WHERE id=?", (pack(payload), cid))
            bump(conn, pid)
            audit(conn, user, "claim.reviewed", cid, {"status": data.status, "comment": data.comment})
        return {"ok": True}

    @app.post("/api/v1/projects/{pid}/runs", status_code=201)
    def run(pid: str, data: ScenarioInput, user=Depends(actor)):
        role(user, "owner", "editor")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p = project(conn, pid, user)
            revision(p, data.revision)
            site = json.loads(p["payload"])
            offers = [validated(model.Candidate, json.loads(r[0]), site["parameters"]["years"]) for r in conn.execute("SELECT payload FROM offers WHERE project=? ORDER BY created,id", (pid,))]
            claims = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM claims WHERE project=? ORDER BY created", (pid,))]
            try: result = model.compare(model.Project(**site["parameters"]), offers, claims, data.degradation_add, data.yield_haircut)
            except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc))
            result["site"] = {k:v for k,v in site.items() if k != "parameters"}
            raw, rid = pack(result), uid()
            conn.execute("INSERT INTO runs(id,project,revision,payload,sha256,created) VALUES(?,?,?,?,?,?)", (rid, pid, p["revision"], raw, digest(raw), now()))
            audit(conn, user, "run.completed", rid, {"model": model.MODEL_VERSION, "revision": p["revision"], "sha256": digest(raw)})
        return {"id": rid, "result": result}

    @app.get("/api/v1/projects/{pid}/runs/{rid}")
    def result(pid: str, rid: str, user=Depends(actor)):
        with db() as conn:
            p = project(conn, pid, user)
            row = conn.execute("SELECT * FROM runs WHERE id=? AND project=?", (rid, pid)).fetchone()
            if not row: raise HTTPException(404, "Run not found")
            if digest(row["payload"]) != row["sha256"]: raise HTTPException(409, "Result integrity check failed")
            approval = conn.execute("SELECT a.*,u.name AS reviewer_name FROM approvals a JOIN users u ON u.id=a.actor WHERE a.run=?", (rid,)).fetchone()
            return {"id": rid, "revision": row["revision"], "current_revision": p["revision"], "sha256": row["sha256"], "result": json.loads(row["payload"]), "approval": dict(approval) if approval else None}

    @app.post("/api/v1/projects/{pid}/runs/{rid}/approve", status_code=201)
    def approve(pid: str, rid: str, data: ReviewInput, user=Depends(actor)):
        role(user, "owner", "reviewer")
        if data.status != "Reviewed": raise HTTPException(422, "Approval requires Reviewed status")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p = project(conn, pid, user)
            row = conn.execute("SELECT * FROM runs WHERE id=? AND project=?", (rid, pid)).fetchone()
            if not row: raise HTTPException(404, "Run not found")
            revision(p, row["revision"])
            if digest(row["payload"]) != row["sha256"]: raise HTTPException(409, "Result integrity check failed")
            output = json.loads(row["payload"])
            if any(r["evidence_gaps"] for r in output["results"]): raise HTTPException(409, "Resolve evidence gaps and create a new run before approval")
            if conn.execute("SELECT 1 FROM approvals WHERE run=?", (rid,)).fetchone(): raise HTTPException(409, "Run already approved")
            ident = uid()
            conn.execute("INSERT INTO approvals VALUES(?,?,?,?,?)", (ident, rid, user["id"], data.comment, now()))
            audit(conn, user, "run.approved", rid, {"comment": data.comment, "sha256": row["sha256"]})
        return {"id": ident}

    @app.get("/api/v1/audit")
    def events(user=Depends(actor)):
        with db() as conn:
            return [dict(r) for r in conn.execute("SELECT a.*,u.name AS actor_name FROM audit a JOIN users u ON u.id=a.actor WHERE a.org=? ORDER BY a.id DESC LIMIT 200", (user["org"],))]

    @app.get('/api/v1/physics/catalog')
    def module_catalog(user=Depends(actor)):
        return physics_catalog()

    def physics_folder(user,pid,rid):
        return path.parent/'physics'/user['org']/pid/rid

    @app.post('/api/v1/projects/{pid}/physics',status_code=201)
    def calculate_physics(pid:str,data:PhysicsInput,user=Depends(actor)):
        role(user,'owner','editor')
        with db() as conn:
            p=project(conn,pid,user)
            revision(p,data.revision)
            saved=json.loads(p['payload'])
        if len(set(data.module_ids))!=len(data.module_ids) or not set(data.module_ids).issubset({m['module_id'] for m in physics_catalog()}):
            raise HTTPException(422,'Choose distinct exact catalog modules')
        if data.weather_source=='riyadh_reference' and (abs(saved['latitude']-24.7136)>.001 or abs(saved['longitude']-46.6753)>.001):
            raise HTTPException(422,'Recorded Riyadh weather requires project coordinates 24.7136, 46.6753. Edit the site or choose Live NASA.')
        rid=uid()
        payload={'project':saved['parameters'],'latitude':saved['latitude'],'longitude':saved['longitude'],
                 'configuration':data.model_dump(), 'project_revision':p['revision']}
        try: result=run_physics(payload,physics_folder(user,pid,rid))
        except (ValueError,OSError) as exc:
            with db() as conn: audit(conn,user,'physics.failed',rid,{'project':pid,'reason':str(exc)})
            raise HTTPException(422,str(exc))
        with db() as conn:
            conn.execute('INSERT INTO physics_runs VALUES(?,?,?,?)',(rid,pid,p['revision'],now()))
            audit(conn,user,'physics.completed',rid,{'project':pid,'revision':p['revision'],'physical_run':result['physics']['run_id']})
        return {'id':rid,'revision':p['revision'],'result':result}

    @app.get('/api/v1/projects/{pid}/physics')
    def physics_history(pid:str,user=Depends(actor)):
        with db() as conn:
            project(conn,pid,user)
            return [dict(r) for r in conn.execute('SELECT * FROM physics_runs WHERE project=? ORDER BY created DESC',(pid,))]

    @app.get('/api/v1/projects/{pid}/physics/{rid}')
    def physics_result(pid:str,rid:str,user=Depends(actor)):
        with db() as conn:
            p=project(conn,pid,user)
            r=conn.execute('SELECT * FROM physics_runs WHERE id=? AND project=?',(rid,pid)).fetchone()
            if not r: raise HTTPException(404,'Physics run not found')
        try: result=read_physics(physics_folder(user,pid,rid))
        except (ValueError,OSError) as exc: raise HTTPException(409,'Physics artifact integrity verification failed') from exc
        return {'id':rid,'revision':r['revision'],'current_revision':p['revision'],'result':result}

    @app.get('/api/v1/projects/{pid}/physics/{rid}/download')
    def physics_download(pid:str,rid:str,user=Depends(actor)):
        with db() as conn:
            project(conn,pid,user)
            if not conn.execute('SELECT 1 FROM physics_runs WHERE id=? AND project=?',(rid,pid)).fetchone():
                raise HTTPException(404,'Physics run not found')
        try: payload=package_physics(physics_folder(user,pid,rid))
        except (ValueError,OSError) as exc: raise HTTPException(409,'Physics artifact integrity verification failed') from exc
        return Response(payload,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="Solaryn-Physics-'+rid+'.zip"'})

    @app.get("/")
    def index(): return FileResponse(ROOT / "web/index.html")
    @app.get("/api/docs")
    def docs(): return FileResponse(ROOT / "web/api.html")
    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
    return app
