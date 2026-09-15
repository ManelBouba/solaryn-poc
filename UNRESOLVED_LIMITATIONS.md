# Unresolved limitations

- The IEC 61853 measured Pmax G-T interpolation layer is externally validated against one IEA PVPS Task 13 / SUPSI reference c-Si module and 12 months of outdoor data. Candidate-specific Jinko/LONGi off-STC validation, cross-technology validation, and full decision-chain measured validation remain PENDING.
- First Solar Series 7 TR1 530 still uses a transparently exploratory CEC-style electrical fallback and remains decision-ineligible. A CdTe-appropriate validated model or measured G-T-Pmax matrix is required.
- No manufacturer datasheet PDFs are packaged locally; seed rows point to sources but their document version/date and exact BOM traceability are incomplete.
- NASA POWER and PVGIS are gridded/modelled resources, not site measurements. The -5.138% annual POA residual is documented, not calibrated away.
- NASA and PVGIS boundaries are not fully identical: PVGIS horizon is enabled and service-side model/albedo metadata are not fully controlled by the current response parser.
- No frozen full-year API response is yet packaged. The artifact generator and live benchmark still require external services.
- No independent PVsyst/PAN/SAM monthly DC benchmark exists.
- Thermal behavior mostly uses construction-class SAPM fallbacks rather than product-specific measured coefficients.
- Technology-class spectral corrections are sensitivity-only; no module-specific spectral response is supplied.
- The 0.5%/year common degradation value is a declared scenario. Warranty slopes are sensitivities; stress metrics are not degradation predictions.
- No actual supplier/EPC quotes or closed historical procurement record were supplied. Procurement economics and historical validation remain PENDING.
- The economic model is a module + area-BOS switching threshold, not LCOE. It excludes financing, O&M, inverter/AC losses, availability, curtailment, replacements, taxes, and other cash-flow elements.
- There is no uncertainty propagation, P50/P90 calculation, or bankability basis.
- Overall `src` line coverage is 66%; live orchestration, HTML report generation, climate conversion, and stress modules need additional mocked integration coverage.
- A project-level exact dependency lock and CI workflow remain to be established; requirements currently use bounded ranges.
