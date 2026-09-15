# SOLARYN — DVP 12-Month External Outdoor Validation

## Source
Official dataset: https://pvpmc.sandia.gov/datasets/iea-pvps-task-13-module-validation-dataset/

IEA PVPS background report: https://iea-pvps.org/key-topics/climatic-rating-of-photovoltaic-modules/

Laboratory: SUPSI PVLab.

## Scope
This validation tests the current SOLARYN IEC 61853 **measured Pmax irradiance-temperature (G-T) interpolation layer** against the companion one-year outdoor measurements from July 2018 through June 2019.

Inputs used for prediction are the outdoor measured in-plane irradiance (Gpoa) and back-of-module temperature (Tbom/Tmod). Predicted Pmax is compared with measured Pmax from outdoor I-V curves.

## Quality-control protocol
- 36,449 raw outdoor records across 12 monthly CSVs.
- 34,763 rows contain timestamp, Pmax, Voc, Isc, module temperature and Gpoa.
- 12 physically inconsistent rows were excluded because they violate basic electrical consistency (including Pmax > Voc × Isc / invalid non-positive inputs).
- Primary reporting is limited to the laboratory-characterized envelope: 100–1100 W/m² and 15–75 °C.
- 28,286 outdoor observations remain in that envelope.
- 783 of those observations require SOLARYN's explicitly reported nearest-neighbour fallback at non-convex edges of the measured matrix.
- A strict-hull sensitivity run excludes those fallback points, leaving 27,503 observations.
- No residual-based trimming was used.

## 12-month result
Reference laboratory STC Pmax: **285.686 W**

Primary retained outdoor set, n = **28,286**:
- RMSE: **18.163 W**
- RMSE / STC Pmax: **6.358%**
- MBE: **-0.0139 W**
- MBE / STC Pmax: **-0.0049%**
- R²: **0.9359**
- Cumulative sampled-energy bias: **-0.0084%**

Strict linear-hull sensitivity, n = **27,503**:
- RMSE: **18.167 W**
- RMSE / STC Pmax: **6.359%**
- MBE: **+0.0594 W**
- MBE / STC Pmax: **+0.0208%**
- Cumulative sampled-energy bias: **+0.0351%**

## Interpretation
This is credible external measured-data validation of **one SOLARYN model layer**: the IEC 61853 measured Pmax G-T interpolation layer.

It is **not** validation of the complete SOLARYN decision engine, cross-technology ranking, annual climate-resource model, thermal model, spectral/AOI corrections, degradation model, economics, 25-year forecasting, or bankability.

The near-zero cumulative annual bias must not be presented alone. Monthly positive and negative biases partially cancel (roughly -2.9% to +1.5% over retained samples), while instantaneous RMSE remains about 6.36% of STC Pmax. Report both.

## DVP-safe wording
> SOLARYN's IEC 61853 measured-performance layer was externally evaluated against the independent IEA PVPS Task 13 / SUPSI validation dataset. Across 28,286 retained five-minute outdoor observations within the laboratory-characterized irradiance-temperature envelope, the model achieved an RMSE of 18.16 W (6.36% of STC Pmax), near-zero mean bias, R² of 0.936, and a cumulative sampled-energy bias of -0.008%. A strict interpolation-hull sensitivity produced essentially the same RMSE and a +0.035% cumulative bias. These results validate the measured-matrix interpolation layer, not the full bankability or cross-technology decision workflow.
