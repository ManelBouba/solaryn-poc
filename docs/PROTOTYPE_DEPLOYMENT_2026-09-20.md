# Shareable prototype release — 2026-09-20

Source: user-supplied SOLARYN_LAST_POC_V6_AUDIT_HARDENED_2026-09-17 archive, applied over the existing solaryn-poc GitHub deployment. Original extracted archive is preserved separately. Existing scientific implementation is copied verbatim; this deployment introduces no scientific formula changes.

Presentation updates: clearer homepage, workflow introduction, responsive typography and cards, larger touch controls, reduced-motion support, original logo, prototype-link copy button with manual fallback, explicit shared/demo workspace and export guidance. Browser lint globals were completed and unused geocoding helper removed. The API contract snapshot now includes the release's existing reverse-geocoding endpoint.

Verification: frontend lint, syntax and TypeScript checks pass. Foundation, performance and report/catalog tests: 44 pass. Pilot evidence/V5/V6 regression subset, run from Solaryn_Pilot: 17 pass. Initial full Platform suite: 76 pass, two fail. One was the stale OpenAPI snapshot, now fixed. The remaining failure is in the separate authenticated server's legacy physics orchestration: evidence_hierarchy attempts boolean evaluation of a pandas Series. That interface is not the deployed entry point; its test remains a known release limitation. No scientific expectations were weakened to make tests pass.

The public app uses foundation:create_app and the existing deterministic screening adapter. Imported archive manifests document the original delivery, not the modified UI; Git records this deployment's changes.

Hosting: existing free Render service solaryn-poc, GitHub main auto-deploy. The filesystem is ephemeral: demo sites/results may reset on restart/redeploy. Visitors share the demo workspace. Export reports and evidence packages to retain results. Cold starts can delay the first visit. Recommendations remain provisional research outputs.
