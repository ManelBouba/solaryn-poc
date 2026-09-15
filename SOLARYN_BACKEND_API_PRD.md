# SOLARYN Backend and API Product Requirements Document

**Date:** 6 September 2026  
**Status:** Architecture and implementation specification  
**API namespace:** `/api/v1`

## Executive summary

The SOLARYN backend must turn project, location, module evidence and supplier-offer inputs into reproducible climate-aware comparison runs. It must preserve the current validated scientific engines and decision gates, isolate tenants, execute long calculations asynchronously and provide immutable provenance for every result and report.

The API must serve the Google Stitch-derived frontend without embedding scientific logic in exported UI code. The first production target may run on Replit, but the service must use portable interfaces: PostgreSQL-compatible storage, S3-compatible object storage, environment-based configuration, standard OIDC authentication, versioned HTTP contracts and independently testable job workers.

## Goals and success metrics

### Goals

1. Provide a secure, tenant-isolated API for projects, sites, candidates, offers, runs, results, reports and approvals.
2. Preserve fail-closed evidence rules and immutable scientific provenance.
3. Decouple interactive requests from NASA/PVGIS access and hourly physics jobs.
4. Make failures recoverable and observable without exposing secrets or stack traces.
5. Enable migration from the current CSV/Streamlit PoC to Replit without changing validated numerical behavior.

### Success metrics

| Metric | Target |
|---|---:|
| API availability | ≥99.9% monthly, excluding declared external-provider outage |
| Read endpoint latency | p95 ≤300 ms, excluding report/object downloads |
| Write endpoint latency | p95 ≤500 ms before asynchronous processing |
| Run submission acknowledgement | ≤1 second |
| Duplicate runs for one idempotency key | 0 |
| Cross-tenant data access incidents | 0 |
| Reproducible frozen benchmark hash | 100% match in release gate |
| Unhandled 5xx rate | <0.1% of requests |
| Audit coverage for privileged mutations | 100% |
| Successful valid offer imports | ≥99.5% |

## Stakeholders

- Product and UX: contract semantics and state requirements.
- Scientific engineering: numerical engines, gates, provenance and benchmark approval.
- Backend engineering: API, persistence, workers and integrations.
- Platform/DevOps: Replit environments, secrets, database, storage and monitoring.
- Security/compliance: tenant isolation, RBAC, audit and retention.
- QA/validation: contract, integration, security and numerical-regression testing.
- EPC/procurement users: workflow validation and output interpretation.

## Assumptions and constraints

- Existing Python engines in `src/` are the initial calculation implementation.
- Physics constants, irradiance, spectral, temperature, degradation assumptions, ranking logic and decision thresholds are controlled scientific configuration—not normal API-editable fields.
- NASA POWER and PVGIS are external dependencies. Their success must never be inferred from offline tests.
- OpenStreetMap public tiles are a frontend map dependency, not an analytical climate source.
- At least two successful candidate simulations are required for a ranked comparison.
- Missing baseline price disables economics without disabling energy comparison.
- A non-eligible evidence state prevents a robust decision claim.
- The system must record USD/W initially. Future currencies require `currency`, `fxRate`, `fxSource` and `fxTimestamp`; the backend must never invent a rate.
- Large hourly arrays and generated reports belong in object storage, not ordinary JSON database columns.

## Roles and authorization

| Role | Capabilities |
|---|---|
| Viewer | Read assigned projects, runs and reports |
| Project editor | Create/edit drafts, sites and offers; submit runs |
| Commercial editor | Edit quotes and baselines; view economics |
| Research user | Run research screening; cannot approve procurement decisions |
| Reviewer | Add review findings and request revisions |
| Approver | Approve/reject completed decision packages |
| Organization admin | Manage members, roles and organization settings |
| Platform admin | Operational support through audited, time-bound elevation only |

Authorization is evaluated from authenticated user, organization membership, project assignment, resource state and requested action. Client-supplied roles are ignored.

## Functional requirements and API endpoints

### Conventions

- Base path: `/api/v1`
- JSON uses camelCase; timestamps use ISO 8601 UTC.
- IDs are opaque UUIDv7 values.
- Mutating POST requests accept `Idempotency-Key`.
- List endpoints support `cursor`, `limit`, `sort` and documented filters.
- Responses include `requestId`; analytical resources include `inputHash`, `engineVersion` and `createdAt`.

