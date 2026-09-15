# Solaryn Platform

## Physics integration — current release

Open a project → **Physics & validation**. The platform now runs the original hourly physics engine and freshly reproduces its measured SUPSI electrical benchmark. Hourly DC power feeds an explicit AC conversion/clipping approximation and then lifecycle economics when module prices are supplied. See [PHYSICS_INTEGRATION.md](PHYSICS_INTEGRATION.md) for the active calculation chain, validation scope, source exports and remaining limits. The manual-yield workflow described below is retained separately.

For the offline reference, set project coordinates to **24.7136, 46.6753**, select Recorded Riyadh, choose 2–5 modules, and click **Run physics & measured validation**. The three default modules reproduce the established DC benchmark. Add a price for every selected module to enable exploratory economics. A complete result is not a scientifically validated procurement winner.

The full sibling `Solaryn_Pilot/src`, required data and validation source directories are now runtime dependencies. The corrected physics delivery includes them; the earlier small procurement-only ZIP does not. Install the updated requirements before using this release. An analysis download includes hourly outputs and measured-validation sources with integrity manifests.

The first working web-platform increment around the existing deterministic procurement model. It has a FastAPI backend, a same-origin responsive HTML/CSS/JavaScript client, and persistent SQLite storage. The model remains in `../Solaryn_Pilot/src/procurement_model.py`; it is loaded directly so older copies of `src` cannot shadow it.

## Open or start

Local URL: **http://127.0.0.1:8765/**. The development server is bound to loopback only.

From the parent delivery folder, using the already installed dependencies:

```powershell
.venv\Scripts\python.exe Solaryn_Platform\run.py
```

Create your organization on the welcome screen. Existing users can switch to Sign in. There is no automatically created administrator or default production password. An isolated `Synthetic QA workspace` was created for browser validation; it contains synthetic examples only and is not shared with newly registered organizations.

For a fresh installation using Python 3.12, from the parent delivery folder:

```powershell
python -m venv Solaryn_Platform\.venv
Solaryn_Platform\.venv\Scripts\python.exe -m pip install -r Solaryn_Platform\requirements-lock.txt
Solaryn_Platform\.venv\Scripts\python.exe Solaryn_Platform\run.py
```

The launcher also supports this delivery's isolated `.packages` dependency directory. When that directory is present it takes precedence over the environment. Keep the sibling `Solaryn_Pilot` folder because it contains the scientific model. No build step, Node runtime, CDN or external font service is required for the browser client.

## Implemented workflow

1. Register an organization and owner account, or sign in.
2. Create projects with site coordinates, climate tags and financial assumptions.
3. Add or edit up to 20 exact module offers with BOM, net AC yield source and lifecycle assumptions.
4. Store PDF, UTF-8 CSV/TXT/JSON source files, up to 5 MB each. Files are hashed and downloaded as attachments; they are not executed or embedded.
5. Bind claims to a stored source, page/section, excerpt, exact candidate, model, BOM, field and current value.
6. An authenticated owner or reviewer reviews claims and records a comment.
7. An owner or editor runs a deterministic scenario. The backend saves the original inputs, evidence, model release, annual cash flows and result hash.
8. Compare NPV, LCOE, IRR, net AC energy and justified module-price premiums. Export the complete result JSON.
9. An owner or reviewer approves a snapshot only when the minimum matching evidence checklist is complete and the project revision has not changed.
10. Reopen historical decisions and inspect organization activity. New edits never rewrite old result payloads through the API.

The first offer entered is the price-premium baseline. Equal DC capacity and consistent imported net AC boundaries are required. All money is constant EUR, pre-tax and unlevered. Downside controls are deterministic adjustments, not statistical P50/P90. See [the existing model documentation](../Solaryn_Pilot/docs/PROCUREMENT_MODEL.md).

## Roles and access

| Role | Permissions |
|---|---|
| Owner | Organization team provisioning, project editing, uploads, calculations, evidence reviews and approvals |
| Editor | Project and offer editing, uploads, claim creation and calculations |
| Reviewer | Read project records, review claims and approve eligible snapshots |
| Viewer | Read and download organization project data |

Each account belongs to one organization in this increment. Owners create team accounts locally; no email is sent. Users within an organization can read every project in that organization. Per-project membership, team invitations, role changes, account removal, password recovery, MFA and OIDC/SSO are not implemented. Ownership does not imply an independent engineering qualification, and an owner may review their own work; four-eyes approval is not yet enforced.

Authentication uses salted scrypt password hashes and eight-hour random sessions. Only hashes of session tokens are stored. Cookies are HttpOnly and SameSite=Strict, authenticated writes require a CSRF token, and browser cross-origin writes are rejected. Login attempts have a persistent per-account throttle. Project/resource queries are scoped to the authenticated organization; IDs supplied by clients never grant access.

`SOLARYN_SECURE_COOKIES=1` enables Secure cookies for a future HTTPS deployment. It is off for local HTTP development. `SOLARYN_DB` overrides the SQLite path. The launcher intentionally exposes no public listener.

## API and code

- `/api/docs`: self-contained endpoint reference.
- `/openapi.json`: generated OpenAPI contract.
- `/api/v1/health`: service and model version.
- `server.py`: API, authorization, transactional persistence and model adapter.
- `web/`: browser client, styling and offline API reference.
- `tests/test_platform.py`: API integration and access-control tests.

Project/offer updates and run submissions use optimistic revision checks. A stale revision returns HTTP 409. Resource queries outside the caller's organization return 404. Invalid scientific inputs return 422. Sources and result hashes are included in saved records; they are not digital signatures.

## Test

From `Solaryn_Platform`, using the parent environment:

```powershell
..\.venv\Scripts\python.exe -m pytest tests -q
node --check web\app.js
```

Node is optional for syntax checks only. Windows test isolation may require a fresh `--basetemp` under this folder and access to `.packages`. Tests use temporary databases and do not depend on the live server or the user's account.

## Persistence and operating limits

Database: `workspace/platform.sqlite3`, with WAL enabled and foreign keys enforced. Schema version 1 is created on startup. Application mutations and their audit entries commit together. Claim reviews update the active claim state; prior review events remain in the audit log, and saved runs retain their original evidence. Audit entries are append-only through the API but can be changed by someone with direct database access.

Uploads are stored as BLOBs for this first local increment. Calculations run synchronously and take a SQLite write transaction so the input snapshot cannot race with edits. This is suitable for short local lifecycle comparisons, not a concurrent production workload or long hourly weather simulation.

Back up with SQLite's online backup API or stop the service before copying the database. Do not copy only the main file from an active WAL database. The platform has no implemented restore UI, automated backups or production retention policy.

## Remaining production work

This is an authenticated local platform foundation, **not a production-ready hosted SaaS**. Next steps are documented in [ROADMAP.md](ROADMAP.md): PostgreSQL migrations and tenant policies, private object storage and malware scanning, external identity and account lifecycle, durable job execution, deployment configuration, operational monitoring, PDF/Excel reports and independently validated scientific assumptions. There is no AI/OCR extraction, direct PVsyst/SAM parser, billing, live climate ingestion or cloud deployment in this increment.
