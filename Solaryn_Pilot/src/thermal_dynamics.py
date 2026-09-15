from __future__ import annotations
import math
import numpy as np
import pandas as pd


def ewm_alpha(dt_seconds: float, tau_seconds: float) -> float:
    """Discrete first-order thermal response coefficient: alpha = 1-exp(-dt/tau)."""
    dt=max(float(dt_seconds),1e-9); tau=max(float(tau_seconds),1e-9)
    return 1.0-math.exp(-dt/tau)


def first_order_filter(values, dt_seconds: float, tau_seconds: float, initial=None) -> pd.Series:
    """Causal first-order low-pass filter used to represent PV module thermal inertia."""
    s=pd.Series(values,dtype=float)
    if s.empty: return s
    a=ewm_alpha(dt_seconds,tau_seconds)
    out=np.empty(len(s),dtype=float)
    x=s.to_numpy(dtype=float)
    finite=np.flatnonzero(np.isfinite(x))
    if len(finite)==0:
        return pd.Series(np.nan,index=s.index,dtype=float)
    first=int(finite[0]); state=float(x[first] if initial is None else initial)
    out[:first]=state
    for i in range(first,len(x)):
        if np.isfinite(x[i]): state=state+a*(float(x[i])-state)
        out[i]=state
    return pd.Series(out,index=s.index,dtype=float)


def dynamic_faiman_temperature(poa_w_m2, temp_air_c, wind_speed_m_s, *, u0=25.0, u1=6.84,
                               dt_seconds=60.0, tau_minutes=6.3) -> pd.Series:
    """Dynamic Faiman model.

    Following the KU Leuven thermal-inertia concept, irradiance and wind are filtered
    with a first-order time constant before evaluating the static Faiman equation.
    Default tau=6.3 min is the cross-site fixed-mount mean reported by Herteleer et al.
    It is a literature prior, not a site calibration.
    """
    g=pd.Series(poa_w_m2,dtype=float).clip(lower=0).fillna(0.0)
    ta=pd.Series(temp_air_c,dtype=float).interpolate(limit_direction='both')
    ws=pd.Series(wind_speed_m_s,dtype=float).clip(lower=0).interpolate(limit_direction='both').fillna(0.0)
    tau=float(tau_minutes)*60.0
    gf=first_order_filter(g,dt_seconds,tau)
    wf=first_order_filter(ws,dt_seconds,tau)
    denom=(float(u0)+float(u1)*wf).clip(lower=1e-9)
    return ta+gf/denom


def dynamic_sandia_cell_temperature(poa_w_m2, temp_air_c, wind_speed_m_s, *, a=-3.56,b=-0.075,
                                    delta_t=3.0,dt_seconds=60.0,tau_minutes=6.3) -> pd.Series:
    g=pd.Series(poa_w_m2,dtype=float).clip(lower=0).fillna(0.0)
    ta=pd.Series(temp_air_c,dtype=float).interpolate(limit_direction='both')
    ws=pd.Series(wind_speed_m_s,dtype=float).clip(lower=0).interpolate(limit_direction='both').fillna(0.0)
    tau=float(tau_minutes)*60.0
    gf=first_order_filter(g,dt_seconds,tau)
    wf=first_order_filter(ws,dt_seconds,tau)
    tm=gf*np.exp(float(a)+float(b)*wf)+ta
    return tm+(gf/1000.0)*float(delta_t)
