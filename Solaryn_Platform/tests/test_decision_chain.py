import math
import pandas as pd
import pytest
from decision_chain import decision_chain
from server import model

def test_lifetime_and_conditional_quantiles():
    p={'years':2,'capacity_mwp':1}
    e=[{'module_id':'a','model':'A','net_ac_kwh_kwp':1000}]
    args=(p,{'degradation':.1},e,pd.DataFrame(),{'decision':{'status':'INSUFFICIENT_EVIDENCE'}},None)
    c=decision_chain(*args)
    assert c['lifetime'][0]['lifetime_mwh']==1900
    assert c['lifetime'][0]['uncertainty']['status']=='NOT_QUANTIFIED'
    args[1]['yield_log_sigma']=.1
    u=decision_chain(*args)['lifetime'][0]['uncertainty']
    assert u['year1_p90_mwh']==pytest.approx(879.715,abs=.01)
    assert u['lifetime_p90_mwh']==pytest.approx(1.9*u['year1_p90_mwh'])
    args[1]['yield_log_sigma']=float('nan')
    with pytest.raises(ValueError): decision_chain(*args)


def comparison(prices=(.5,.05), yields=(1200,1150), reverse=False):
    project=model.Project(name='Separation test',capacity_mwp=1)
    energy=[{'module_id':mid,'model':mid.upper(),'net_ac_kwh_kwp':value,'dc_kwh_kwp':value/0.95}
            for mid,value in zip(['a','b'],yields)]
    offers=[model.Candidate(name=e['module_id'],model=e['model'],bom='test',quote_eur_w=price,
                            net_ac_kwh_kwp=e['net_ac_kwh_kwp'],yield_source='Synthetic test')
            for e,price in zip(energy,prices)]
    if reverse:
        energy.reverse()
        offers.reverse()
    from dataclasses import asdict
    return decision_chain(asdict(project),{'degradation':.005},energy,pd.DataFrame(),
                          {'decision':{'status':'INSUFFICIENT_EVIDENCE','required_decision_gap_pct':2}},
                          model.compare(project,offers))


def test_prices_change_commercial_not_physical_or_lifetime_rank():
    expensive=comparison()
    cheap=comparison(prices=(.05,.5))
    assert expensive['physical']==cheap['physical']
    assert expensive['lifetime']==cheap['lifetime']
    assert expensive['physical']['numerical_leader_ids']==['a']
    assert expensive['commercial']['numerical_leader_ids']==['b']
    assert cheap['commercial']['numerical_leader_ids']==['a']
    assert expensive['recommendation']['recommended_module_id'] is None
    assert 'different objectives' in expensive['recommendation']['explanation']


def test_climate_yield_reversal_changes_physical_order_without_price_change():
    warm=comparison(yields=(1200,1150))
    cold=comparison(yields=(1100,1200))
    assert warm['physical']['numerical_leader_ids']==['a']
    assert cold['physical']['numerical_leader_ids']==['b']
    assert cold['lifetime'][0]['module_id']=='b'


def test_ties_do_not_manufacture_winner_and_row_order_is_irrelevant():
    a=comparison(prices=(.12,.12),yields=(1200,1200))
    b=comparison(prices=(.12,.12),yields=(1200,1200),reverse=True)
    assert a['physical']==b['physical']
    assert a['commercial']==b['commercial']
    assert [r['rank'] for r in a['commercial']['ranking']]==[1,1]
    assert [r['rank'] for r in a['lifetime']]==[1,1]
    assert a['recommendation']['recommended_module_id'] is None
    assert a['physical']['status']=='UNRESOLVED_WITHIN_GUARDRAIL'


def test_small_gap_and_missing_quotes_remain_explicit():
    c=comparison(yields=(1201,1200))
    assert c['physical']['status']=='UNRESOLVED_WITHIN_GUARDRAIL'
    assert 'superiority is unresolved' in c['recommendation']['explanation']
    assert 'rear generation is disabled' in c['physical']['geometry_scope']
    args=({'years':2,'capacity_mwp':1},{'degradation':.01},
          [{'module_id':'a','model':'A','net_ac_kwh_kwp':1200},
           {'module_id':'b','model':'B','net_ac_kwh_kwp':1000}],
          pd.DataFrame(),{'decision':{'status':'INSUFFICIENT_EVIDENCE'}},None)
    no_prices=decision_chain(*args)
    assert len(no_prices['physical']['ranking'])==2
    assert no_prices['commercial']['status']=='PRICES_REQUIRED'
