# SOLARYN V9 Source / Evidence Map

## IEA PVPS Task 13 — Climatic Rating of PV Modules (2020)

Official report page: https://iea-pvps.org/key-topics/climatic-rating-of-photovoltaic-modules/

Used for V9 design principles:

- climate-specific energy rating rather than STC-only ranking;
- low-irradiance, temperature, spectral and angular effects;
- IEC 61853 G-T performance matrix concept;
- full-year hourly climate profiles;
- technology/model-form caution;
- uncertainty and “do not over-resolve small differences” principle;
- Annex 1 validation-data structure.

## Sandia PV Performance Modeling Collaborative

Datasets: https://pvpmc.sandia.gov/datasets/

IEA PVPS module validation dataset: https://pvpmc.sandia.gov/datasets/iea-pvps-task-13-module-validation-dataset/

PV Lifetime / module characterization datasets: https://pvpmc.sandia.gov/datasets/pv-lifetime-module-datasets-clone/

Used as the planned external validation source for:

- IEC 61853-1 performance matrices;
- IEC 61853-2 IAM / thermal evidence;
- PAN/PVsyst comparison;
- one-year outdoor validation.

## pvlib

IEC 61853 matrix to PVsyst parameter fitting (current pvlib):
https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.ivtools.sdm.fit_pvsyst_iec61853_sandia_2025.html

Tilted irradiance models:
https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.get_total_irradiance.html

Faiman temperature model:
https://pvlib-python.readthedocs.io/en/stable/user_guide/modeling_topics/temperature.html

IAM modeling:
https://pvlib-python.readthedocs.io/en/stable/user_guide/modeling_topics/iam.html

## NASA POWER

Hourly API:
https://power.larc.nasa.gov/docs/services/api/temporal/hourly/

Parameter guidance:
https://power.larc.nasa.gov/docs/tutorials/parameters/

Used for global hourly resource/meteorology input. POWER data should be treated at its native spatial/temporal resolution; it is not a microclimate sensor.

## Evidence hierarchy in code

1. Module-specific measured/traceable evidence.
2. Validated model fitted to module-level measurements.
3. Datasheet physical fallback where scientifically appropriate.
4. Common project assumption that does not create technology differences.
5. Technology-class proxy only as a visible sensitivity.
6. No evidence -> no robust decision.
