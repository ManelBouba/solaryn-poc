# SOLARYN V9.1 Runtime / Evidence-Gate Fix

This patch keeps the V9 scientific architecture unchanged and corrects two runtime inconsistencies exposed during a live EPC comparison.

## 1. Spectral proxy no longer aborts broadband EPC physics

The pvlib First Solar spectral mismatch model has bounded atmospheric inputs. V9 already classifies this technology-class proxy as sensitivity-only, but the implementation incorrectly raised a fatal error when a small fraction of daylight hours returned a non-finite proxy value.

V9.1 now:

- keeps the broadband calculation as the primary energy path;
- assigns a neutral spectral factor of 1.0 only to unsupported sensitivity hours;
- records the invalid and valid daylight coverage percentages;
- exposes the fallback policy in the result table and hourly export;
- still fails closed if a future decision-grade spectral path is explicitly run in strict mode.

A neutral factor of 1.0 means “no spectral correction for this unsupported hour”; it does not create a technology gain or penalty.

## 2. Decision-ineligible exploratory electrical fits cannot crash the whole comparison

Non-c-Si candidates without module-specific IEC 61853 evidence are already decision-ineligible under V9 policy. If their exploratory CEC fit fails, V9.1 keeps the candidate visible with missing energy outputs and an explicit model-failure diagnostic rather than terminating otherwise valid decision-grade candidate simulations.

No substitute electrical parameters are generated. A decision-grade candidate still fails closed if its accepted model fails.

## 3. Missing exploratory energy remains missing

Lifetime calculations now preserve NaN when annual exploratory energy is unavailable instead of allowing an all-NaN sum to become zero.

## Validation

- Python compileall: PASS
- Regression/unit tests: 41/41 PASS
- Added regression coverage for the exact 1% spectral-domain failure mode
- Added strict-mode regression proving a decision-grade spectral path still fails closed
- Added regression proving unavailable exploratory annual energy remains NaN in lifetime outputs

## Scientific reference

pvlib `spectral_factor_firstsolar` documentation/source defines atmospheric validity controls and notes that the default technology coefficients are derived from representative module spectral responses rather than every commercial module model:

https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.spectrum.spectral_factor_firstsolar.html