### Authentication and organization

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/me` | Current user, memberships and effective permissions |
| GET | `/organizations/{organizationId}` | Organization settings |
| GET | `/organizations/{organizationId}/members` | List members |
| POST | `/organizations/{organizationId}/invitations` | Invite a member |
| PATCH | `/organizations/{organizationId}/members/{userId}` | Change role/status |

### Projects and sites

| Method | Endpoint | Required/request fields | Result |
|---|---|---|---|
| GET | `/projects` | `organizationId`, filters | Paginated accessible projects |
| POST | `/projects` | `organizationId`, `name`, `segment`, `capacityMwp`, `referenceYear` | Draft project |
| GET | `/projects/{projectId}` | — | Project and current status |
| PATCH | `/projects/{projectId}` | Mutable draft fields, `version` | Updated project |
| DELETE | `/projects/{projectId}` | `version` | Soft-delete draft only |
| POST | `/projects/{projectId}/sites` | `name`, `latitude`, `longitude`, `tiltDeg`, `azimuthDeg` | Site |
| PATCH | `/projects/{projectId}/sites/{siteId}` | Mutable site fields, `version` | Updated site |

**Create project request**

```http
POST /api/v1/projects
Authorization: Bearer <token>
Idempotency-Key: 018f-project-create
Content-Type: application/json

{
  "organizationId": "0198f81f-34d0-7000-9e81-55f67016ee10",
  "name": "Riyadh module comparison",
  "segment": "utility",
  "capacityMwp": 100,
  "referenceYear": 2020
}
```

### Module catalog, evidence and offers

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/module-candidates` | Search approved catalog by segment/manufacturer/evidence |
| GET | `/module-candidates/{moduleId}` | Technical fields and evidence summary |
| POST | `/projects/{projectId}/offer-batches` | Create upload batch metadata |
| POST | `/projects/{projectId}/offer-batches/{batchId}/file` | Upload canonical CSV using multipart form data |
| GET | `/projects/{projectId}/offer-batches/{batchId}` | Parsing status and row-level validation |
| GET | `/projects/{projectId}/offers` | Normalized project offers |
| PATCH | `/projects/{projectId}/offers/{offerId}` | Quote, supplier metadata and commercial validity |
| GET | `/templates/module-offers.csv` | Versioned canonical CSV template |

**Offer patch request**

```json
{
  "quote": {"amountPerWatt": 0.184, "currency": "USD"},
  "supplierName": "Example supplier",
  "quoteReference": "Q-2026-1048",
  "validUntil": "2026-10-31",
  "version": 3
}
```

Required physics fields follow the canonical schema in `src/module_offer_io.py`. Unknown fields may be retained as namespaced metadata but cannot influence calculations unless added through a reviewed API/schema version.

### Climate resources and analysis runs

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/projects/{projectId}/climate-checks` | Queue NASA/PVGIS resource check |
| GET | `/climate-checks/{checkId}` | Status, provider provenance and discrepancy |
| POST | `/projects/{projectId}/analysis-runs` | Freeze inputs and queue comparison |
| GET | `/analysis-runs/{runId}` | State, progress and immutable provenance |
| POST | `/analysis-runs/{runId}/cancel` | Request cancellation while queued/running |
| GET | `/analysis-runs/{runId}/results` | Decision summary and candidate results |
| GET | `/analysis-runs/{runId}/hourly-data` | Signed URL or streamed CSV/Parquet export |

**Submit run request**

```http
POST /api/v1/projects/0198f-project/analysis-runs
Authorization: Bearer <token>
Idempotency-Key: 018f-riyadh-run-001
Content-Type: application/json

