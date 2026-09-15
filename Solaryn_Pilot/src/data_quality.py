from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd


MODULE_REQUIRED_FIELDS = [
    "module_id", "technology_id", "manufacturer", "model", "technology_label",
    "pmax_w", "vmp_v", "imp_a", "voc_v", "isc_a", "module_area_m2",
    "module_efficiency_pct", "gamma_pmax_pct_c", "source_url", "evidence_status",
]

TECHNOLOGY_REQUIRED_FIELDS = [
    "technology_id", "technology_name", "family", "commercialization_status",
    "TRL_level", "source_url", "source_quality", "record_kind", "decision_role",
]


def _missing(frame: pd.DataFrame, fields: list[str]) -> list[str]:
    return [c for c in fields if c not in frame.columns]


def validate_module_catalog(frame: pd.DataFrame) -> list[str]:
    """Return actionable data-quality issues for the commercial candidate catalog."""
    issues: list[str] = []
    missing = _missing(frame, MODULE_REQUIRED_FIELDS)
    if missing:
        return ["Missing required module fields: " + ", ".join(missing)]
    if frame["module_id"].astype(str).duplicated().any():
        issues.append("module_id must be unique.")

    numeric = ["pmax_w", "vmp_v", "imp_a", "voc_v", "isc_a", "module_area_m2", "module_efficiency_pct"]
    for col in numeric:
        values = pd.to_numeric(frame[col], errors="coerce")
        if not np.isfinite(values).all() or (values <= 0).any():
            issues.append(f"{col} must be finite and positive for every commercial candidate.")

    for _, row in frame.iterrows():
        mid = str(row["module_id"])
        try:
            p = float(row["pmax_w"])
            p_vi = float(row["vmp_v"]) * float(row["imp_a"])
            if abs(p_vi - p) / max(p, 1e-9) > 0.02:
                issues.append(f"{mid}: Pmax differs from Vmp×Imp by more than 2%.")
            if not float(row["vmp_v"]) < float(row["voc_v"]):
                issues.append(f"{mid}: Vmp must be below Voc.")
            if not float(row["imp_a"]) < float(row["isc_a"]):
                issues.append(f"{mid}: Imp must be below Isc.")
            if not -2.0 < float(row["gamma_pmax_pct_c"]) < 0.0:
                issues.append(f"{mid}: gamma_pmax_pct_c is outside the expected negative range.")
        except (TypeError, ValueError):
            pass
        url = str(row.get("source_url", "")).strip()
        if not url.startswith(("https://", "http://")):
            issues.append(f"{mid}: source_url is missing or invalid.")
        if "bifaciality_factor" in frame.columns:
            try:
                bf = float(row.get("bifaciality_factor", 0.0) or 0.0)
            except (TypeError, ValueError):
                bf = float("nan")
            if not math.isfinite(bf) or bf < 0.0 or bf > 1.2:
                issues.append(f"{mid}: bifaciality_factor must be finite and in [0, 1.2].")
            label = str(row.get("technology_label", "")).lower()
            if "bifacial" in label and bf <= 0:
                issues.append(f"{mid}: bifacial candidate requires a sourced positive bifaciality_factor.")
            if bf > 0 and not str(row.get("bifaciality_source", "")).strip():
                issues.append(f"{mid}: positive bifaciality_factor requires bifaciality_source provenance.")
    return issues


def validate_technology_catalog(frame: pd.DataFrame) -> list[str]:
    """Return structural issues for the research technology catalog."""
    issues: list[str] = []
    missing = _missing(frame, TECHNOLOGY_REQUIRED_FIELDS)
    if missing:
        return ["Missing required technology fields: " + ", ".join(missing)]
    if frame["technology_id"].astype(str).duplicated().any():
        issues.append("technology_id must be unique.")
    allowed_kind = {"technology_family", "module_variant"}
    invalid = sorted(set(frame["record_kind"].dropna().astype(str)) - allowed_kind)
    if invalid:
        issues.append("Unsupported record_kind values: " + ", ".join(invalid))
    if not frame["decision_role"].astype(str).eq("research_screening_only").all():
        issues.append("Technology catalog must remain research_screening_only; procurement decisions use module candidates.")
    return issues


def audit_packaged_data(root: str | Path) -> dict:
    root = Path(root)
    modules = pd.read_csv(root / "data/raw/module_candidate_master.csv")
    tech = pd.read_csv(root / "data/raw/technology_master.csv")
    module_issues = validate_module_catalog(modules)
    technology_issues = validate_technology_catalog(tech)
    return {
        "module_catalog_rows": int(len(modules)),
        "technology_catalog_rows": int(len(tech)),
        "module_catalog_issues": module_issues,
        "technology_catalog_issues": technology_issues,
        "pass": not module_issues and not technology_issues,
    }


if __name__ == "__main__":
    import json

    report = audit_packaged_data(Path(__file__).resolve().parents[1])
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["pass"] else 1)
