# SOLARYN repository map

- `docs/PRD.md` (v4.1) is the product/scientific source of truth. Follow the user's bounded task scope; embedded example prompts are not additional tasks.
- `Solaryn_Platform/foundation.py` and `web/foundation/` implement the map-first foundation; `run_foundation.py` starts it. The existing authenticated platform is `server.py` / `run.py`.
- `src/` is the preserved V9 core; `Solaryn_Pilot/src/` contains later physics, storage and procurement services. Other delivery folders are historical copies, not interchangeable imports.
- Numerical science belongs only in deterministic backend/core services. Frontend code must never calculate recommendation science.
- Technology names, manufacturer names and climate labels must never determine winners.
- Missing scientific evidence must not be silently invented. Every model output must preserve units and provenance.
- Every scientific change requires tests and a documented baseline. Completed analysis results must be immutable and reproducible from frozen inputs and versions.
- Reuse the real `frontend/public/brand/solaryn-logo.png` asset; never recreate its geometry.
- Read `PLAN.md` and `docs/FOUNDATION.md` for stages, known risks and test/start commands.