{
  "siteId": "0198f-site",
  "offerIds": ["0198f-offer-a", "0198f-offer-b", "0198f-offer-c"],
  "baselineOfferId": "0198f-offer-a",
  "referenceYear": 2020,
  "systemSizeMwp": 100,
  "acknowledgedInputVersion": 7
}
```

**Accepted response**

```json
{
  "runId": "0198f-run",
  "state": "queued",
  "inputHash": "sha256:…",
  "statusUrl": "/api/v1/analysis-runs/0198f-run",
  "requestId": "req_01"
}
```

Run states: `queued`, `fetching_climate`, `validating_inputs`, `simulating`, `ranking`, `reporting`, `completed`, `failed`, `cancelled`. Progress is monotonic and contains a user-safe message plus optional diagnostic code.

### Results, reports and approvals

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/analysis-runs/{runId}/results` | Commercial state, modeled leader and evidence gates |
| POST | `/analysis-runs/{runId}/reports` | Generate versioned HTML/PDF/CSV package |
| GET | `/reports/{reportId}` | Report metadata and signed download links |
| POST | `/analysis-runs/{runId}/reviews` | Submit review finding or recommendation |
| POST | `/analysis-runs/{runId}/approvals` | Approve, reject or request revision |
| GET | `/analysis-runs/{runId}/audit-events` | Immutable project/run event history |

The result schema must separate:

```json
{
  "decisionStatus": "no_robust_winner",
  "maximumJustifiedPremium": null,
  "premiumUnavailableReason": "baseline_quote_missing",
  "provisionalModeledLeader": {
    "moduleId": "MOD_TOPCON_JINKO_JKM575N_72HL4_V",
    "annualSpecificEnergyKwhKwp": 2073.4,
    "leadOverSecondPct": 1.2103052741519815
  },
  "requiredDecisionGapPct": 2.0,
  "decisionIneligibleModuleIds": ["MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530"],
  "validationGates": [{"code": "cross_technology", "status": "pending"}]
}
```

