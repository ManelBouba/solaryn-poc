# SOLARYN PoC end-to-end validation

**Execution date:** 8 September 2026  
**Scenario:** Riyadh, Saudi Arabia; latitude 24.7136, longitude 46.6753; reference year 2020; fixed tilt 25°; south-facing azimuth 180°  
**Purpose:** Validate location → climate → technology comparison → evidence-gated recommendation → performance/economic output.

## Executive result

The PoC pipeline executed successfully using live NASA POWER and PVGIS data and the packaged module-candidate records. The implementation reproduced the frozen Riyadh result exactly: JinkoSolar JKM575N-72HL4-V is the provisional modeled annual-energy leader at 2,073.433 kWh/kWp/year.

The system correctly did **not** issue a robust cross-technology winner. The Jinko lead over the next candidate is 1.2103%, below the declared 2.00% decision guardrail, and the selected First Solar CdTe candidate lacks a decision-eligible module-specific electrical model. This is correct fail-closed behavior, not a failed calculation.

## Test evidence

| Stage | Result | Evidence |
|---|---|---|
| Offline regression | PASS | 64/64 tests passed, including two external measured DVP regressions |
| Location | PASS | Riyadh 24.7136, 46.6753 |
| NASA POWER climate | PASS | 8,784 hourly records for leap year 2020 |
| PVGIS cross-check | PASS | 8,784 hourly records |
| NASA → pvlib POA | PASS | 2,346.767 kWh/m²/year |
| PVGIS in-plane irradiation | PASS | 2,473.875 kWh/m²/year |
| Resource comparison | REVIEW | PVGIS is 5.138% above NASA→pvlib annually; retain as an explicit cross-check discrepancy |
| Three-candidate physics comparison | PASS | Frozen candidate hash and yields reproduced |
| Evidence-gated recommendation | PASS | Provisional leader shown; robust winner withheld |
| Missing-quote economics gate | PASS | Packaged quotes are blank, so production economics remains disabled |
| Test-only economics scenario | PASS | Switching calculation executed with clearly synthetic prices |
| External measured/financial validation | PARTIAL | IEC 61853 Pmax G-T interpolation layer externally validated; supplier quotes, candidate-specific matrices, historical EPC and bankability evidence remain pending |

## Performance output

| Candidate | Annual modeled DC specific energy | Evidence eligibility | Outcome |
|---|---:|---|---|
| JinkoSolar JKM575N-72HL4-V | 2,073.433 kWh/kWp/year | Eligible c-Si datasheet-fit fallback | Provisional modeled leader |
| First Solar Series 7 TR1 530 | 2,048.638 kWh/kWp/year | Ineligible exploratory model | Visible, cannot establish robust winner |
| LONGi LR5-72HPH-550M | 2,034.998 kWh/kWp/year | Eligible c-Si datasheet-fit fallback | Third by modeled annual yield |

Candidate-set SHA-256: `e5953b0d0b3cbf873ef2c04c6780947547e90a115b3c10a6e877598626c0f590`.

## Recommendation interpretation

- **What works:** the system identifies and ranks the provisional modeled energy leader.
- **What is correctly withheld:** a robust cross-technology or bankable recommendation.
- **Why:** the energy separation is below the decision guardrail and not all selected model evidence is eligible.
- **Next evidence required:** module-specific IEC 61853 or validated device-specific performance evidence, measured validation/holdout data, and real supplier offers.

## Economics-path validation

The packaged supplier prices are intentionally blank. Therefore, the real commercial output correctly states that the maximum justified price premium is unavailable.

To exercise the economics code path without representing invented prices as market evidence, a test-only scenario used:

- LONGi baseline: $0.200/W
- JinkoSolar: $0.230/W
- First Solar: $0.190/W
- Energy value: $0.05/kWh
- Discount rate: 7.0%
- Area-sensitive BOS input: $20/m²
- Common project degradation scenario: 0.50%/year

| Candidate | Maximum premium vs LONGi | Indifference price | Test quote | Test result | Decision eligible |
|---|---:|---:|---:|---|---|
| LONGi | $0.0000/W | $0.2000/W | $0.2000/W | Baseline | Yes |
| JinkoSolar | $0.02546/W | $0.22546/W | $0.2300/W | Above threshold; not preferred in this test scenario | Yes |
| First Solar | -$0.00414/W | $0.19586/W | $0.1900/W | Below threshold, but blocked from a commercial recommendation | No |

These numbers validate the switching-point implementation only. They are not real supplier prices, LCOE, financial advice or a procurement recommendation.

## Generated artifacts

- `RESOURCE_BENCHMARK.csv`
- `outputs/RIYADH_LIVE_BENCHMARK_RESULTS.csv`
- `outputs/RIYADH_ECONOMICS_TEST_SCENARIO.csv`
- `MODULE_FIT_RESIDUALS.csv`
- `DATA_PROVENANCE.csv`
- `MEASURED_VALIDATION_RESULTS.csv`

## Final PoC conclusion

The end-to-end software PoC is functioning as designed for the supplied Riyadh example. Its IEC 61853 measured Pmax G-T interpolation layer also has external validation for one reference c-Si module. The platform can produce climate-aware performance rankings, explain evidence limitations and calculate a quote-sensitive switching threshold. It must not yet be marketed as fully externally validated, bankable or capable of a final cross-technology procurement recommendation until the remaining evidence gates and real supplier quotations are supplied.
