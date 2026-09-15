# Pilot implementation plan

The user authorized implementation of the supplied PRD. This stage implements the local vertical slice; cloud services and multi-user security are future stages, not simulated features.

| Work | Requirements | Paths / contract | Acceptance / verification |
|---|---|---|---|
| Numerical repair | PHY-001/004, DEC-002, section 23 | module_iv_engine, uncertainty_engine; W/m2, C, kWh/kWp | Real RangeIndex weather produces positive energy; invalid daytime inputs stop; ties are order-independent |
| Decision policy | DEC-001/003/004 | pilot_decision; four status codes | Evidence absent fails closed; zero outputs never rank; no probability creates robust claims |
| Immutable service | RUN-001, FR-PROJ-01, CLIM-001/005 | pilot_service, run_store; schema 2.0 | Snapshot hashes, source/code/parameter releases, repeatable results, corruption detection |
| Pilot workflow | UI-001/002/003, RPT-001, ECO-001/002 | pilot_ui, pilot_report | Saved and live climate; persistent project runs; JSON/report parity; missing quote disables economics |
| Validation | VAL-001, section 24 | tests, tools, model card | Riyadh regression, measured replay, no invented site winners |

No database migration: new local append-only run store. Existing supplied archives remain unchanged. Model release changes require a documented numerical explanation. No cloud RBAC/TLS, vendor pricing feeds, or bankability claim is included in this local stage.
