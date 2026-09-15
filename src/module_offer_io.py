from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO, TextIO

import numpy as np
import pandas as pd

from src.module_iv_engine import REQUIRED_MODULE_FIELDS, validate_module_candidates

# Canonical V9.2 EPC module-offer schema.  The physics engine only requires the
# strict core fields in REQUIRED_MODULE_FIELDS; the remaining fields are
# evidence, display or economics metadata and must never crash the upload path
# when omitted.
CANONICAL_MODULE_OFFER_COLUMNS = [
    "module_id", "technology_id", "manufacturer", "model", "technology_label",
    "cec_celltype", "pmax_w", "vmp_v", "imp_a", "voc_v", "isc_a",
    "alpha_isc_pct_c", "beta_voc_pct_c", "gamma_pmax_pct_c",
    "cells_in_series", "cells_in_series_basis", "module_area_m2",
    "module_efficiency_pct", "noct_c", "thermal_construction",
    "first_year_retention_pct", "annual_warranty_degradation_pct_year",
    "warranty_years", "quote_usd_w", "source_url", "evidence_status",
    "source_note", "iec61853_matrix_file", "spectral_evidence_level",
    "thermal_u0_w_m2k", "thermal_u1_w_s_m3k", "bom_evidence_status",
    "project_segment", "spectral_response_file", "spectral_irradiance_source",
    "iam_curve_file", "thermal_evidence_source",
    "electrical_model_validation_reference", "bom_source_reference",
]

OPTIONAL_DEFAULTS = {
    "technology_label": "unspecified",
    "cells_in_series_basis": "user_supplied_unverified",
    "noct_c": np.nan,
    "quote_usd_w": np.nan,
    "source_url": "",
    "evidence_status": "user_supplied",
    "source_note": "",
    "iec61853_matrix_file": "",
    "spectral_evidence_level": "technology_class_proxy",
    "thermal_u0_w_m2k": np.nan,
    "thermal_u1_w_s_m3k": np.nan,
    "bom_evidence_status": "not_provided",
    "project_segment": "all",
    "spectral_response_file": "",
    "spectral_irradiance_source": "",
    "iam_curve_file": "",
    "thermal_evidence_source": "",
    "electrical_model_validation_reference": "",
    "bom_source_reference": "",
}

_TEXT_COLUMNS = {
    "module_id", "technology_id", "manufacturer", "model", "technology_label",
    "cec_celltype", "cells_in_series_basis", "thermal_construction", "source_url",
    "evidence_status", "source_note", "iec61853_matrix_file",
    "spectral_evidence_level", "bom_evidence_status", "project_segment",
    "spectral_response_file", "spectral_irradiance_source", "iam_curve_file",
    "thermal_evidence_source", "electrical_model_validation_reference",
    "bom_source_reference",
}


def _read_csv(source: str | Path | BinaryIO | TextIO) -> pd.DataFrame:
    try:
        # ``sep=None`` handles comma/semicolon/tab CSVs produced by different Excel
        # locales (important for EU users) while preserving quoted fields.
        return pd.read_csv(source, sep=None, engine="python")
    except pd.errors.EmptyDataError as exc:
        raise ValueError(
            "The uploaded CSV is empty. Use the SOLARYN template and add at least two module rows."
        ) from exc
    except Exception as exc:
        raise ValueError(f"The uploaded file could not be parsed as CSV: {exc}") from exc


