import numpy as np
from src.thermal_dynamics import ewm_alpha, first_order_filter, dynamic_faiman_temperature

def test_alpha_bounds():
    a=ewm_alpha(60,378); assert 0<a<1

def test_filter_has_thermal_lag():
    x=[0,0,1000,1000]; y=first_order_filter(x,60,378)
    assert 0<y.iloc[2]<1000 and y.iloc[3]>y.iloc[2]

def test_dynamic_faiman_limits_step_response():
    g=[0,0,1000,1000]; ta=[20]*4; ws=[1]*4
    t=dynamic_faiman_temperature(g,ta,ws,dt_seconds=60,tau_minutes=6.3)
    assert t.iloc[2]>20 and t.iloc[2] < 20+1000/(25+6.84)
