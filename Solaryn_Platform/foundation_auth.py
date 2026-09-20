"""Admin-only boundary for the public research prototype. No science changes."""
from contextlib import closing
import hashlib
import hmac
import os
import secrets
import sqlite3
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

COOKIE = "solaryn_admin"
SESSION_SECONDS = 8 * 60 * 60


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${value}"


def password_matches(password, encoded):
    try:
        algorithm, salt, _ = encoded.split("$")
        return algorithm == "scrypt" and hmac.compare_digest(password_hash(password, salt), encoded)
    except (ValueError, TypeError):
        return False


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


def install_admin_auth(app, db_path):
    username = os.environ.get("SOLARYN_ADMIN_USERNAME", "admin")
    encoded = os.environ.get("SOLARYN_ADMIN_PASSWORD_HASH", "")
    # Rotating credentials invalidates all older sessions, including persisted ones.
    credential_version = hashlib.sha256((username + encoded).encode()).hexdigest()
    dummy_hash = password_hash(secrets.token_urlsafe(32))
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS admin_sessions (token_hash TEXT PRIMARY KEY, expires REAL NOT NULL, credential_version TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS admin_attempts (client TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at REAL NOT NULL)")
        db.commit()

    def token_hash(request):
        return hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()

    def is_admin(request):
        if not encoded:
            return False
        with closing(sqlite3.connect(db_path)) as db:
            row = db.execute("SELECT expires, credential_version FROM admin_sessions WHERE token_hash=?", (token_hash(request),)).fetchone()
        return bool(row and row[0] > time.time() and hmac.compare_digest(row[1], credential_version))

    def public_path(path):
        return path in {"/", "/login", "/api/v1/health", "/api/v1/auth/session", "/api/v1/auth/login", "/api/v1/auth/logout"} or path.startswith(("/assets/", "/brand/"))

    @app.middleware("http")
    async def admin_boundary(request: Request, call_next):
        path = request.url.path
        # Reject cross-site cookie writes, including login and logout.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin != str(request.base_url).rstrip("/")):
                return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403, headers={"Cache-Control": "no-store"})
        request.state.admin = is_admin(request)
        if not public_path(path) and not request.state.admin:
            if path.startswith("/api/") or path == "/openapi.json":
                return JSONResponse({"detail": "Admin login required"}, status_code=401, headers={"Cache-Control": "no-store"})
            return RedirectResponse("/login", status_code=303, headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        if not path.startswith(("/assets/", "/brand/")):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/api/v1/auth/session", include_in_schema=False)
    def session(request: Request):
        return {"authenticated": request.state.admin, "profile": {"username": username, "name": "Administrator", "role": "admin"} if request.state.admin else None}

    @app.post("/api/v1/auth/login", include_in_schema=False)
    def login(data: Credentials, request: Request):
        if not encoded:
            raise HTTPException(503, "Admin access has not been configured")
        client = hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest()
        now = time.time()
        # A short transaction also makes concurrent attempts count atomically.
        with closing(sqlite3.connect(db_path)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM admin_attempts WHERE reset_at<=?", (now,))
            row = db.execute("SELECT count FROM admin_attempts WHERE client=?", (client,)).fetchone()
            if row and row[0] >= 10:
                raise HTTPException(429, "Too many login attempts. Try again in 15 minutes.")
            db.execute("INSERT INTO admin_attempts VALUES (?,1,?) ON CONFLICT(client) DO UPDATE SET count=count+1", (client, now + 900))
            db.commit()
        valid_password = password_matches(data.password, encoded if data.username == username else dummy_hash)
        if not valid_password or not hmac.compare_digest(data.username.encode(), username.encode()):
            raise HTTPException(401, "Invalid username or password")
        token = secrets.token_urlsafe(32)
        with closing(sqlite3.connect(db_path)) as db:
            db.execute("DELETE FROM admin_attempts WHERE client=?", (client,))
            db.execute("DELETE FROM admin_sessions WHERE expires<=? OR token_hash=?", (now, token_hash(request)))
            db.execute("INSERT INTO admin_sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), now + SESSION_SECONDS, credential_version))
            db.commit()
        response = JSONResponse({"authenticated": True, "profile": {"username": username, "name": "Administrator", "role": "admin"}})
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=request.url.scheme == "https" or os.environ.get("RENDER") == "true", samesite="strict", path="/")
        return response

    @app.post("/api/v1/auth/logout", include_in_schema=False)
    def logout(request: Request):
        with closing(sqlite3.connect(db_path)) as db:
            db.execute("DELETE FROM admin_sessions WHERE token_hash=?", (token_hash(request),))
            db.commit()
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/")
        return response
