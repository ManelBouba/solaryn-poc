from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.module_offer_io import load_module_offer_csv, normalize_module_offer_dataframe

ROOT = Path(__file__).resolve().parents[1]


def _seed_two() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data/raw/module_candidate_master.csv").iloc[:2].copy()


def test_blank_template_has_helpful_error():
    blank = pd.read_csv(ROOT / "data/raw/epc_module_offer_template.csv")
    with pytest.raises(ValueError, match="headers but no module rows"):
        normalize_module_offer_dataframe(blank)


def test_missing_optional_quote_does_not_crash():
    df = _seed_two().drop(columns=["quote_usd_w"])
    out = normalize_module_offer_dataframe(df)
    assert "quote_usd_w" in out.columns
    assert out["quote_usd_w"].isna().all()


def test_missing_ui_optional_columns_are_synthesized():
    df = _seed_two().drop(columns=[
        "technology_label", "project_segment", "spectral_evidence_level",
        "iec61853_matrix_file", "source_url", "source_note", "evidence_status",
        "cells_in_series_basis",
    ])
    out = normalize_module_offer_dataframe(df)
    for col in [
        "technology_label", "project_segment", "spectral_evidence_level",
        "iec61853_matrix_file", "source_url", "source_note", "evidence_status",
        "cells_in_series_basis", "quote_usd_w",
    ]:
        assert col in out.columns


def test_column_names_are_trimmed_and_lowercased():
    df = _seed_two()
    df = df.rename(columns={"quote_usd_w": " Quote_USD_W "})
    out = normalize_module_offer_dataframe(df)
    assert "quote_usd_w" in out.columns


def test_spaces_and_capitalization_in_headers_are_normalized():
    df = _seed_two().rename(columns={
        "module_id": " Module ID ",
        "technology_id": "Technology ID",
        "pmax_w": "Pmax W",
    })
    out = normalize_module_offer_dataframe(df)
    assert out.loc[0, "module_id"] == _seed_two().loc[0, "module_id"]
    assert out.loc[0, "technology_id"] == _seed_two().loc[0, "technology_id"]
    assert float(out.loc[0, "pmax_w"]) == float(_seed_two().loc[0, "pmax_w"])


def test_duplicate_module_id_is_rejected():
    df = _seed_two()
    df.loc[df.index[1], "module_id"] = df.loc[df.index[0], "module_id"]
    with pytest.raises(ValueError, match="must be unique"):
        normalize_module_offer_dataframe(df)


def test_semicolon_excel_locale_and_decimal_commas_are_accepted():
    df = _seed_two().copy()
    # Simulate a French/Belgian Excel export: semicolon separator and decimal comma.
    text = df.to_csv(index=False, sep=";")
    text = text.replace("550.0", "550,0").replace("-0.34", "−0,34")
    out = load_module_offer_csv(StringIO(text))
    assert len(out) == 2
    assert float(out.loc[0, "pmax_w"]) == 550.0
    assert float(out.loc[0, "gamma_pmax_pct_c"]) == pytest.approx(-0.34)