def normalize_module_offer_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a user EPC CSV and make optional metadata safe downstream.

    Required physics fields remain fail-closed.  Optional evidence/economics
    fields are added with explicit neutral/blank defaults so a missing quote or
    display column disables only that feature rather than crashing Streamlit.
    """
    out = df.copy()
    out.columns = [
        "_".join(str(c).lstrip("\ufeff").strip().lower().split())
        for c in out.columns
    ]

    if out.columns.duplicated().any():
        duplicated = sorted(set(out.columns[out.columns.duplicated()].tolist()))
        raise ValueError(f"Duplicate CSV column names after normalization: {duplicated}")

    if out.empty:
        raise ValueError(
            "This file contains headers but no module rows. Add at least two module candidates, "
            "or download the populated example CSV."
        )


    # Normalize common spreadsheet exports before strict physics validation.
    # This accepts decimal commas, Unicode minus signs, percent signs and currency
    # symbols without weakening the numerical validity checks that follow.
    numeric_columns = {
        "pmax_w", "vmp_v", "imp_a", "voc_v", "isc_a",
        "alpha_isc_pct_c", "beta_voc_pct_c", "gamma_pmax_pct_c",
        "cells_in_series", "module_area_m2", "module_efficiency_pct", "noct_c",
        "first_year_retention_pct", "annual_warranty_degradation_pct_year",
        "warranty_years", "quote_usd_w", "thermal_u0_w_m2k", "thermal_u1_w_s_m3k",
    }
    for col in numeric_columns.intersection(out.columns):
        def _clean_number(v):
            if pd.isna(v) or isinstance(v, (int, float, np.number)):
                return v
            text = str(v).strip().replace("−", "-").replace("–", "-")
            text = text.replace("$", "").replace("€", "").replace("%", "").replace(" ", "")
            if "," in text and "." not in text:
                text = text.replace(",", ".")
            return text
        out[col] = out[col].map(_clean_number)

    missing_required = [c for c in REQUIRED_MODULE_FIELDS if c not in out.columns]
    if missing_required:
        raise ValueError(
            "Module candidate table is missing required physics columns: "
            + ", ".join(missing_required)
        )

    # Required model fields are validated before optional columns are synthesized.
    validate_module_candidates(out)

    for col, default in OPTIONAL_DEFAULTS.items():
        if col not in out.columns:
            out[col] = default

    # Standardize text without converting true missing values into the literal 'nan'.
    for col in _TEXT_COLUMNS.intersection(out.columns):
        out[col] = out[col].map(
            lambda v: "" if pd.isna(v) else str(v).strip()
        )

    # Re-apply meaningful defaults to blank optional text cells.
    for col, default in OPTIONAL_DEFAULTS.items():
        if col in out.columns and isinstance(default, str):
            blank = out[col].astype(str).str.strip().eq("")
            out.loc[blank, col] = default

    # Economics is optional.  Invalid/blank quote cells become NaN rather than a crash.
    out["quote_usd_w"] = pd.to_numeric(out["quote_usd_w"], errors="coerce")
    invalid_quote = out["quote_usd_w"].notna() & (out["quote_usd_w"] < 0)
    if invalid_quote.any():
        mids = out.loc[invalid_quote, "module_id"].astype(str).tolist()
        raise ValueError(f"quote_usd_w cannot be negative: {mids}")

    # Stable IDs are essential because selections, report joins and economics use them.
    if out["module_id"].astype(str).str.strip().eq("").any():
        raise ValueError("module_id cannot be blank.")
    if out["module_id"].duplicated().any():
        dupes = out.loc[out["module_id"].duplicated(keep=False), "module_id"].astype(str).tolist()
        raise ValueError(f"module_id values must be unique. Duplicates: {sorted(set(dupes))}")

    # Put known columns first while preserving any user-supplied extra columns.
    canonical = [c for c in CANONICAL_MODULE_OFFER_COLUMNS if c in out.columns]
    extras = [c for c in out.columns if c not in canonical]
    return out[canonical + extras].reset_index(drop=True)


def load_module_offer_csv(source: str | Path | BinaryIO | TextIO) -> pd.DataFrame:
    return normalize_module_offer_dataframe(_read_csv(source))


def module_offer_readiness(df: pd.DataFrame, root: str | Path | None = None) -> pd.DataFrame:
    """Return UI-friendly evidence/economics readiness flags without changing physics."""
    from src.evidence_policy import electrical_model_policy

    rows = []
    for _, r in df.iterrows():
        policy = electrical_model_policy(r, root)
        quote = pd.to_numeric(pd.Series([r.get("quote_usd_w")]), errors="coerce").iloc[0]
        matrix_raw = str(r.get("iec61853_matrix_file", "") or "").strip()
        rows.append({
            "module_id": r["module_id"],
            "manufacturer": r["manufacturer"],
            "model": r["model"],
            "electrical_model": policy["electrical_model"],
            "decision_evidence_ready": bool(policy["decision_eligible"]),
            "supplier_quote_ready": bool(np.isfinite(quote)),
            "iec61853_matrix_declared": bool(matrix_raw and matrix_raw.lower() != "nan"),
            "evidence_status": r.get("evidence_status", "user_supplied"),
        })
    return pd.DataFrame(rows)
