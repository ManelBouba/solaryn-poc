# Procurement implementation validation — 2026-09-12

The complete existing pilot suite plus the initial procurement tests passed: **139 passed**, 11 dependency/thermal timedelta deprecation warnings, 64.91 seconds. A final zero-energy guard and more stable IRR discount evaluation were subsequently checked with the focused suite: **16 passed**, 5.24 seconds. The full suite was not repeated after these bounded calculation changes.

Checks cover independently hand-calculated year-one NPV/LCOE/IRR and unit conversion; multi-year discounting and compounded degradation; replacement cost, recovery and outage; equal-NPV break-even price; ties and downside monotonicity; invalid/nonfinite inputs; exact-value/BOM evidence invalidation; thermal/wind/night/clipping behavior; ambiguous IRR; zero lifetime energy; saved-result integrity and roundtrip; and Streamlit rendering, scenario interaction and saving.

The synthetic example is in `examples/procurement/decision.json` and `.md`. `tools/procurement.py --input examples/procurement/decision.json` reproduces the exact saved calculation offline. Synthetic values do not constitute scientific or commercial validation.

No cloud resources, accounts or external messages were created. No live browser server was started. Interface checks used Streamlit AppTest. Authentication, multi-tenant isolation, source-document ingestion/OCR, PDF/Excel export and approval workflows remain unimplemented, as specified in [the model documentation](PROCUREMENT_MODEL.md).
