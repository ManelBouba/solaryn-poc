# Measured electrical validation integration record

## Source

- Dataset: IEA PVPS Task 13 module validation dataset
- Laboratory: SUPSI PVLab
- Official dataset page: https://pvpmc.sandia.gov/datasets/iea-pvps-task-13-module-validation-dataset/
- IEA PVPS background: https://iea-pvps.org/key-topics/climatic-rating-of-photovoltaic-modules/

## Integrated validation

Solaryn reproduces the supplied 12-month outdoor electrical-layer validation through `src/outdoor_validation.py`. Automated regression tests verify the numerical result and protect the evidence boundary from being promoted to whole-system or commercial-candidate validation.

## Approved claim

Solaryn's measured IEC 61853 Pmax irradiance-temperature interpolation layer was externally evaluated against the IEA PVPS Task 13 / SUPSI validation dataset. Across 28,286 retained outdoor observations inside the characterized envelope, it achieved an RMSE of 18.163 W (6.358% of STC Pmax), R² of 0.9359, and cumulative sampled-energy bias of -0.0084%.

## Scope boundary

This result validates the Pmax G-T interpolation layer for the supplied reference c-Si module. It does not validate resource accuracy, transposition, thermal prediction, spectral/AOI correction, degradation, present commercial candidates, cross-technology ranking, economics, full-system yield or bankability.
