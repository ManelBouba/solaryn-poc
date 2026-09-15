from __future__ import annotations
import math
import numpy as np
import pandas as pd


def apply_dc_array_losses(module_mpp_kw: pd.Series,
                          mismatch_loss_pct: float = 1.5,
                          dc_wiring_loss_pct: float = 1.5,
                          availability: pd.Series | float = 1.0) -> pd.Series:
    """Aggregate module/string DC output to array DC with explicit mismatch and wiring losses."""
    p = pd.to_numeric(module_mpp_kw, errors="coerce").fillna(0.0).clip(lower=0.0)
    mm = np.clip(float(mismatch_loss_pct)/100.0, 0.0, 0.5)
    wire = np.clip(float(dc_wiring_loss_pct)/100.0, 0.0, 0.5)
    av = availability if isinstance(availability, pd.Series) else pd.Series(float(availability), index=p.index)
    av = pd.to_numeric(av, errors="coerce").fillna(1.0).clip(0.0,1.0)
    return p * (1-mm) * (1-wire) * av


def inverter_ac_power_kw(dc_kw: pd.Series,
                         ac_rating_kw: float,
                         nominal_efficiency: float = 0.975,
                         night_tare_kw: float = 0.0,
                         temp_air_c: pd.Series | None = None,
                         derate_start_c: float = 45.0,
                         derate_pct_per_c: float = 0.005) -> pd.Series:
    """Evidence-transparent inverter model with load curve, clipping and optional heat derating.

    If detailed Sandia/CEC inverter parameters are available they should replace this fallback.
    """
    pdc = pd.to_numeric(dc_kw, errors="coerce").fillna(0.0).clip(lower=0.0)
    pac0 = max(float(ac_rating_kw), 1e-9)
    load = (pdc / pac0).clip(lower=0.0)
    # Smooth part-load efficiency curve: lower at very low load, near nominal around 30-100%.
    eta = float(nominal_efficiency) - 0.035*np.exp(-8.0*load)
    eta = eta.clip(lower=0.80, upper=min(0.995, float(nominal_efficiency)+0.01))
    raw = pdc * eta
    if temp_air_c is not None:
        t = pd.to_numeric(temp_air_c, errors="coerce").fillna(25.0)
        der = (1.0 - np.maximum(t-float(derate_start_c),0.0)*float(derate_pct_per_c)).clip(0.70,1.0)
        raw = raw*der
    pac = raw.clip(upper=pac0)
    pac = (pac - float(night_tare_kw)).clip(lower=0.0)
    return pac


def apply_ac_delivery_losses(ac_kw: pd.Series,
                             transformer_loss_pct: float = 1.0,
                             ac_wiring_loss_pct: float = 0.5,
                             grid_availability: pd.Series | float = 1.0,
                             curtailment_factor: pd.Series | float = 1.0) -> pd.Series:
    p = pd.to_numeric(ac_kw, errors="coerce").fillna(0.0).clip(lower=0.0)
    fixed = (1-np.clip(float(transformer_loss_pct)/100.0,0,0.5))*(1-np.clip(float(ac_wiring_loss_pct)/100.0,0,0.5))
    ga = grid_availability if isinstance(grid_availability,pd.Series) else pd.Series(float(grid_availability), index=p.index)
    cf = curtailment_factor if isinstance(curtailment_factor,pd.Series) else pd.Series(float(curtailment_factor), index=p.index)
    return p*fixed*pd.to_numeric(ga,errors='coerce').fillna(1).clip(0,1)*pd.to_numeric(cf,errors='coerce').fillna(1).clip(0,1)


def annual_system_from_specific_dc(annual_dc_kwh_kwp: float,
                                   dc_ac_ratio: float = 1.25,
                                   mismatch_loss_pct: float = 1.5,
                                   dc_wiring_loss_pct: float = 1.5,
                                   inverter_efficiency: float = 0.975,
                                   transformer_loss_pct: float = 1.0,
                                   ac_wiring_loss_pct: float = 0.5,
                                   availability_pct: float = 99.0,
                                   curtailment_pct: float = 0.0,
                                   clipping_loss_pct: float | None = None) -> dict:
    """Annual scalar fallback for screening when hourly inverter data are unavailable.

    Clipping must be supplied from an hourly design study when known. If omitted, a bounded
    engineering screening proxy based on DC/AC ratio is used and labeled as such.
    """
    dc = max(float(annual_dc_kwh_kwp),0.0)
    post_dc = dc*(1-mismatch_loss_pct/100)*(1-dc_wiring_loss_pct/100)
    if clipping_loss_pct is None:
        clipping_loss_pct = max(0.0, min(8.0, (float(dc_ac_ratio)-1.05)*8.0))
        clip_basis='screening_proxy_from_dc_ac_ratio_not_bankable'
    else:
        clip_basis='user_or_hourly_model_supplied'
    ac = post_dc*float(inverter_efficiency)*(1-clipping_loss_pct/100)
    meter = ac*(1-transformer_loss_pct/100)*(1-ac_wiring_loss_pct/100)*(availability_pct/100)*(1-curtailment_pct/100)
    return {
        'annual_dc_specific_energy_kwh_kwp': round(dc,3),
        'annual_ac_specific_energy_kwh_kwp': round(ac,3),
        'annual_meter_specific_energy_kwh_kwp': round(meter,3),
        'mismatch_loss_pct': float(mismatch_loss_pct), 'dc_wiring_loss_pct': float(dc_wiring_loss_pct),
        'inverter_efficiency_nominal': float(inverter_efficiency), 'dc_ac_ratio': float(dc_ac_ratio),
        'clipping_loss_pct': round(float(clipping_loss_pct),3), 'clipping_model_basis': clip_basis,
        'transformer_loss_pct': float(transformer_loss_pct), 'ac_wiring_loss_pct': float(ac_wiring_loss_pct),
        'availability_pct': float(availability_pct), 'curtailment_pct': float(curtailment_pct),
        'system_model_basis':'explicit_DC_array_losses -> inverter_efficiency/clipping -> AC/transformer/grid losses'
    }
