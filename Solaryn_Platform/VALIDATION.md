# Platform validation — 13 September 2026

## Automated checks

Ten API integration tests passed after repairing initial SQL insert-column mismatches. Coverage includes:

- Account creation, sign-in, HttpOnly/SameSite cookies, CSRF rejection, logout invalidation and cross-origin write rejection.
- Cross-organization denial for project reads/writes, source downloads, result reads, claim reviews, approvals and source-document references. Audit output remains scoped to the organization.
- Editor/reviewer/viewer permissions and blocked privilege escalation through member provisioning.
- Exact result parity with the existing procurement model and persisted-result access after application recreation.
- Source storage/download; exact-value evidence binding; authenticated claim review; complete-checklist approval; duplicate approval rejection; stale-revision rejection; changed-price evidence invalidation; preservation of older outputs.
- Invalid scientific inputs, malformed filenames/PDF headers, oversized request rejection, persistent login throttling and result hash failure detection.
- Static asset serving and security headers.

The installed Starlette TestClient emits a deprecation warning about httpx; it did not affect these tests. The existing scientific engine was reused, not modified by this platform build.

## Browser verification

Verified against the local server using an isolated synthetic QA organization:

- Sign-in and organization-scoped empty portfolio render successfully.
- Creating the synthetic example persists one project and two offers.
- Base comparison completes and appears in decision history.
- For the synthetic 100 MWp example, Candidate B has base NPV EUR 33,116,504 and LCOE EUR 30.25/MWh, with eight missing reviewed claims across the two candidates. These figures are software fixtures, not measured product performance or investment advice.
- A downside scenario of +0.50 percentage points of annual degradation and 5% yield haircut produces Candidate B NPV EUR 23,653,586; the saved scenario and entered controls remain visible after calculation.
- Reloading the browser preserves authentication and project data.
- Browser console inspection returned no errors; desktop visual layout was inspected.

Browser testing did not establish production security, mobile-device coverage, independent scientific validity, AI extraction or cloud operation. API tests cover the document/reviewer/approval workflow; the entire file-upload and reviewer workflow has not been exercised manually through the browser.
