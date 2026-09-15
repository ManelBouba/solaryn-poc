import pandas as pd
from src.system_physics import annual_system_from_specific_dc, inverter_ac_power_kw
from src.uncertainty_engine import monte_carlo_yield, probability_of_best
from src.validation_framework import ranking_metrics

def test_system_losses_reduce_meter_energy():
    r=annual_system_from_specific_dc(2000)
    assert 0 < r['annual_meter_specific_energy_kwh_kwp'] < 2000

def test_inverter_clips():
    p=inverter_ac_power_kw(pd.Series([0,50,150]),100)
    assert p.max() <= 100 and p.iloc[0] == 0

def test_p90_below_p50():
    r=monte_carlo_yield(1800,n=3000)
    assert r['p90_kwh_kwp'] < r['p50_kwh_kwp']

def test_probability_best_sums():
    p=probability_of_best({'A':1900,'B':1800},n=3000)
    assert 99.5 <= sum(p.values()) <= 100.5 and p['A'] > p['B']

def test_ranking_metrics():
    r=ranking_metrics({'A':3,'B':2,'C':1},{'A':4,'B':1,'C':2})
    assert r['winner_match'] and 0 < r['pairwise_accuracy_pct'] < 100

def test_resource_calibration_recovers_bias():
    from src.resource_calibration import fit_linear_resource_bias
    x=pd.Series(range(100),dtype=float); y=5+1.1*x
    r=fit_linear_resource_bias(x,y)
    assert abs(r['slope']-1.1)<1e-9 and abs(r['intercept']-5)<1e-8

def test_reliability_is_diagnostic():
    from src.reliability_engine import reliability_exposure_score
    r=reliability_exposure_score({'hours_cell_gt_65c':100,'damp_heat_hours_40c_85rh':50},{'glass_configuration':'glass-glass'})
    assert 'diagnostic_only' in r['decision_use'] and r['bom_completeness_pct']>0
