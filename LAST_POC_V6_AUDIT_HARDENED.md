# SOLARYN — Last PoC V6 Audit-Hardened (2026-09-17)

This release incorporates the defensible parts of the external PV Decision Engine audit without copying unsupported heuristics or unreproducible site winners.

## Implemented

- Keeps pvlib `infinite_sheds` as the rear-side bifacial irradiance model; no handwritten view-factor replacement.
- Uses all-hours annual T98 for IEC TS 63126 screening logic.
- Missing high-temperature / salt-mist / humidity evidence is conditional by default; hard blocking requires an explicit project policy.
- Adds optional rainfall-driven pvlib Kimber soiling. The default remains a declared common project scalar.
- Supports direct snowfall/snow-depth inputs and explicit snow albedo; no snow bonus is invented when those inputs are absent.
- Candidate-specific degradation mean is accepted only with explicit validated field evidence. Otherwise all candidates share the same project degradation prior.
- Candidate uncertainty no longer depends on technology family or A/B/C/D evidence grade. Product-specific empirical residuals can override a common screening residual.
- Adds correlated annual and lifetime Monte Carlo comparisons: the same resource and common degradation scenario is applied to every co-located candidate in each draw.
- Decision Trace exposes all-hours T98, lifetime P50/P90, degradation mean/sigma and degradation evidence basis.
- No city-to-technology rules and no forced diversity of winners.

## Deliberately not implemented from the external audit

- No universal `EVA + tropical = FAIL` rule.
- No automatic `coastal <10 km => FAIL without IEC 61701` rule unless the project explicitly enables hard gates.
- No fixed technology-family degradation rates or first-year-loss constants.
- No invented evidence-grade uncertainty widths.
- No copied 30-site winner table; every future site claim must come from a reproducible execution artifact.
- No custom bifacial view-factor implementation from the audit PDF.

## Validation in this environment

- Python source compilation succeeds for the complete Pilot and Platform source trees.
- Scientific/evidence/decision/procurement test subset: 39 passed; one UI test cannot run here because Streamlit is unavailable.
- `pvlib`, `NREL-PySAM`, and `streamlit` are not installed in this execution environment, so a new full live hourly site run cannot be truthfully claimed here.

## Run locally

From the package root on Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\Solaryn_Platform\requirements-lock.txt
.\.venv\Scripts\python.exe .\Solaryn_Platform\run_foundation.py
```

Open `http://127.0.0.1:8766`.

## Next scientific bottleneck

The code can now distinguish candidates without assigning family-wide bonuses. The remaining bottleneck is evidence density in the commercial candidate catalog: product-specific IEC 61853/PAN response, measured thermal parameters, bifaciality provenance, BOM/qualification evidence, validated field degradation and actual supplier prices. Missing evidence must remain visible rather than being replaced by favorable assumptions.
