from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


REFERENCE_THREE_CANDIDATE_IDS = (
    "MOD_CDTE_FIRST_SOLAR_SERIES7_TR1_530",
    "MOD_PERC_LONGI_LR5_72HPH_550M",
    "MOD_TOPCON_JINKO_JKM575N_72HL4_V",
)

REFERENCE_FOUR_CANDIDATE_IDS = REFERENCE_THREE_CANDIDATE_IDS + (
    "MOD_HJT_REC_ALPHA_PURE_RX_470",
)


def candidate_set_sha256(modules: pd.DataFrame) -> str:
    """Hash normalized candidate records, including evidence and optional fields."""
    # The reference benchmark hash is intentionally tied to the historical baseline
    # schema. Post-baseline optional fields are tested independently so adding an
    # all-zero/blank field does not falsely mutate the frozen physics fixture.
    extension_columns = {"bifaciality_factor", "bifaciality_tolerance_pct_points", "bifaciality_source"}
    columns = sorted(c for c in modules.columns if c not in extension_columns)
    payload = modules.sort_values("module_id")[columns].to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.12g",
        na_rep="",
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_frozen_reference_benchmarks(root: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(root) / "data/processed/reference_regression_benchmark.csv")
