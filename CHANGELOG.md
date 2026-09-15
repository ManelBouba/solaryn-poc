# SOLARYN validation correction changelog

## 2026-09-08 - external measured IEC 61853 DVP integration

- Integrated the supplied IEA PVPS Task 13 / SUPSI 12-month outdoor validation evidence with source-file SHA-256 provenance.
- Added a reusable Pmax G-T validation engine, deterministic artifact runner, monthly/point outputs and two automated regressions.
- Reproduced 28,286 retained observations, 18.163 W RMSE, 6.358% normalized RMSE, R² 0.9359 and -0.0084% cumulative sampled-energy bias.
- Promoted only the measured IEC 61853 Pmax interpolation layer to PASS; candidate-specific c-Si, cross-technology, climate, economics, historical EPC and bankability claims remain limited or pending.

## 2026-09-04 - supplied brand logo integration

- Added the supplied high-resolution transparent SOLARYN wordmark to the application shell, sidebar, and browser icon configuration.
- Updated the sidebar to a light brand surface so the navy wordmark and climate-aware tagline remain legible at application scale.
- No scientific, ranking, climate, economic, or decision behavior changed.

## 2026-09-04 - professional product-workspace UX hardening

- Added persistent navigation for Projects, New Project, Technology & Materials, Reports, Organization, and Help, plus a guided nine-stage EPC project workflow.
- Reframed the research surface as `Technology & Material Screening` and clearly labeled its outputs as research hypotheses that cannot override EPC procurement evidence.
- Added honest empty, loading, missing-quote, live-service failure, and modeled-decision states; raw connection exceptions are now kept behind optional technical details.
- Put the maximum justified price-premium state before modeled energy results and retained USD because EUR conversion is not implemented in the validated engine.
- Added keyboard-accessible latitude/longitude entry alongside the interactive map and retained public OpenStreetMap tiles without an application API key.
- Added five frontend contract regressions and verified responsive 1280 x 720 and 1440 x 900 layouts in the running Streamlit application.
- No physics constants, ranking logic, irradiance models, spectral/temperature/degradation assumptions, or decision thresholds changed.

## 2026-09-03 - climate connection error experience

- Replaced the full network exception shown in the main workflow with a concise recovery message and optional technical details.
- Explicitly states that a failed live climate request does not silently substitute fallback climate data.
- No climate, POA, physics, ranking, or decision behavior changed.

## 2026-09-03 - high-resolution visual polish

- Strengthened the professional solar palette with a deep navy navigation surface, teal analytical accents, solar-gold actions, richer chart colors, and larger high-resolution typography.
- Added three concise workflow cards for site modeling, evidence comparison, and decision output while retaining the native, accessible Streamlit layout.
- No physics, ranking, data-source, assumption, degradation, or threshold logic changed.

## 2026-09-03 - professional Streamlit interface refresh

- Reworked SOLARYN into a clean, procurement-focused workspace with persistent navigation, grouped project assumptions, a compact map, and structured module/result views.
- Added an accessible light theme with restrained teal and gold accents, native Streamlit components, and clearer evidence and bankability boundaries.
- Preserved all physics constants, candidate ranking logic, irradiance, spectral, temperature, degradation, and decision-threshold behavior.

## 2026-09-03 - map background access fix

- Replaced CARTO Positron with Folium's OpenStreetMap background in both location views after CARTO returned API-key-required tiles.
- Kept built-in OpenStreetMap attribution. Public tiles require internet and compliance with https://operations.osmfoundation.org/policies/tiles/; they are not an offline or unlimited production service.
- Preserved selected coordinates, map click handling, all weather APIs, and all scientific calculations.
- Extended the existing source regression to cover both map providers; no new physics assumptions.

## 2026-08-28 - final hardening pass

- Added exact `requirements-lock.txt` from the successful final environment.
- Added frozen three-candidate and four-candidate Riyadh regression metadata with canonical candidate-set SHA256 hashes.
- Added offline regression tests for both candidate universes, making candidate-set drift explicit.
- Generalized pvlib azimuth to official PVGIS aspect conversion and tested south, east, west, and north.
- Separated offline regression PASS, live NASA/PVGIS integration status, and interactive Streamlit status in validation wording.
- Regenerated all audit CSVs and live Riyadh outputs after the final code changes.
- Updated test/coverage logs, validation gates, manifest, unified diff, and final package.
- Did not modify physics constants, rankings, resource models, spectral/temperature/degradation assumptions, or decision thresholds.

## 2026-08-25 - audit and defensibility corrections

- Reproduced the exact three-candidate Riyadh 2020 benchmark before changing production code.
- Changed PoC decision wording so deterministic robust/no-robust status precedes the nominal modeled leader in the decision object, Streamlit UI, and HTML report.
- Added an explicit guard against fewer than two successful simulations before lifetime/project result columns are accessed.
- Made source-inspection tests explicitly UTF-8 and removed Windows CP-1252 dependence.
- Normalized whitespace in uploaded CSV headers to canonical underscores while retaining strict required-field validation.
- Added CEC STC fit diagnostics for Pmp, Voc, Isc, Vmp, and Imp and exported Jinko/LONGi residuals.
- Added directional physics tests for temperature, irradiance, and night-zero behavior.
- Added a reproducible artifact generator for monthly NASA/PVGIS resource comparison, module residuals, provenance, and measured-validation status.
- Added `pytest-cov` to the development requirements and produced text/HTML coverage reports.
- Added architecture, baseline, findings, validation plan, unresolved limitations, and final gate documentation.

No irradiance, IAM, temperature, spectral, electrical, soiling, degradation, guardrail, or economics constants were tuned to alter candidate ordering.
