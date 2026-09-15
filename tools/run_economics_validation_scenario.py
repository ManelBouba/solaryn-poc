"""Run a clearly labelled, non-market economics scenario on the live Riyadh yields.

The prices below exist only to exercise the switching-point code path. They are not
supplier quotes and must not be presented as commercial evidence.
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.economics_engine import switching_point_table
from src.module_offer_io import load_module_offer_csv


OUTPUT = ROOT / "outputs" / "RIYADH_ECONOMICS_TEST_SCENARIO.csv"
TEST_QUOTES_USD_W = {
    "MOD_PERC_LONGI_LR5_72HPH_550M": 0.20,
    "MOD_TOPCON_JINKO_JKM575N_72HL4_V": 0.23,
    "MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530": 0.19,
}


def main() -> None:
    modules = load_module_offer_csv(ROOT / "data/raw/module_candidate_master.csv")
    results = pd.read_csv(ROOT / "outputs/RIYADH_LIVE_BENCHMARK_RESULTS.csv")
    results = results.loc[results["case"].eq("three_candidate")].copy()
    modules["quote_usd_w"] = modules["module_id"].map(TEST_QUOTES_USD_W)

    switching = switching_point_table(
        results,
        modules,
        baseline_module_id="MOD_PERC_LONGI_LR5_72HPH_550M",
        energy_value_usd_kwh=0.05,
        discount_rate_pct=7.0,
        area_bos_usd_m2=20.0,
        years=25,
        common_degradation_pct_year=0.5,
        allow_exploratory=True,
    )
    switching.insert(0, "scenario_status", "TEST_ONLY_NOT_SUPPLIER_QUOTES")
    switching.to_csv(OUTPUT, index=False)
    print(switching[[
        "module_id",
        "actual_quote_usd_w",
        "allowable_module_price_premium_vs_baseline_usd_w",
        "indifference_module_price_usd_w",
        "economically_preferred_vs_baseline_at_quote",
        "economic_decision_eligible",
        "economic_evidence_note",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
