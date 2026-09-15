# External DVP integration record

## Source package

- Supplied archive: `SOLARYN_DVP_12_Month_Outdoor_Validation_Evidence (1).zip`
- Archive SHA-256: `4635cee0583e4965a011052e7eb13806408eef2701b8e80f5ae4f006bce17297`
- Dataset: IEA PVPS Task 13 module validation dataset
- Laboratory: SUPSI PVLab
- Official dataset page: https://pvpmc.sandia.gov/datasets/iea-pvps-task-13-module-validation-dataset/
- IEA PVPS background: https://iea-pvps.org/key-topics/climatic-rating-of-photovoltaic-modules/

## Integrated validation

SOLARYN reproduces the supplied 12-month outdoor validation through `src/outdoor_validation.py` and `tools/run_outdoor_validation.py`. Two automated regressions verify the numerical result and prevent the evidence scope from being promoted to full decision-engine or commercial-candidate validation.

## Approved claim

SOLARYN's measured IEC 61853 Pmax irradiance-temperature interpolation layer was externally evaluated against the IEA PVPS Task 13 / SUPSI validation dataset. Across 28,286 retained outdoor observations within the laboratory-characterized envelope, it achieved an RMSE of 18.163 W (6.358% of STC Pmax), R² of 0.9359, and cumulative sampled-energy bias of -0.0084%.

## Scope boundary

This result validates the Pmax G-T interpolation layer for the supplied reference c-Si module. It does not validate NASA/PVGIS resource accuracy, transposition, thermal prediction, spectral/AOI correction, degradation, current Jinko/LONGi/First Solar candidate models, cross-technology ranking, economics, full-system yield or bankability.
