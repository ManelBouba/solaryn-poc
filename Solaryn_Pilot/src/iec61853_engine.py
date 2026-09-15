from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator


REQUIRED_MATRIX_COLUMNS = ["irradiance_w_m2", "module_temperature_c", "pmax_w"]
IEC_IRRADIANCE_REFERENCE_LEVELS = {100, 200, 400, 600, 800, 1000, 1100}
IEC_TEMPERATURE_REFERENCE_LEVELS = {15, 25, 50, 75}


@dataclass(frozen=True)
class MatrixValidation:
    measured_points: int
    irradiance_min_w_m2: float
    irradiance_max_w_m2: float
    temperature_min_c: float
    temperature_max_c: float
    has_stc_anchor: bool
    stc_relative_error_pct: float | None
    reference_irradiance_levels_present: tuple[float, ...]
    reference_temperature_levels_present: tuple[float, ...]
    source_status: str


def read_iec61853_matrix(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"IEC 61853 matrix file does not exist: {path}")
    df = pd.read_csv(path)
    return df


def validate_iec61853_matrix(
    matrix: pd.DataFrame,
    *,
    module_pmax_w: float | None = None,
    source_status: str = "module_specific_measured",
    require_minimum_points: int = 6,
) -> MatrixValidation:
    """Validate a module-specific IEC-61853-style G-T performance matrix.

    The function deliberately validates evidence and geometry, not just syntax.
    It accepts reduced matrices (minimum six well-chosen points), because the IEA
    Task 13 report notes that reduced matrices can preserve energy-rating accuracy
    when the points are well chosen. The caller must still expose the evidence
    grade and any extrapolation fraction in the final result.
    """
    if matrix is None or matrix.empty:
        raise ValueError("IEC 61853 performance matrix is empty.")
    missing = [c for c in REQUIRED_MATRIX_COLUMNS if c not in matrix.columns]
    if missing:
        raise ValueError(f"IEC 61853 matrix is missing columns: {missing}")

    m = matrix.copy()
    for col in REQUIRED_MATRIX_COLUMNS:
        m[col] = pd.to_numeric(m[col], errors="coerce")
    if m[REQUIRED_MATRIX_COLUMNS].isna().any().any():
        raise ValueError("IEC 61853 matrix contains non-numeric or missing G/T/Pmax values.")
    if (m["irradiance_w_m2"] < 0).any():
        raise ValueError("irradiance_w_m2 cannot be negative.")
    if (m["pmax_w"] < 0).any():
        raise ValueError("pmax_w cannot be negative.")
    if m.duplicated(["irradiance_w_m2", "module_temperature_c"]).any():
        raise ValueError("IEC 61853 matrix contains duplicate irradiance/temperature coordinates.")
    if len(m) < int(require_minimum_points):
        raise ValueError(
            f"At least {require_minimum_points} independent G-T points are required for a reduced matrix."
        )

    gmin = float(m["irradiance_w_m2"].min())
    gmax = float(m["irradiance_w_m2"].max())
    tmin = float(m["module_temperature_c"].min())
    tmax = float(m["module_temperature_c"].max())
    if gmax < 800 or gmin > 200:
        raise ValueError("Matrix does not span a useful low-to-high irradiance range.")
    if tmax < 50 or tmin > 25:
        raise ValueError("Matrix does not span a useful operating-temperature range.")

    stc_mask = np.isclose(m["irradiance_w_m2"], 1000.0, atol=1e-6) & np.isclose(
        m["module_temperature_c"], 25.0, atol=1e-6
    )
    has_stc = bool(stc_mask.any())
    stc_err: float | None = None
    if has_stc and module_pmax_w is not None and float(module_pmax_w) > 0:
        stc_p = float(m.loc[stc_mask, "pmax_w"].iloc[0])
        stc_err = 100.0 * abs(stc_p - float(module_pmax_w)) / float(module_pmax_w)
        if stc_err > 3.0:
            raise ValueError(
                f"Measured 1000 W/m², 25°C Pmax differs from module nameplate by {stc_err:.2f}%; "
                "verify module identity, stabilization state and units before using the matrix."
            )

    g_present = tuple(sorted(set(float(x) for x in m["irradiance_w_m2"].unique()) & IEC_IRRADIANCE_REFERENCE_LEVELS))
    t_present = tuple(sorted(set(float(x) for x in m["module_temperature_c"].unique()) & IEC_TEMPERATURE_REFERENCE_LEVELS))

    return MatrixValidation(
        measured_points=len(m),
        irradiance_min_w_m2=gmin,
        irradiance_max_w_m2=gmax,
        temperature_min_c=tmin,
        temperature_max_c=tmax,
        has_stc_anchor=has_stc,
        stc_relative_error_pct=stc_err,
        reference_irradiance_levels_present=g_present,
        reference_temperature_levels_present=t_present,
        source_status=str(source_status),
    )


