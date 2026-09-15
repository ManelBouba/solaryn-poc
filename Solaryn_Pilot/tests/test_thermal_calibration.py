import numpy as np
import pandas as pd
from src.thermal_calibration import chronological_split, calibrate_dynamic_faiman


def _synthetic():
    idx=pd.date_range('2025-01-01',periods=60*24*20,freq='1min')
    h=idx.hour.to_numpy()+idx.minute.to_numpy()/60
    g=np.maximum(0,800*np.sin(np.pi*(h-6)/12))
    ta=12+6*np.sin(2*np.pi*(h-8)/24)
    ws=2+0.5*np.sin(2*np.pi*h/24)
    # approximate target from known parameters, slight deterministic perturbation
    from src.thermal_dynamics import dynamic_faiman_temperature
    tc=dynamic_faiman_temperature(pd.Series(g),pd.Series(ta),pd.Series(ws),u0=27.0,u1=5.0,dt_seconds=60,tau_minutes=7.0).to_numpy()
    tc=tc+0.05*np.sin(np.arange(len(tc))/37)
    return pd.DataFrame({'Tamb':ta,'PV052_5x4C':tc,'G_Pyr_18_S':g,'WS':ws},index=idx)[lambda x:x.G_Pyr_18_S>=20]


def test_chronological_split_has_gap_and_no_overlap():
    df=_synthetic(); tr,ho=chronological_split(df,0.7,1440)
    assert tr.index.max() < ho.index.min()
    assert len(set(tr.index).intersection(set(ho.index)))==0


def test_calibration_recovers_reasonable_parameters_and_improves_holdout():
    df=_synthetic()
    result,_=calibrate_dynamic_faiman(df,train_fraction=0.7,gap_minutes=60)
    assert 15 <= result.u0 <= 40
    assert 0 <= result.u1 <= 15
    assert 1 <= result.tau_minutes <= 30
    assert result.holdout_metrics['rmse_k'] < result.baseline_holdout_metrics['rmse_k']
