from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


DECISION_VALID_CEC_CELL_TYPES = {"monosi", "multisi", "polysi"}
DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT = 2.0


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and np.isnan(value):
        return False
    return bool(str(value).strip())


def matrix_path_for_module(row: pd.Series, root: str | Path | None = None) -> Path | None:
    raw = row.get("iec61853_matrix_file", "")
    if not _nonempty(raw):
        return None
    p = Path(str(raw))
    if not p.is_absolute() and root is not None:
        p = Path(root) / p
    return p


def electrical_model_policy(row: pd.Series, root: str | Path | None = None) -> dict:
    """Select the least-assumptive electrical model supported by evidence.

    Order of evidence:
      1. module-specific measured IEC 61853 matrix;
      2. datasheet-fitted CEC SDM for crystalline-silicon families;
      3. exploratory CEC SDM for other families, explicitly barred from a robust
         cross-technology winner until matrix/validated model evidence is supplied.
    """
    matrix_path = matrix_path_for_module(row, root)
    if matrix_path is not None and matrix_path.exists():
        return {
            "electrical_model": "iec61853_module_specific_matrix",
            "decision_eligible": True,
            "model_evidence_level": "module_specific_measured_matrix",
            "model_form_warning": "",
            "matrix_path": str(matrix_path),
        }

    celltype = str(row.get("cec_celltype", "")).strip().lower()
    if celltype in DECISION_VALID_CEC_CELL_TYPES:
        return {
            "electrical_model": "cec_single_diode_datasheet_fit",
            "decision_eligible": True,
            "model_evidence_level": "datasheet_fit_crystalline_silicon_fallback",
            "model_form_warning": (
                "No module-specific IEC 61853 G-T matrix: decision uses a datasheet-fitted "
                "single-diode model and must retain an uncertainty guardrail."
            ),
            "matrix_path": None,
        }

    return {
        "electrical_model": "cec_single_diode_exploratory_only",
        "decision_eligible": False,
        "model_evidence_level": "technology_model_not_validated_for_this_module",
        "model_form_warning": (
            "No module-specific IEC 61853 matrix or validated device-specific model. "
            "This candidate may be displayed as exploratory but cannot determine the robust winner."
        ),
        "matrix_path": None,
    }


def spectral_evidence_policy(row: pd.Series) -> dict:
    """Declare whether spectral correction may influence the primary decision.

    V9 deliberately fails closed. A label such as ``module_specific_eqe`` is not
    enough by itself: EQE must be coupled to time-resolved spectral irradiance (or a
    validated module-specific spectral correction model) before it can alter energy.
    The current PoC implements only pvlib's technology-class First Solar proxy, so
    every spectral result is a sensitivity, never a primary winner-making term.
    """
    status = str(row.get("spectral_evidence_level", "technology_class_proxy")).strip().lower()
    if status in {"module_specific_eqe", "module_specific_spectral_response", "validated_module_specific"}:
        return {
            "spectral_decision_eligible": False,
            "spectral_evidence_level": status,
            "spectral_policy": "module_specific_spectral_evidence_declared_but_time_resolved_spectral_engine_not_yet_implemented",
        }
    return {
        "spectral_decision_eligible": False,
        "spectral_evidence_level": status or "technology_class_proxy",
        "spectral_policy": "technology_class_proxy_is_sensitivity_only",
    }


def thermal_evidence_policy(row: pd.Series) -> dict:
    u0 = pd.to_numeric(pd.Series([row.get("thermal_u0_w_m2k")]), errors="coerce").iloc[0]
    u1 = pd.to_numeric(pd.Series([row.get("thermal_u1_w_s_m3k")]), errors="coerce").iloc[0]
    if np.isfinite(u0) and np.isfinite(u1) and u0 > 0 and u1 >= 0:
        return {
            "thermal_model": "Faiman IEC-61853 module-specific coefficients",
            "thermal_evidence_level": "module_specific_u0_u1",
            "u0": float(u0),
            "u1": float(u1),
        }
    return {
        "thermal_model": "SAPM construction-class proxy",
        "thermal_evidence_level": "generic_construction_proxy",
        "u0": None,
        "u1": None,
    }


def project_segment_compatible(row: pd.Series, project_segment: str) -> bool:
    project = str(project_segment).strip().lower()
    raw = str(row.get("project_segment", "all")).strip().lower()
    if not raw or raw == "nan" or raw == "all":
        return True
    tokens = {x.strip() for x in raw.replace(";", ",").split(",") if x.strip()}
    aliases = {
        "commercial": {"commercial", "c&i", "commercial_industrial"},
        "c&i": {"commercial", "c&i", "commercial_industrial"},
        "utility": {"utility", "utility_scale"},
        "residential": {"residential", "rooftop"},
        "rooftop": {"residential", "rooftop", "commercial", "c&i"},
        "research": tokens | {project},
    }
    accepted = aliases.get(project, {project})
    return bool(tokens & accepted)


def add_evidence_columns(modules: pd.DataFrame, root: str | Path | None = None) -> pd.DataFrame:
    out = modules.copy()
    rows = []
    for _, row in out.iterrows():
        e = electrical_model_policy(row, root)
        s = spectral_evidence_policy(row)
        t = thermal_evidence_policy(row)
        rows.append({**e, **s, **t})
    meta = pd.DataFrame(rows, index=out.index)
    for col in meta.columns:
        out[col] = meta[col]
    return out
