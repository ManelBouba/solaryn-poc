# Data and evidence policy

## Two separate catalogs

Solaryn keeps two data concepts separate because they support different claims.

### Commercial candidate catalog — `data/raw/module_candidate_master.csv`

This table represents actual SKUs used in the module-recommendation workflow. It carries identity, electrical data, model/evidence metadata, geometry where verified, reliability/commercial fields when available, and explicit unknowns where evidence was not found.

The package currently contains ten sourced commercial candidates spanning PERC, TOPCon, bifacial TOPCon, HJT, bifacial HJT, HPBC/back-contact, IBC/back-contact and CdTe. Multiple supplier SKUs are included where reliable datasheets were available, while family-level claims remain prohibited unless the evidence actually supports them. Catalog expansion does not turn manufacturer specifications into independent field proof.

### Technology research catalog — `data/raw/technology_master.csv`

This 30-record table is retained for technology intelligence and research screening. Every row is explicitly marked `decision_role=research_screening_only`. It must not be used as a direct commercial procurement winner table.

Three rows describe module variants/properties rather than distinct cell families and are labeled `record_kind=module_variant`. This prevents bifaciality or similar module/system properties from being mistaken for independent technologies.

## Field-use policy

`data/processed/module_field_policy.csv` states whether each field is used for:

- direct physics,
- a fallback model,
- uncertainty/evidence control,
- display/provenance only,
- or not yet active in the current decision path.

This makes it possible to distinguish a richly documented field from a field that actually affects the winner.

## Data-quality rules

`python -m src.data_quality` checks, among other items:

- unique candidate IDs,
- required identity/electrical fields,
- finite positive electrical values,
- `Pmax ≈ Vmp × Imp` consistency,
- `Vmp < Voc` and `Imp < Isc`,
- physically consistent sign for Pmax temperature coefficient,
- valid evidence/source URLs,
- technology-catalog research-only decision role.

Unknown BOM or candidate-specific evidence is kept unknown instead of inferred from a family stereotype.

## Evidence hierarchy

Solaryn uses four broad evidence tiers:

- **A — authoritative/primary:** standards and institutional methods.
- **B — peer-reviewed field/academic:** calibration and falsification evidence for the tested context.
- **C — product/independent testing:** manufacturer datasheets, independent test files and product characterization.
- **D — secondary/industry context:** useful for hypothesis discovery, not winner-making coefficients.

## Current product-source verification

The commercial master links every candidate to a source record. The expanded catalog includes official manufacturer documentation from LONGi, JinkoSolar, REC, First Solar, Maxeon, Canadian Solar, JA Solar and Trina Solar. Key STC electrical values, temperature coefficients, module geometry and visible warranty/BOM fields are stored with verification notes.

For example, LONGi's LR7-72HVH-670M record uses the official 670 W / 24.8% / -0.260%/°C Hi-MO X10 Scientist row; Canadian Solar's CS6.2-66TB-620H uses the official 620 W TOPCon row; Canadian Solar's CS6.2-66HB-635H uses the official HJT row; and Maxeon's SPR-MAX7-445-PT uses the official 445 W / 24.1% record. Values absent from an official product sheet remain blank rather than being filled from a generic family assumption.

Manufacturer warranty information is stored as contractual/product evidence but is not converted into field-degradation truth.

## Deliberate evidence gaps

The catalog does not fabricate:

- unknown BOM constituents,
- candidate-specific spectral response where unavailable,
- candidate-specific IEC 61853 matrices where not supplied,
- exact long-term field degradation for current SKUs without supporting data,
- supplier quotes or availability not supplied by a real project.

These gaps are surfaced through evidence eligibility and wider uncertainty.
