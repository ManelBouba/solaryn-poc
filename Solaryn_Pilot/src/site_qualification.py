"""Climate/BOM qualification gates for product suitability.

Gates are evidence requirements, not hidden performance scores. Missing evidence
makes a candidate conditional or blocked only when the user explicitly requests a
hard gate. This avoids technology-family stereotypes such as 'HJT is humid-safe'.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Qualification:
    status: str
    t98_module_c: float
    temperature_level: str
    humidity_exposure: str
    salinity_exposure: str
    snow_exposure: str
    requirements: tuple[str, ...]
    satisfied: tuple[str, ...]
    missing: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self): return asdict(self)


def _text(module, key):
    v = module.get(key, "")
    return "" if pd.isna(v) else str(v)


def _has_cert(module, token: str) -> bool:
    blob = " ".join([
        _text(module, "certifications"), _text(module, "source_note"),
        _text(module, "verification_note"), _text(module, "bom_source_reference")
    ]).lower()
    return token.lower() in blob


def _bool_evidence(module, *keys) -> bool:
    for key in keys:
        v = module.get(key, None)
        if v is None or (isinstance(v, float) and math.isnan(v)): continue
        s = str(v).strip().lower()
        if s in {"1", "true", "yes", "verified", "reviewed", "pass", "passed", "available"}: return True
        if s and s not in {"0", "false", "no", "unknown", "nan", "none", "not_provided"}: return True
    return False


def classify_site_exposure(weather: pd.DataFrame, project: dict) -> dict:
    daylight = pd.to_numeric(weather.get("poa_w_m2", 0), errors="coerce").fillna(0) > 20
    rh = pd.to_numeric(weather.get("relative_humidity_pct", pd.Series(np.nan, index=weather.index)), errors="coerce")
    ta = pd.to_numeric(weather.get("temp_air_c", pd.Series(np.nan, index=weather.index)), errors="coerce")
    precip = pd.to_numeric(weather.get("rainfall_mm_hour", pd.Series(0.0, index=weather.index)), errors="coerce").fillna(0.0)
    humidity_high_fraction = float(((rh >= 80) & daylight).sum() / max(int(daylight.sum()), 1))
    humidity = "high" if humidity_high_fraction >= 0.25 else "moderate" if humidity_high_fraction >= 0.10 else "low"
    # Precipitation at/below 1 C is a conservative snow-potential proxy when direct snowfall data are absent.
    snow_proxy_mm = float(precip.where(ta <= 1.0, 0.0).sum())
    snow = "high" if snow_proxy_mm >= 100 else "moderate" if snow_proxy_mm >= 20 else "low"
    salinity = str(project.get("salinity_stress", "auto")).strip().lower()
    if salinity == "auto":
        salinity = "unknown"  # do not infer coastline from coordinates without a coastline dataset
    return {
        "humidity": humidity,
        "humidity_high_fraction": humidity_high_fraction,
        "snow": snow,
        "snowfall_water_equivalent_proxy_mm": snow_proxy_mm,
        "salinity": salinity,
    }


def qualification_for_candidate(module: pd.Series | dict, result: pd.Series | dict,
                                weather: pd.DataFrame, project: dict) -> Qualification:
    module = dict(module); result = dict(result)
    exposure = classify_site_exposure(weather, project)
    # IEC TS 63126 public scope defines T98 as the 98th-percentile module temperature
    # (175.2 h/year). Prefer the all-hours annual statistic. The daylight-only statistic
    # remains a diagnostic but is not represented as the IEC definition.
    t98 = float(result.get(
        "p98_module_temperature_c_all_hours",
        result.get("p98_module_temperature_c_daylight", result.get("p95_module_temperature_c_daylight", np.nan)),
    ))
    if not np.isfinite(t98):
        temp_level = "unknown"
    elif t98 <= 70: temp_level = "IEC base range (T98 ≤70°C)"
    elif t98 <= 80: temp_level = "IEC TS 63126 Level 1 evidence recommended"
    elif t98 <= 90: temp_level = "IEC TS 63126 Level 2 evidence recommended"
    else: temp_level = "above IEC TS 63126 Level 2 screening range"

    req=[]; sat=[]; miss=[]; reasons=[]
    if np.isfinite(t98) and t98 > 70:
        req.append("high_temperature_qualification")
        if _bool_evidence(module, "high_temperature_qualification_status") or _has_cert(module, "63126"):
            sat.append("high_temperature_qualification")
        else:
            miss.append("high_temperature_qualification")
            reasons.append(f"T98={t98:.1f}°C exceeds the 70°C base range; IEC TS 63126 evidence is not recorded.")

    if exposure["salinity"] in {"high", "very_high", "marine", "coastal"}:
        req.append("IEC_61701_salt_mist")
        if _has_cert(module, "61701") or _bool_evidence(module, "salt_mist_evidence"):
            sat.append("IEC_61701_salt_mist")
        else:
            miss.append("IEC_61701_salt_mist")
            reasons.append("High/coastal salinity was declared but IEC 61701 salt-mist evidence is not recorded.")

    if exposure["humidity"] == "high":
        req.append("damp_heat_or_BOM_humidity_evidence")
        # IEC 61215 qualification is useful evidence, but does not become a quantitative lifetime prediction.
        if _has_cert(module, "61215") or _bool_evidence(module, "damp_heat_evidence"):
            sat.append("damp_heat_or_BOM_humidity_evidence")
        else:
            miss.append("damp_heat_or_BOM_humidity_evidence")
            reasons.append("High humidity exposure requires recorded damp-heat/BOM evidence for a stronger claim.")

    if exposure["snow"] in {"high", "moderate"}:
        req.append("snow_mechanical_and_loss_review")
        # Mechanical load evidence is frequently recorded only in detailed datasheets; absence stays conditional.
        if _bool_evidence(module, "snow_load_evidence") or "snow" in _text(module, "source_note").lower():
            sat.append("snow_mechanical_and_loss_review")
        else:
            miss.append("snow_mechanical_and_loss_review")
            reasons.append("Snow potential detected; module mechanical snow-load evidence is not structured in the catalog.")

    hard = bool(project.get("hard_qualification_gates", False))
    if not req:
        status = "eligible"
    elif miss and hard:
        status = "blocked"
    elif miss:
        status = "conditional"
    else:
        status = "eligible"

    return Qualification(status=status, t98_module_c=t98, temperature_level=temp_level,
        humidity_exposure=exposure["humidity"], salinity_exposure=exposure["salinity"],
        snow_exposure=exposure["snow"], requirements=tuple(req), satisfied=tuple(sat),
        missing=tuple(miss), reasons=tuple(reasons))
