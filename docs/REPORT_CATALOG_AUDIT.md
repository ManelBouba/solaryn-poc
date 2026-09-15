# Report / visuals / catalog increment audit

Baseline 2026-09-15: **70 platform tests passed**, five dependency deprecation warnings. Current foundation uses four rows in `data/raw/module_candidate_master.csv`; Pilot contains ten rows, with HPBC, IBC and bifacial variants absent from the active catalog.

The current Path C PVWatts model differentiates year-1 DC specific yield only by the supplied temperature coefficient. Neither technology names nor a larger catalog can supply missing P(G,T), spectral, rear-side, IAM or thermal evidence. Existing completed results must retain their original inputs and outputs.

Reviewed reusable components:

- Pilot `iec61853_engine.py`: pure matrix validation/interpolation, with documented temperature clipping, irradiance scaling and counted nearest fallback. Safe to load under an isolated module name after validating SKU identity and finite measured data. It does not establish exact IEC 61853-3 compliance.
- Pilot `module_iv_engine.py`, `_pmp_from_cec`: reviewed pvlib CEC/maximum-power primitive. A small isolated adapter can use this same calculation with supplied validated coefficients, without importing spectral/thermal family policy or fitting inferred electrical topology.
- Pilot `epc_report.py`: pure SVG line/bar layout patterns can be refactored for the current immutable result contract. Its old aggregate calculations, green branding and probability-of-best claims must not be imported.
- Pilot lifetime/economics orchestration uses different historical assumptions; the current backend-stored annual lifetime and procurement outputs remain the source for reports.

Implementation order: canonical catalog and source audit; evidence-gated A/B/C routing plus stored chart data; shared pure report/chart renderer and archive endpoints; richer candidate filters and visual results; regression/browser/offline-report verification.

Market verification policy: an official current product/download listing supports a marketed product, not inventory or an executable quote. Old datasheet existence alone leaves current availability UNKNOWN. Preserve datasheet region and application restrictions; CIGS facade products require a compatible facade scenario. No exact tandem SKU will be fabricated to satisfy a row-count target.
