from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator


REQUIRED_OUTDOOR_COLUMNS = ("Date", "Time", "Pm", "Voc", "Isc", "Tbom", "Gpoa")
REQUIRED_MATRIX_COLUMNS = ("irradiance_w_m2", "module_temperature_c", "pmax_w")


def validate_iec61853_pmax_layer(
    data_dir: str | Path,
    matrix_path: str | Path,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Evaluate the measured IEC 61853 Pmax G-T interpolation layer.

    Outdoor measured in-plane irradiance and back-of-module temperature are used
    directly. Consequently, this function validates the interpolation layer only;
    it does not validate climate, transposition, thermal, spectral or degradation
    models.
    """
    data_dir = Path(data_dir)
    matrix = pd.read_csv(matrix_path)
    missing_matrix = [c for c in REQUIRED_MATRIX_COLUMNS if c not in matrix.columns]
    if missing_matrix:
        raise ValueError("IEC 61853 matrix is missing columns: " + ", ".join(missing_matrix))

    points = matrix[["irradiance_w_m2", "module_temperature_c"]].to_numpy(float)
    values = matrix["pmax_w"].to_numpy(float)
    linear = LinearNDInterpolator(points, values, fill_value=np.nan)
    nearest = NearestNDInterpolator(points, values)

    frames: list[pd.DataFrame] = []
    for path in sorted(data_dir.glob("*.csv")):
        frame = pd.read_csv(path, sep=";")
        frame.columns = [str(c).strip() for c in frame.columns]
        missing = [c for c in REQUIRED_OUTDOOR_COLUMNS if c not in frame.columns]
        if missing:
            raise ValueError(f"{path.name} is missing outdoor columns: {', '.join(missing)}")
        frame["source_file"] = path.name
        frames.append(frame)
    if not frames:
        raise ValueError("No monthly outdoor CSV files were found.")

    raw = pd.concat(frames, ignore_index=True)
    raw["timestamp"] = pd.to_datetime(
        raw["Date"].astype(str).str.strip() + " " + raw["Time"].astype(str).str.strip(),
        dayfirst=True,
        errors="coerce",
    )
    for column in ("Pm", "Voc", "Isc", "Tbom", "Gpoa"):
        raw[column] = pd.to_numeric(raw[column], errors="coerce")

    complete = raw.dropna(subset=["timestamp", "Pm", "Voc", "Isc", "Tbom", "Gpoa"]).copy()
    physical = (
        complete["Pm"].ge(0)
        & complete["Voc"].gt(0)
        & complete["Isc"].gt(0)
        & complete["Gpoa"].gt(0)
        & complete["Pm"].le(complete["Voc"] * complete["Isc"] * 1.000001)
    )
    g_min, g_max = matrix["irradiance_w_m2"].min(), matrix["irradiance_w_m2"].max()
    t_min, t_max = matrix["module_temperature_c"].min(), matrix["module_temperature_c"].max()
    retained = complete.loc[
        physical
        & complete["Gpoa"].between(g_min, g_max)
        & complete["Tbom"].between(t_min, t_max)
    ].copy()

    query = np.column_stack([retained["Gpoa"].to_numpy(), retained["Tbom"].to_numpy()])
    prediction = np.asarray(linear(query), dtype=float)
    fallback = ~np.isfinite(prediction)
    prediction[fallback] = np.asarray(nearest(query[fallback]), dtype=float)
    retained["predicted_pmax_w"] = prediction
    retained["error_w"] = retained["predicted_pmax_w"] - retained["Pm"]
    retained["nearest_fallback"] = fallback
    retained["month"] = retained["timestamp"].dt.to_period("M").astype(str)

    stc_rows = matrix.loc[
        matrix["irradiance_w_m2"].eq(1000) & matrix["module_temperature_c"].eq(25),
        "pmax_w",
    ]
    if len(stc_rows) != 1:
        raise ValueError("IEC 61853 matrix must contain exactly one 1000 W/m2, 25 C STC point.")
    stc_pmax = float(stc_rows.iloc[0])
    errors = retained["error_w"].to_numpy(float)
    measured = retained["Pm"].to_numpy(float)
    predicted = retained["predicted_pmax_w"].to_numpy(float)
    rmse = float(np.sqrt(np.mean(errors**2)))
    mbe = float(np.mean(errors))
    r2 = float(1 - np.sum(errors**2) / np.sum((measured - np.mean(measured)) ** 2))
    energy_bias = float((np.sum(predicted) / np.sum(measured) - 1) * 100)

    summary = {
        "validation_scope": "iec61853_measured_pmax_gt_interpolation_layer_only",
        "status": "PASS_EXTERNAL_MEASURED_LAYER",
        "raw_rows": int(len(raw)),
        "complete_rows": int(len(complete)),
        "excluded_physical_rows": int((~physical).sum()),
        "retained_rows": int(len(retained)),
        "nearest_fallback_rows": int(fallback.sum()),
        "reference_stc_pmax_w": stc_pmax,
        "rmse_w": rmse,
        "rmse_pct_stc": 100 * rmse / stc_pmax,
        "mbe_w": mbe,
        "mbe_pct_stc": 100 * mbe / stc_pmax,
        "r2": r2,
        "cumulative_sampled_energy_bias_pct": energy_bias,
        "source": "IEA PVPS Task 13 / SUPSI PVLab via Sandia PVPMC",
        "full_decision_engine_validated": False,
        "commercial_candidate_specific_validation": False,
    }

    monthly = retained.groupby("month", as_index=False).agg(
        retained_points=("Pm", "size"),
        measured_power_sum_w=("Pm", "sum"),
        predicted_power_sum_w=("predicted_pmax_w", "sum"),
        squared_error_sum_w2=("error_w", lambda s: float(np.sum(np.square(s)))),
        error_sum_w=("error_w", "sum"),
        fallback_points=("nearest_fallback", "sum"),
    )
    monthly["rmse_w"] = np.sqrt(monthly["squared_error_sum_w2"] / monthly["retained_points"])
    monthly["mbe_w"] = monthly["error_sum_w"] / monthly["retained_points"]
    monthly["energy_bias_pct"] = (
        monthly["predicted_power_sum_w"] / monthly["measured_power_sum_w"] - 1
    ) * 100
    return summary, monthly, retained
