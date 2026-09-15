# Solaryn pilot model card

Model release 3.0.0; decision policy 3.0.0; result schema 2.0. The internal release identifiers and checksums serve reproducibility; the product name is Solaryn.

## Numerical change

The supplied row model constructed a pandas Series from timestamp-indexed extraterrestrial irradiance while specifying a RangeIndex. Label alignment created missing values for every hour. Later zero filling produced zero energy, and argmax selected the first tied candidate. The repaired adapter explicitly transfers irradiance values onto the weather index, checks finite daylight irradiance and temperature, and rejects non-positive annual results. Tests compare RangeIndex and DatetimeIndex inputs and exercise the real saved weather pipeline.

References: [pvlib extraterrestrial irradiance API](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.get_extra_radiation.html) and [pvlib infinite-sheds API](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.bifacial.infinite_sheds.get_irradiance.html). Using this geometry model does not establish independently measured rear-side validation.

## Units and boundaries

| Quantity | Unit / rule |
|---|---|
| Irradiance | W/m2, explicit UTC hourly records |
| Temperature | ambient, module/back-sheet and cell C remain distinct |
| Pmax | W per module; area/efficiency and Vmp x Imp are checked |
| Specific power | W/Wp, numerically kW/kWp |
| Annual energy | hourly specific-power sum with 1/N resource-year weights, kWh/kWp/year |
| Project DC energy | kWh/kWp x MWp = MWh/year |
| Common lifetime | compounded annual retention with annual-average retention, no climate-derived degradation |
| Warranty | separate linear warranty-retention sensitivity; not measured degradation |
| Economics | year-end discounted energy difference per DC watt plus area-BOS difference, declared USD or EUR |
| Decision guardrail | max(minimum separation, selected guardrail), default 2%; not statistical confidence |

The annual Riyadh no-row baseline is unchanged: TOPCon 2073.433038, CdTe 2048.638261 and Mono PERC 2034.997755 kWh/kWp/year. TOPCon's 1.2103% modeled lead does not establish a robust cross-technology winner. The latest supplied build already changed common degradation from the older linear scenario to a compounded scenario; this delivery preserves that latest convention and makes it explicit. Thus annual-energy baseline parity does not imply parity with the older linear lifetime totals.

Exact matrix evidence takes precedence over permitted c-Si datasheet fits. Unsupported device-model paths remain ineligible. Thermal construction defaults, generic IAM, common soiling, fixed-tilt geometry and albedo assumptions remain visible. Unreviewed numeric thermal coefficients are not independent proof of field validation. The ten catalog records are retained rather than replaced with fabricated measurements; their parameter records state source and reviewer limits.

## State precedence

Failed selected simulations or missing candidate evidence -> insufficient evidence. Otherwise an exact tie, a gap within the guardrail, or a declared scenario reversal -> effectively tied. A separated eligible leader with incomplete robust conditions -> provisional technical leader. Robust modeled advantage requires adequate independent resource agreement and the declared stronger electrical, thermal and geometry/rear gates. Exact ties have no unique leader. The available catalog does not establish full cross-technology field validity.

## Validation

The measured SUPSI replay uses independent supplied module characterization and outdoor observations. MAE 8.6006 W, RMSE 18.1633 W, MBE -0.01391 W, normalized RMSE 6.3578% STC, R2 0.93588; maximum absolute residual 184.918 W. Of 28286 retained observations, 2.7682% use nearest fallback. Input hashes are published with the replay. This validates only that reference electrical interpolation layer, not all product SKUs, site/weather, thermal model, lifetime, economics or procurement outcomes.

The historical field registry retains the Benguerir ordering failure. Historical KU Leuven thermal records lack the raw measurements needed for a fresh holdout replay. Cross-technology, historical EPC replay and bankability gates remain pending/not claimed. A passing software suite is not a passing scientific field-validation gate.