### Research screening

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/research-screenings` | Queue heuristic technology/material screening |
| GET | `/research-screenings/{screeningId}` | Retrieve ranked hypotheses and assumptions |
| POST | `/research-screenings/{screeningId}/exports` | Generate watermarked research export |

Every research response includes `commercialUseAllowed: false` and `classification: "research_hypothesis"`. The API rejects approval creation for a research-screening resource.

## Data models

```text
Organization 1──* Membership *──1 User
Organization 1──* Project 1──* Site
Project      1──* OfferBatch 1──* ModuleOffer *──1 ModuleCandidate
ModuleCandidate 1──* EvidenceArtifact
Project      1──* AnalysisRun 1──* CandidateResult
AnalysisRun  1──1 DecisionSummary
AnalysisRun  1──* ValidationGate
AnalysisRun  1──* Report
AnalysisRun  1──* Review
AnalysisRun  1──* Approval
Organization 1──* AuditEvent
ResearchScreening 1──* ResearchCandidateResult
```

### Core project schema

```json
{
  "$id": "Project",
  "type": "object",
  "required": ["id", "organizationId", "name", "segment", "capacityMwp", "referenceYear", "status", "version"],
  "properties": {
    "id": {"type": "string", "format": "uuid"},
    "organizationId": {"type": "string", "format": "uuid"},
    "name": {"type": "string", "minLength": 1, "maxLength": 160},
    "segment": {"enum": ["utility", "commercial", "residential", "research"]},
    "capacityMwp": {"type": "number", "exclusiveMinimum": 0},
    "referenceYear": {"type": "integer", "minimum": 1981},
    "status": {"enum": ["draft", "ready", "under_review", "approved", "archived"]},
    "version": {"type": "integer", "minimum": 1}
  }
}
```

### Immutability and provenance

An `AnalysisRun` stores or references an immutable input snapshot containing project/site parameters, normalized offers, evidence versions, climate-source identifiers, engine/lockfile version, candidate-set hash, input hash, timestamps and initiating user. Editing a project never modifies a completed run.

## Authentication and authorization

- Use OIDC/OAuth 2.1 Authorization Code Flow with PKCE.
- Prefer an established managed identity provider compatible with Replit; do not create password storage in application code.
- Use secure, HTTP-only, SameSite cookies for browser sessions or short-lived bearer tokens with refresh rotation.
- Require MFA for organization admins and approvers.
- Enforce RBAC and project scope on every query and object download.
- Signed report/data URLs expire in ≤15 minutes and are tenant-bound where supported.
- Service-to-service credentials use separate audiences and least-privilege scopes.

## Rate limits

| Operation | Default limit |
|---|---:|
| Read endpoints | 300 requests/user/minute |
| Project/offer mutations | 60 requests/user/minute |
| CSV imports | 10 requests/user/hour; 25 MB/file |
| Analysis submissions | 10 active runs/organization; 30/day/user |
| Report generation | 30/hour/organization |
| Authentication-sensitive actions | 10/minute/IP plus identity-provider controls |

Return `429` with `Retry-After`, stable error code and remaining-window metadata. Apply stricter adaptive limits for abuse without changing scientific results.

## Error handling

Use RFC 9457-style problem details:

```json
{
  "type": "https://api.solaryn.example/problems/invalid-module-offer",
  "title": "Module offer validation failed",
  "status": 422,
  "code": "OFFER_REQUIRED_FIELD_MISSING",
  "detail": "Two rows require physics fields.",
  "fieldErrors": [{"row": 3, "field": "pmaxW", "message": "Required"}],
  "requestId": "req_01"
}
```

- `400`: malformed request or unsupported query.
- `401`: missing/expired authentication.
- `403`: authenticated but not authorized.
- `404`: absent or inaccessible resource; avoid tenant enumeration.
- `409`: stale version, duplicate state transition or input changed after run preparation.
- `422`: valid JSON but domain/schema validation failure.
- `429`: rate limit.
- `502/503`: upstream NASA/PVGIS unavailable; include retryability and provider status.
- `500`: unexpected server error with safe message and request ID only.

Never substitute synthetic climate data unless the caller explicitly selects a separately labeled test mode that cannot produce an approvable result.

## Non-functional requirements

### Performance

- Use asynchronous workers for climate acquisition, simulation and report generation.
- Cache provider responses by normalized coordinates, year, parameters and provider version within licensing/usage constraints.
- Store hourly output in compressed Parquet; paginate/aggregate UI result APIs.
- Support 50 concurrent active analysis jobs at initial production target; scale workers horizontally.
- Complete the frozen Riyadh three-candidate run within 120 seconds at p95 under normal provider conditions.

### Reliability

- API availability target: 99.9%; durable job state and retry-safe workers.
- Retry transient upstream errors with capped exponential backoff and jitter.
- Use circuit breakers for NASA/PVGIS and expose provider status separately.
- Daily database backups; target RPO ≤24 hours and RTO ≤4 hours for initial release.
- Queue jobs at-least-once; make every stage idempotent to prevent duplicate reports/results.

### Security

- Encrypt transport using TLS 1.2+ and managed data stores at rest.
- Keep secrets exclusively in environment/secret management.
- Validate CSV type, size, encoding, formulas and paths; never execute uploaded content.
- Prevent SSRF by allowlisting external provider hosts and denying user-controlled URLs in workers.
- Parameterize database queries and scan dependencies/containers in CI.
- Log authentication, role, offer, run, report and approval mutations without logging secrets or full proprietary files.
- Define retention and deletion policies per organization; use soft deletion followed by scheduled purge.

### Observability

- Emit structured logs with request, organization, project and run correlation IDs.
- Track latency, error rate, queue depth, run duration, provider failures, cache hit rate and validation-gate distribution.
- Alert on elevated 5xx, cross-tenant authorization failures, queue backlog and frozen benchmark mismatch.

## API versioning

- Use `/api/v1` for major compatibility boundaries.
- Add fields backward-compatibly; clients ignore unknown response fields.
- Never silently change units, scientific semantics or enum meaning.
- Version upload templates and analytical input schemas separately.
- Announce breaking changes with ≥90 days overlap when security does not require immediate removal.
- Return `Deprecation` and `Sunset` headers for retired endpoints.
- Record the API schema version and engine version in every run.

## Testing and QA criteria

- Unit tests for validation, authorization, economics gates and state transitions.
- OpenAPI contract tests for every endpoint and error shape.
- Tenant-isolation tests across database queries, object URLs and audit endpoints.
- Property/fuzz tests for CSV normalization, numeric units and malformed files.
- Worker retry/idempotency tests and provider outage simulations.
- Load tests for 50 concurrent runs and 500 concurrent read sessions.
- OWASP API Top 10 security tests, dependency scans and secret scans.
- Frozen three-candidate and four-candidate Riyadh regression tests using recorded candidate-set SHA-256 values.
- Compare migrated API outputs with the current Python engine at strict field-specific tolerances.
- Maintain separate statuses for offline regression, live integration and external scientific validation.

## Deployment and Replit migration strategy

### Target topology

```text
Browser → Replit web service/API → PostgreSQL
                         ├──────→ Object storage
                         ├──────→ Durable job queue/worker
                         ├──────→ NASA POWER
                         └──────→ PVGIS
