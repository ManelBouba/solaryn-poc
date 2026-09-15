from __future__ import annotations
import numpy as np
import pandas as pd


def fit_linear_resource_bias(satellite: pd.Series, measured: pd.Series) -> dict:
    """Fit y_meas = a + b*y_sat on timestamp-aligned irradiance data.

    Intended for site commissioning/validation only; coefficients must never be transferred
    blindly to another site.
    """
    x=pd.to_numeric(satellite,errors='coerce'); y=pd.to_numeric(measured,errors='coerce')
    m=x.notna()&y.notna()&(x>=0)&(y>=0)
    if m.sum()<30: raise ValueError('At least 30 aligned valid measurements are required.')
    b,a=np.polyfit(x[m].to_numpy(),y[m].to_numpy(),1)
    pred=a+b*x[m]
    e=pred-y[m]
    return {'intercept':float(a),'slope':float(b),'n':int(m.sum()),
            'rmse':float(np.sqrt(np.mean(e**2))),'mbe':float(np.mean(e)),
            'basis':'site_specific_linear_bias_correction_from_aligned_ground_measurements'}


def apply_resource_calibration(series: pd.Series, calibration: dict) -> pd.Series:
    x=pd.to_numeric(series,errors='coerce')
    return (float(calibration['intercept'])+float(calibration['slope'])*x).clip(lower=0.0)
