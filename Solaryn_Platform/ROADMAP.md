# Platform build sequence

## Increment 1 — implemented

Authenticated organization workspaces, server-side role checks, projects and offers, source files, cited manual evidence, reviewer identity, deterministic lifecycle comparisons, immutable-through-API run snapshots, revision-bound human approval, organization audit events and a responsive web client.

## Increment 2 — persistence and account lifecycle

- Replace SQLite queries with a repository layer and PostgreSQL migrations. Use organization keys on every tenant entity and enforce row-level policies in addition to application authorization.
- Add per-project memberships and invitation acceptance, session revocation, account deactivation, password reset, verified email and OIDC/SSO. Enforce separation between preparer and approver where required.
- Replace document BLOBs with private object storage. Add organization quotas, malware scanning, validated media inspection and retention controls before processing uploads.
- Add pagination, idempotency keys, transactional revision numbers and indexed entity audit history. Do not add deletion without recovery/retention design.

Acceptance: migrate representative projects without changing model results; prove cross-tenant denial at database and API layers; exercise member removal/session revocation and backup restoration.

## Increment 3 — engineering document workflow

- Add asynchronous extraction jobs with explicit source page and excerpt; extracted values stay unreviewed.
- Build candidate identity reconciliation for factory, BOM revisions and certificate scope.
- Normalize documented PVsyst/SAM AC output formats with explicit weather, geometry, DC/AC and loss boundaries. Preserve original source files and parsing versions.
- Extend the minimum evidence checklist to a governed project-specific review policy. Display contradictory claims and unresolved evidence, not a universal supplier score.
- Add deterministic procurement reports, source register and annual cash-flow exports in PDF/Excel.

Acceptance: reproduce a real two-to-five-offer comparison from its sources, independently review every extracted claim, and prevent stale or contradictory evidence from passing the approval policy.

## Increment 4 — cloud operations and pilot release

- Containerize API/client and separate durable workers; add queued job status, retries and cancellation.
- Configure HTTPS, secure cookies, trusted origins/hosts, secrets management, distributed throttling, dependency scanning and observability.
- Deploy managed PostgreSQL/private storage and verify disaster recovery. Add quotas, abuse prevention and audit export/retention.
- Validate electrical/yield boundaries and lifetime assumptions with project-specific engineering evidence. Passing software tests is not scientific field validation.
- Run a controlled customer pilot with documented service limits and support workflow.

Acceptance: deployment smoke tests, restore drill, organization isolation tests, concurrency testing, scientific review and a full real-project user acceptance run. No cloud provider or external account was selected or provisioned in increment 1.