def _build_interpolators(matrix: pd.DataFrame):
    points = matrix[["irradiance_w_m2", "module_temperature_c"]].to_numpy(dtype=float)
    values = matrix["pmax_w"].to_numpy(dtype=float)
    # Linear interpolation is used inside the measured convex hull. Nearest-neighbour
    # is ONLY a controlled fallback for holes/non-convex edges and is counted as a
    # model-evidence penalty in the returned diagnostics.
    linear = LinearNDInterpolator(points, values, fill_value=np.nan)
    nearest = NearestNDInterpolator(points, values)
    return linear, nearest


def interpolate_iec61853_pmax(
    matrix: pd.DataFrame,
    irradiance_w_m2: Iterable[float] | pd.Series,
    module_temperature_c: Iterable[float] | pd.Series,
) -> tuple[pd.Series, dict]:
    """Interpolate module Pmax over hourly G-T conditions.

    Policy:
    * G <= 0 -> P = 0.
    * Temperature outside the measured range is clipped to the measured range and
      counted as temperature extrapolation.
    * Irradiance below/above the measured envelope is evaluated at the envelope and
      scaled linearly with G; those hours are explicitly counted as irradiance
      extrapolation.
    * Holes inside the measured convex hull use nearest-neighbour fallback and are
      counted. No hidden technology coefficient is inserted.

    This is a transparent measured-matrix interpolation layer, not a claim of exact IEC 61853-3
    conformity. A production implementation should reproduce the standard's exact
    interpolation/extrapolation procedure and carry laboratory measurement uncertainty.
    """
    m = matrix.copy()
    for col in REQUIRED_MATRIX_COLUMNS:
        m[col] = pd.to_numeric(m[col], errors="coerce")
    validate_iec61853_matrix(m)

    g = pd.Series(pd.to_numeric(pd.Series(list(irradiance_w_m2)), errors="coerce"), dtype=float)
    t = pd.Series(pd.to_numeric(pd.Series(list(module_temperature_c)), errors="coerce"), dtype=float)
    if len(g) != len(t):
        raise ValueError("Irradiance and module-temperature arrays must have the same length.")
    if g.isna().any() or t.isna().any():
        raise ValueError("Hourly irradiance/temperature contains missing values.")

    gmin, gmax = float(m["irradiance_w_m2"].min()), float(m["irradiance_w_m2"].max())
    tmin, tmax = float(m["module_temperature_c"].min()), float(m["module_temperature_c"].max())
    daylight = g > 0
    g_low = daylight & (g < gmin)
    g_high = daylight & (g > gmax)
    t_out = daylight & ((t < tmin) | (t > tmax))

    g_eval = g.clip(lower=gmin, upper=gmax)
    t_eval = t.clip(lower=tmin, upper=tmax)
    linear, nearest = _build_interpolators(m)
    query = np.column_stack([g_eval.to_numpy(), t_eval.to_numpy()])
    p = np.asarray(linear(query), dtype=float)
    hole = daylight.to_numpy() & ~np.isfinite(p)
    if hole.any():
        p[hole] = np.asarray(nearest(query[hole]), dtype=float)

    # Linear irradiance scaling is only applied outside the measured irradiance
    # envelope; it is never used to create technology-specific low-light advantages.
    scale = np.ones(len(g), dtype=float)
    low_idx = g_low.to_numpy()
    high_idx = g_high.to_numpy()
    scale[low_idx] = g.to_numpy()[low_idx] / max(gmin, 1e-9)
    scale[high_idx] = g.to_numpy()[high_idx] / max(gmax, 1e-9)
    p = np.maximum(0.0, p * scale)
    p[~daylight.to_numpy()] = 0.0

    daylight_n = max(int(daylight.sum()), 1)
    diagnostics = {
        "matrix_hours_daylight": int(daylight.sum()),
        "matrix_irradiance_extrapolation_fraction_pct": 100.0 * float((g_low | g_high).sum()) / daylight_n,
        "matrix_temperature_extrapolation_fraction_pct": 100.0 * float(t_out.sum()) / daylight_n,
        "matrix_nearest_fallback_fraction_pct": 100.0 * float(hole.sum()) / daylight_n,
        "matrix_interpolation_policy": "linear_inside_measured_hull_explicit_envelope_extrapolation",
    }
    return pd.Series(p, index=getattr(irradiance_w_m2, "index", None)), diagnostics


def build_matrix_template() -> pd.DataFrame:
    rows = []
    for g in [100, 200, 400, 600, 800, 1000, 1100]:
        for t in [15, 25, 50, 75]:
            # IEC 61853-1 omits several extreme combinations. Template Pmax is blank;
            # never invent laboratory values.
            if (g == 1100 and t == 15) or (g == 400 and t == 75) or (g in {100, 200} and t in {50, 75}):
                continue
            rows.append({
                "irradiance_w_m2": g,
                "module_temperature_c": t,
                "pmax_w": np.nan,
                "measurement_uncertainty_pct": np.nan,
                "source_reference": "",
            })
    return pd.DataFrame(rows)