```

Do not execute long physics jobs only inside a request handler. If the selected Replit deployment cannot provide durable workers/queues, use an external managed queue/worker while keeping the public API on Replit.

### Migration phases

1. **Inventory and freeze:** tag the validated code, lock dependencies and record benchmark artifacts/hashes.
2. **Extract domain service:** wrap existing `src/` engines behind typed service functions without modifying calculations.
3. **Introduce persistence:** import CSV catalog/evidence data into normalized PostgreSQL tables while retaining source-file hashes.
4. **Build API:** implement OpenAPI contracts, OIDC, RBAC and tenant-scoped repositories.
5. **Add workers/storage:** queue runs; store input snapshots, hourly Parquet and reports.
6. **Connect Stitch frontend:** replace mocks with `/api/v1`; implement polling or server-sent job updates.
7. **Parallel validation:** run Streamlit and Replit paths against identical inputs; compare hashes and numerical outputs.
8. **Cutover:** migrate approved projects, enforce read-only legacy access, monitor and retain rollback package.

### Replit environment setup

- Pin Python and frontend runtime versions; install from exact lockfiles.
- Define separate development, staging and production deployments/databases.
- Store `DATABASE_URL`, object-storage credentials, OIDC settings and provider configuration in Replit Secrets.
- Run database migrations as an explicit release step, never automatically from every web process.
- Provide `/health/live` and `/health/ready`; readiness verifies database and queue, not external climate-provider health.
- Configure outbound HTTPS access to NASA/PVGIS and verify timeouts/DNS during staging.
- Persist no authoritative data on ephemeral local disk.

### Data migration

- Create an import manifest for each CSV with source SHA-256, schema version, row count and import timestamp.
- Preserve canonical `moduleId` values and candidate-set hashes.
- Reject duplicate IDs and quarantine invalid rows rather than coercing scientific fields.
- Reconcile row counts, key constraints and sample outputs after import.
- Keep original CSVs in immutable migration storage for audit/recovery.

## Milestones and timeline

| Milestone | Duration | Deliverable |
|---|---:|---|
| 1. Contracts and threat model | 1 week | Approved OpenAPI outline, RBAC and abuse cases |
| 2. Persistence and migration tooling | 2 weeks | Schema, migrations, CSV import/reconciliation |
| 3. Core project/offer APIs | 2 weeks | Authenticated CRUD and validation |
| 4. Job orchestration and engines | 2 weeks | Climate/run workers and immutable provenance |
| 5. Results/reports/approvals | 2 weeks | Decision schemas, exports and audit events |
| 6. Replit staging integration | 1 week | Deployed frontend/API and environment runbook |
| 7. Security, load and validation gate | 2 weeks | Release evidence and rollback plan |

Total target: 12 weeks with a backend team of two to three engineers plus scientific and QA support.

## Acceptance criteria

- OpenAPI specification documents every endpoint, field, unit, enum, permission and problem response.
- Tenant isolation passes automated and manual authorization tests.
- Completed runs contain immutable inputs, candidate-set hash, engine version and provenance.
- Missing quotes disable only economics; missing evidence prevents unsupported robust claims.
- Research endpoints cannot create procurement approvals and always label outputs as hypotheses.
- Long jobs survive web-process restart without duplication or loss of terminal state.
- NASA/PVGIS failure is explicit, retryable where appropriate and never replaced silently.
- Frozen Riyadh three- and four-candidate regressions match approved outputs/hashes.
- Valid offer uploads parse successfully; invalid rows return actionable row/field errors.
- Replit staging uses managed secrets, persistent database/object storage and a durable job mechanism.
- Stitch-derived frontend completes contract tests against the staging API.
- Security, performance, backup/restore and rollback tests pass before production cutover.
