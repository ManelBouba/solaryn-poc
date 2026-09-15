from __future__ import annotations

"""Leakage-safe calibration and validation for SOLARYN dynamic Faiman thermal physics.

The calibration routine is deliberately chronological: an early training period is used
for parameter estimation and a later holdout period is never used by the optimizer.
This prevents the KU Leuven benchmark from becoming a fitted-in-sample validation.
"""

from dataclasses import dataclass, asdict
import math
from typing import Any

import numpy as np
import pandas as pd

from .thermal_dynamics import dynamic_faiman_temperature


@dataclass(frozen=True)
class ThermalCalibrationResult:
    u0: float
    u1: float
    tau_minutes: float
    train_start: str
    train_end: str
    holdout_start: str
    holdout_end: str
    train_n: int
    holdout_n: int
    train_metrics: dict[str, float]
    holdout_metrics: dict[str, float]
    baseline_holdout_metrics: dict[str, float]
    improvement: dict[str, float]
    site_bias_correction_k: float = 0.0
    fit_target: str = "cell_temperature"
    method: str = "chronological_holdout_scipy_least_squares_plus_train_only_bias"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    m=np.isfinite(y)&np.isfinite(p)
    y=np.asarray(y,float)[m]; p=np.asarray(p,float)[m]
    if len(y)==0:
        return {"n":0,"rmse_k":math.nan,"mae_k":math.nan,"mbe_k":math.nan,"r2":math.nan}
    e=p-y
    rmse=float(np.sqrt(np.mean(e*e)))
    mae=float(np.mean(np.abs(e)))
    mbe=float(np.mean(e))
    syy=float(np.sum((y-y.mean())**2))
    r2=float(1.0-np.sum(e*e)/syy) if syy>0 else math.nan
    return {"n":int(len(y)),"rmse_k":rmse,"mae_k":mae,"mbe_k":mbe,"r2":r2}


def chronological_split(df: pd.DataFrame, train_fraction: float=0.70, gap_minutes: int=1440):
    """Split by time, with an optional gap to reduce serial leakage around the boundary."""
    x=df.sort_index()
    if not isinstance(x.index,pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")
    if not 0.5 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be between 0.5 and 0.9")
    unique_days=pd.Index(x.index.normalize().unique()).sort_values()
    if len(unique_days)<10:
        raise ValueError("At least 10 distinct days are required for calibration/holdout validation")
    cut=max(1,min(len(unique_days)-2,int(len(unique_days)*train_fraction)))
    train_end=pd.Timestamp(unique_days[cut-1])+pd.Timedelta(days=1)
    holdout_start=train_end+pd.Timedelta(minutes=max(0,int(gap_minutes)))
    train=x[x.index < train_end]
    holdout=x[x.index >= holdout_start]
    if train.empty or holdout.empty:
        raise ValueError("Chronological split produced an empty train or holdout set")
    return train,holdout


def _predict(df: pd.DataFrame, u0: float, u1: float, tau_minutes: float, dt_seconds: float=60.0) -> np.ndarray:
    return dynamic_faiman_temperature(
        df["G_Pyr_18_S"],df["Tamb"],df["WS"],
        u0=float(u0),u1=float(u1),dt_seconds=float(dt_seconds),tau_minutes=float(tau_minutes)
    ).to_numpy(float)


def calibrate_dynamic_faiman(
    df: pd.DataFrame,
    *,
    target_col: str="PV052_5x4C",
    train_fraction: float=0.70,
    gap_minutes: int=1440,
    baseline_u0: float=25.0,
    baseline_u1: float=6.84,
    baseline_tau_minutes: float=6.3,
    bounds=((15.0,40.0),(0.0,15.0),(1.0,30.0)),
    optimization_resample: str="5min",
) -> tuple[ThermalCalibrationResult,pd.DataFrame]:
    """Calibrate U0/U1/tau on training data only and evaluate on untouched holdout data.

    The optimizer sees only the training interval. The holdout is evaluated once with the
    final parameters. Bounds are intentionally physical/conservative and should be changed
    only with documented module/mounting evidence.
    """
    req={"Tamb","G_Pyr_18_S","WS",target_col}
    missing=req-set(df.columns)
    if missing: raise ValueError(f"Missing required columns: {sorted(missing)}")
    x=df[list(req)].copy().replace([np.inf,-np.inf],np.nan).dropna()
    x["G_Pyr_18_S"]=x["G_Pyr_18_S"].clip(lower=0)
    x["WS"]=x["WS"].clip(lower=0)
    train,holdout=chronological_split(x,train_fraction=train_fraction,gap_minutes=gap_minutes)

    # Reduce optimizer cost without contaminating the untouched 1-min holdout evaluation.
    opt=train.resample(optimization_resample).mean().dropna()
    try:
        from scipy.optimize import least_squares
    except Exception as exc:
        raise RuntimeError("scipy is required for thermal parameter calibration") from exc

    y=opt[target_col].to_numpy(float)
    def residual(theta):
        u0,u1,tau=map(float,theta)
        return _predict(opt,u0,u1,tau)-y
    lo=np.array([b[0] for b in bounds],float); hi=np.array([b[1] for b in bounds],float)
    x0=np.array([baseline_u0,baseline_u1,baseline_tau_minutes],float)
    x0=np.minimum(np.maximum(x0,lo+1e-8),hi-1e-8)
    fit=least_squares(residual,x0=x0,bounds=(lo,hi),loss="soft_l1",f_scale=1.0,max_nfev=250)
    u0,u1,tau=map(float,fit.x)

    pred_train_raw=_predict(train,u0,u1,tau)
    # Site-specific residual bias is estimated from TRAINING ONLY. It is not transferable
    # to other sites/modules and is reported separately from the physical U0/U1/tau fit.
    train_y=train[target_col].to_numpy(float)
    site_bias=float(np.nanmean(train_y-pred_train_raw))
    pred_train=pred_train_raw+site_bias
    pred_hold=_predict(holdout,u0,u1,tau)+site_bias
    base_hold=_predict(holdout,baseline_u0,baseline_u1,baseline_tau_minutes)
    mt=_metrics(train_y,pred_train)
    mh=_metrics(holdout[target_col].to_numpy(float),pred_hold)
    mb=_metrics(holdout[target_col].to_numpy(float),base_hold)
    improvement={
        "holdout_rmse_reduction_k": float(mb["rmse_k"]-mh["rmse_k"]),
        "holdout_rmse_reduction_pct": float(100*(mb["rmse_k"]-mh["rmse_k"])/mb["rmse_k"]) if mb["rmse_k"] else math.nan,
        "holdout_abs_mbe_reduction_k": float(abs(mb["mbe_k"])-abs(mh["mbe_k"])),
    }
    result=ThermalCalibrationResult(
        u0=u0,u1=u1,tau_minutes=tau,
        train_start=str(train.index.min()),train_end=str(train.index.max()),
        holdout_start=str(holdout.index.min()),holdout_end=str(holdout.index.max()),
        train_n=len(train),holdout_n=len(holdout),train_metrics=mt,holdout_metrics=mh,
        baseline_holdout_metrics=mb,improvement=improvement,site_bias_correction_k=site_bias
    )
    out=holdout.copy()
    out["pred_dynamic_faiman_baseline_c"]=base_hold
    out["pred_dynamic_faiman_calibrated_c"]=pred_hold
    out["site_bias_correction_k"]=site_bias
    out["residual_baseline_k"]=base_hold-out[target_col].to_numpy(float)
    out["residual_calibrated_k"]=pred_hold-out[target_col].to_numpy(float)
    return result,out
