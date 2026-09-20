"""Evidence hierarchy and claim-strength utilities for SOLARYN.

This module keeps evidence quality separate from the physics result. Evidence can
widen uncertainty, block a claim, or mark a candidate conditional; it must never
silently add an arbitrary performance bonus.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import pandas as pd

EVIDENCE_LEVELS = {
    "A": "measured product-specific / independent laboratory or field evidence",
    "B": "manufacturer product-specific evidence or certification",
    "C": "technology-family literature / proxy model",
    "D": "SOLARYN fallback assumption",
}

@dataclass(frozen=True)
class EvidenceAssessment:
    grade: str
    score: int
    electrical: str
    thermal: str
    spectral: str
    bom: str
    degradation: str
    qualification: str
    gaps: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _nonblank(value) -> bool:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    s = str(value).strip()
    return bool(s and s.lower() not in {"nan", "none", "unknown", "not_provided"})


def _grade_from_score(score: float) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 55: return "C"
    return "D"


def assess_candidate_evidence(module: pd.Series | dict, result: pd.Series | dict | None = None,
                              qualification_status: str = "not_checked") -> EvidenceAssessment:
    m = dict(module)
    r = dict(result or {})
    gaps: list[str] = []

    electrical_model = str(r.get("electrical_model", "")).lower()
    model_level = str(r.get("model_evidence_level", "")).lower()
    if "iec61853" in electrical_model and ("measured" in model_level or "module_specific" in model_level):
        electrical, e_score = "A", 100
    elif _nonblank(m.get("electrical_model_validation_reference")):
        electrical, e_score = "A", 92
    elif "cec" in electrical_model or _nonblank(m.get("source_url")):
        electrical, e_score = "B", 74
        gaps.append("No product-specific measured off-STC P(G,T) matrix / independent model validation.")
    else:
        electrical, e_score = "D", 35
        gaps.append("Electrical model evidence is only a fallback assumption.")

    thermal_level = str(r.get("thermal_evidence_level", "")).lower()
    if any(x in thermal_level for x in ("measured", "module_specific", "validated")):
        thermal, t_score = "A", 92
    elif _nonblank(m.get("noct_c")) or _nonblank(m.get("thermal_construction")):
        thermal, t_score = "B", 70
        gaps.append("Thermal behavior uses datasheet/construction evidence rather than measured project calibration.")
    else:
        thermal, t_score = "D", 35
        gaps.append("Thermal behavior uses a generic fallback.")

    spectral_level = str(r.get("spectral_evidence_level", m.get("spectral_evidence_level", ""))).lower()
    if any(x in spectral_level for x in ("module_specific", "measured", "validated")):
        spectral, s_score = "A", 95
    elif _nonblank(m.get("spectral_response_file")):
        spectral, s_score = "B", 80
    elif "technology" in spectral_level or "proxy" in spectral_level:
        spectral, s_score = "C", 58
        gaps.append("Spectral behavior is a technology-class proxy/sensitivity, not product-specific evidence.")
    else:
        spectral, s_score = "D", 40
        gaps.append("No product-specific spectral response evidence.")

    bom_status = str(m.get("bom_evidence_status", "")).lower()
    if any(x in bom_status for x in ("reviewed", "verified", "product_specific")) or _nonblank(m.get("bom_source_reference")):
        bom, b_score = "B", 80
    else:
        bom, b_score = "D", 40
        gaps.append("BOM evidence is incomplete; reliability claims must remain conditional.")

    degr_status = str(m.get("degradation_evidence_status", "")).lower()
    field_rate = pd.to_numeric(pd.Series([m.get("field_validated_degradation_pct_year")]), errors="coerce").iloc[0]
    if pd.notna(field_rate) and any(x in degr_status for x in ("field", "validated", "measured")):
        degradation, d_score = "A", 100
    elif _nonblank(m.get("annual_warranty_degradation_pct_year")):
        degradation, d_score = "B", 68
        gaps.append("Warranty degradation is a sensitivity, not a field lifetime prediction.")
    else:
        degradation, d_score = "D", 35
        gaps.append("No candidate-specific field degradation evidence.")

    q = str(qualification_status).lower()
    if q in {"eligible", "pass", "verified"}:
        qualification, q_score = "B", 85
    elif q in {"conditional", "evidence_gap", "not_checked"}:
        qualification, q_score = "C", 55
    elif q in {"blocked", "fail"}:
        qualification, q_score = "D", 20
    else:
        qualification, q_score = "C", 55

    # Weighted evidence score. This changes claim strength/uncertainty, not predicted energy.
    score = round(0.35*e_score + 0.15*t_score + 0.10*s_score + 0.15*b_score + 0.15*d_score + 0.10*q_score)
    return EvidenceAssessment(
        grade=_grade_from_score(score), score=int(score), electrical=electrical,
        thermal=thermal, spectral=spectral, bom=bom, degradation=degradation,
        qualification=qualification, gaps=tuple(dict.fromkeys(gaps)),
    )
