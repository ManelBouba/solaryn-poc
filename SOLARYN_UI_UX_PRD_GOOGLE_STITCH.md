# SOLARYN UI/UX Product Requirements Document — Google Stitch

**Date:** 6 September 2026  
**Status:** Design specification for validation  
**Product:** SOLARYN Climate-Aware PV Intelligence

## Executive summary

SOLARYN is a professional decision-support platform for comparing photovoltaic module offers against project-specific climate, energy-yield, evidence and price inputs. The interface must help EPC engineers and procurement teams move from project setup to an auditable comparison without implying that an exploratory model result is measured, bankable or commercially approved.

Google Stitch will be used to generate and iterate the high-fidelity responsive interface, interactive journeys and frontend handoff. Stitch supports natural-language, image and code inputs, interactive prototypes, frontend export and portable `DESIGN.md` rules. It remains a design/prototyping layer: exported screens must be integrated with SOLARYN APIs, authorization, calculations, storage and validation logic before production use. Generated accessibility, responsiveness and component states require manual QA. Official references: [Stitch UI generation and export](https://blog.google/innovation-and-ai/products/io-2025-tools-to-try-globally/), [interactive prototypes](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-gemini-3/), and [portable DESIGN.md](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/).

## Goals and success metrics

### Goals

1. Let a qualified user create and configure a PV project in under five minutes.
2. Make the distinction between **EPC Module Comparison** and **Technology & Material Screening** unmistakable.
3. Present the commercial decision, maximum justified price premium and evidence limitations before secondary diagnostics.
4. Make every blocking state actionable: missing quote, invalid offer, unavailable climate service, incomplete evidence and insufficient candidates.
5. Produce a consistent design system that can move from Stitch to a Replit-hosted web application.

### Success metrics

| Metric | Target |
|---|---:|
| First project setup completion | ≥ 85% of usability-test participants |
| Median time from project creation to valid comparison submission | ≤ 5 minutes |
| Users correctly identifying research output as non-commercial | ≥ 95% |
| Users locating evidence limitations without assistance | ≥ 90% |
| CSV upload success for valid template | ≥ 98% |
| Critical task completion using keyboard only | 100% |
| WCAG 2.2 AA automated checks | 0 critical violations |
| Desktop page LCP after production integration | ≤ 2.5 seconds at p75 |
| Horizontal overflow at 1280×720 and 1440×900 | 0 pages |

## Stakeholders

- Product owner: owns scope, prioritization and go-to-market decisions.
- Scientific lead: approves scientific language, evidence gates and model boundaries.
- EPC engineer: validates project configuration and technical comparison usefulness.
- Procurement manager: validates quote, premium and supplier decision workflows.
- UX/UI lead: owns Stitch canvas, `DESIGN.md`, components and accessibility.
- Frontend engineering: converts approved designs into production components.
- Backend/data engineering: supplies API contracts, job states and provenance.
- Security/compliance: approves authentication, tenant isolation and audit requirements.
- QA/validation: maintains functional, visual, accessibility and scientific regression tests.

## Assumptions and constraints

### Product assumptions

- At least two successfully simulated candidates are required for a comparison.
- A real supplier quote is required to calculate switching economics or a maximum justified price premium.
- Technology-class spectral results remain sensitivity diagnostics and cannot determine a commercial decision.
- Evidence-ineligible candidates may be displayed transparently but cannot create a robust cross-technology winner.
- Climate/resource, c-Si off-STC, cross-technology, IEC measured, economics, historical EPC and bankability validation remain pending until external evidence is supplied.
- Currency conversion is not silently inferred. The first release supports USD/W; multi-currency requires an explicit exchange-rate service and dated rate.

### Google Stitch constraints

- Use Stitch for screen generation, visual iteration, prototype flows, design tokens and frontend handoff—not scientific computation or authoritative state.
- Import the supplied SOLARYN logo as a reference asset; do not redraw, recolor, stretch or crop the wordmark without brand approval.
- Import the existing SOLARYN screenshots as layout references, not as pixel-perfect implementation requirements.
- Generate desktop and tablet variants explicitly; do not assume generated reflow is production-ready.
- Create every loading, empty, warning, error, success, permission and stale-data state as a named frame.
- Treat exported code as a starting point. Engineering must replace mock data, connect APIs, add route guards, validate semantics and run accessibility tests.
- Export and version a project-level `DESIGN.md` so Replit implementation agents receive the same semantic token rules.

### Supplied design assets

- Primary logo: `app/assets/solaryn_logo.png` — approved transparent horizontal wordmark and “Climate-Aware PV Intelligence” tagline.
- Reference screenshots: `outputs/ui_screenshots/` — current Projects, EPC comparison, research screening and results states.
- Design decisions relying on these assets: sunrise-gold accent, deep navy typography, teal analytical actions, light sidebar, horizontal brand lockup and professional B2B dashboard density.

## Scope

### In scope

- Responsive authenticated application shell.
- Projects list, project creation and project overview.
- Nine-stage EPC comparison workflow.
- Supplier-offer template download, CSV upload, validation and quote editing.
- Climate job progress and recoverable external-service failure states.
- Decision summary, energy comparison, switching economics, climate, evidence and exports.
- Separate research-screening workspace with persistent non-commercial labeling.
- Reports, organization, roles, approvals, audit history and help shells.
- Desktop ≥1280 px and tablet 768–1279 px. Mobile supports read-only reports and urgent approvals only in the first production release.

### Out of scope

- Editing physics constants or decision thresholds in the UI.
- Hidden fallback climate data.
- Automatic bankability certification.
- Supplier marketplace, contracting or payment execution.
- Full mobile authoring of technical candidate matrices.

## Target users

| Persona | Primary need | Permission baseline |
|---|---|---|
| EPC engineer | Configure sites and compare technically compatible modules | Project editor |
| Procurement manager | Compare actual offers and price premiums | Commercial editor |
| Scientific reviewer | Inspect evidence, provenance and assumptions | Reviewer |
| Approver | Approve or reject a completed decision package | Approver |
| Organization administrator | Manage users, roles and defaults | Admin |
| Research analyst | Screen technologies without making commercial claims | Research user |

## Core user journeys and stories

### Journey A — create and validate a project

1. User selects **New project**.
2. User enters project name, country, segment, capacity, reference year and location.
3. System validates coordinates and displays data-source coverage.
4. User saves a draft and continues to module candidates.

**Stories**

- As an EPC engineer, I want required fields and units shown inline so I can configure a valid project without external instructions.
- As a reviewer, I want assumptions and their provenance visible so I can reproduce the run.
- As a user with a service failure, I want retry and diagnostic options without seeing a raw stack trace.

### Journey B — upload offers and run comparison

1. User downloads the canonical CSV template or starts from packaged candidates.
2. User uploads supplier offers.
3. System identifies row-level errors, compatible candidates, evidence readiness and missing quotes.
4. User selects at least two candidates and an economic baseline.
5. User starts an asynchronous comparison and may leave the page.

**Stories**

- As a procurement manager, I want editable quote cells isolated from locked technical evidence.
- As an engineer, I want incompatible candidates explained instead of silently removed.
- As a user, I want progress, cancellation and completion notification for a long calculation.

### Journey C — interpret and approve results

1. User sees the maximum justified premium or the exact reason it is unavailable.
2. User sees robust-decision status before the provisional modeled leader.
3. User compares annual/lifetime energy, evidence and economics.
4. User exports a versioned report or submits it for review.

**Stories**

- As an approver, I want an immutable run ID, input hash and evidence status.
- As a procurement manager, I want actual quote deltas separated from modeled energy.
- As a scientific reviewer, I want decision-ineligible candidates visibly marked throughout.

### Journey D — screen research hypotheses

- As a research analyst, I want to compare emerging technologies using explicit heuristic weights.
- As any user, I must see “Research hypothesis — not a procurement recommendation” on setup, result and export screens.

## Information architecture and wireframe guidelines

### Persistent navigation

Use a 280 px desktop sidebar containing the supplied logo and:

1. Projects
2. New project
3. Technology & materials
4. Reports
5. Organization
6. Help

Place the current project and status at the bottom. On tablet, collapse to an accessible drawer with a visible current-page label. Keep one dominant action per page.

### EPC project page

Display a compact workflow header:

`Overview → Project → Location → Offers → Validation → Run → Results → Review → Report`

- Use a two-column setup layout on desktop and a single column on tablet.
- Keep editable inputs in bordered cards; show units in labels.
- Make climate and calculation progress persistent above results.
- Order result content: commercial decision → key metrics → comparison tabs → exports.
- Keep diagnostics collapsed unless they block a decision.

### Required frames in Stitch

- Projects: populated and empty.
- Create project: default, field error and saved.
- EPC setup: blank, seeded and validation error.
- Offer import: drag/drop, parsing, row errors and success.
- Run: queued, fetching climate, calculating, complete, cancelled and failed.
- Results: no quote, no robust winner, robust winner, missing evidence and stale input.
- Research screening: setup and results with warning banner.
- Reports: empty, list and report detail.
- Organization: members, roles and invitation.
- Approval: pending, approved, rejected and revision requested.

## Design system and component guidelines

### Tokens

| Token | Value | Use |
|---|---|---|
| `color.navy.900` | `#0A2845` | Headings, brand text |
| `color.teal.600` | `#087F8C` | Primary analytical action |
| `color.gold.500` | `#F0B429` | Solar accent, highlight—not body text |
| `color.surface` | `#FFFFFF` | Main background |
| `color.surface.subtle` | `#F7FAFA` | Sidebar and secondary panels |
| `color.border` | `#D3E4E6` | Card and input borders |
| `color.success` | `#23835B` | Valid evidence/success |
| `color.warning` | `#C56A18` | Pending/limited evidence |
| `color.error` | `#C84A4F` | Blocking failure |
| `radius.control` | `12px` | Inputs and buttons |
| `space.unit` | `4px` | 4/8/12/16/24/32 spacing scale |

### Typography

- Use Inter or a metrically compatible system sans-serif.
- H1 40/48 semibold; H2 30/38 semibold; H3 23/30 semibold.
- Body 16/24; secondary 14/20; table minimum 14 px.
- Use tabular numerals for energy, percentage, price and coordinate values.
- Use sentence case. Avoid release/version terminology in customer-facing headings.

### Components

- App shell and responsive navigation drawer.
- Project card, status badge and workflow stepper.
- Text, numeric, date, select and coordinate inputs.
- Map with manual coordinate alternative.
- File drop zone, template download and row-validation table.
- Locked technical-evidence table and editable quote table.
- Progress tracker, toast and resumable job banner.
- Decision banner, KPI card, evidence badge and comparison table.
- Accessible tabs, disclosure panels and report-export menu.
- Review timeline, approval controls and audit-log entry.

### Interaction rules

- Disable an action only when the user can see why and how to enable it.
- Confirm destructive actions. Autosave non-destructive drafts.
- Never encode evidence state using color alone; pair color with icon and text.
- Preserve filters and scroll position when users move between evidence and results.
- Show timestamps and source status for all live external data.

## Non-functional requirements

### Accessibility

- Meet WCAG 2.2 AA.
- Maintain ≥4.5:1 contrast for normal text and ≥3:1 for large text/UI boundaries.
- Provide visible focus, logical tab order, skip link and keyboard-operable menus/tables.
- Associate error text, unit and help text with its field programmatically.
- Announce asynchronous status changes through polite live regions.
- Provide text summaries for charts and never require pointer-only map interaction.
- Support 200% zoom without loss of function at 1280 CSS pixels.
- Respect reduced motion and do not use flashing content.

### Performance and reliability

- Render the initial application shell in ≤1 second on a warm production session.
- Lazy-load maps and detailed charts.
- Preserve draft inputs across refresh and expired sessions after authentication.
- Show last-known job status after reconnect; never start a duplicate run on refresh.

### Security and privacy

- Do not expose API keys, stack traces or internal filesystem paths.
- Display tenant and project context on reports and approval screens.
- Require re-authentication for organization-level security changes.

## Data model diagram for UI state

```text
Organization 1──* Membership *──1 User
Organization 1──* Project 1──* Site
Project      1──* OfferBatch 1──* ModuleOffer
Project      1──* AnalysisRun 1──* CandidateResult
AnalysisRun  1──1 DecisionSummary
AnalysisRun  1──* EvidenceFinding
AnalysisRun  1──* Report
AnalysisRun  1──* Approval
User         1──* AuditEvent
```

Every result screen must resolve from `projectId` and immutable `analysisRunId`; transient UI state must not redefine scientific inputs.

## Testing and QA criteria

- Validate every Stitch frame against the named user story and state.
- Run moderated usability tests with at least five EPC/procurement users per design round.
- Test 1280×720, 1440×900, 1920×1080, 1024×768 and 768×1024.
- Run keyboard-only and screen-reader checks on all critical journeys.
- Run automated axe/Lighthouse checks and manual contrast/zoom/error tests.
- Add visual regression snapshots for navigation, offer import, loading, results and research warning.
- Verify all API states using contract mocks: 200, 202, 400, 401, 403, 409, 422, 429, 500 and 503.
- Verify research exports always contain the non-commercial watermark and wording.

## Replit migration considerations

- Export Stitch frontend/code and `DESIGN.md` into a versioned repository; do not copy only screenshots.
- Implement reusable components in React/TypeScript or the selected Replit-compatible frontend stack.
- Store tokens as CSS variables and assets under a stable public asset path.
- Replace Stitch prototype links with application routes and API-backed state.
- Configure Replit Secrets for API base URL, OAuth/OIDC settings and third-party credentials.
- Use environment-specific API URLs and feature flags for local, staging and production.
- Keep authentication/session handling server-side or in secure HTTP-only cookies.
- Add build, lint, type, accessibility and end-to-end commands to the Replit deployment workflow.
- Validate map-tile and NASA/PVGIS outbound-network requirements in the Replit environment.

## Milestones and timeline

| Milestone | Duration | Deliverable |
|---|---:|---|
| 1. Discovery and content model | 1 week | Approved journeys, terminology and evidence boundaries |
| 2. Stitch design system | 1 week | Logo, tokens, `DESIGN.md`, core components |
| 3. Core Stitch prototype | 2 weeks | Projects, setup, offers, run and result journeys |
| 4. Governance surfaces | 1 week | Reports, approvals, organization and audit views |
| 5. Accessibility/usability validation | 1 week | Findings resolved; approved prototype |
| 6. Replit frontend integration | 2 weeks | API-connected staging frontend |
| 7. Production hardening | 2 weeks | Security, performance, E2E and release evidence |

Total target: 10 weeks, assuming backend contracts are stable by the end of week 3.

## Acceptance criteria

- Stakeholders approve all required Stitch frames and the versioned `DESIGN.md`.
- Supplied logo is used without distortion and remains legible in expanded/collapsed navigation.
- A user can complete project setup, offer import and comparison initiation without training.
- Research and EPC workflows are visually and linguistically distinct on every screen/export.
- Every blocking state explains the cause and a next action.
- Decision status and evidence limitations precede the provisional leader.
- All critical journeys meet WCAG 2.2 AA and pass keyboard testing.
- Responsive layouts pass at the specified desktop/tablet sizes without horizontal overflow.
- Exported frontend contains no mock decision logic and integrates only through documented APIs.
- Replit staging reproduces the approved design tokens and journeys without scientific behavior changes.
