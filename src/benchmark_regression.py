from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


RIYADH_THREE_CANDIDATE_IDS = (
    "MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530",
    "MOD_PERC_LONGI_LR5_72HPH_550M",
    "MOD_TOPCON_JINKO_JKM575N_72HL4_V",
)

RIYADH_FOUR_CANDIDATE_IDS = RIYADH_THREE_CANDIDATE_IDS + (
    "MOD_HJT_REC_ALPHA_PURE_RX_470",
)


def candidate_set_sha256(modules: pd.DataFrame) -> str:
    """Hash normalized candidate records, including evidence and optional fields."""
    columns = sorted(modules.columns)
    payload = modules.sort_values("module_id")[columns].to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.12g",
        na_rep="",
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_frozen_riyadh_benchmarks(root: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(root) / "data/processed/riyadh_benchmark_v9_2_1.csv")
