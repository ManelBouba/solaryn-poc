"""Transparent scenario extensions; no fitted climate-aging or probability claim."""
import math
from statistics import NormalDist


def ranked(rows, metric):
    """Numerical ranks only; equal values share rank and never pick by brand/order."""
    ordered = sorted(rows, key=lambda r: (-r[metric], r['module_id']))
    previous = None
    rank = 0
    for index, row in enumerate(ordered, 1):
        if previous is None or not math.isclose(row[metric], previous, rel_tol=1e-10, abs_tol=1e-8):
            rank = index
            previous = row[metric]
        row['rank'] = rank
    return ordered


def decision_chain(params, configuration, energy, weather, physics, economics):
    years = int(params['years'])
    degradation = configuration['degradation']
    sigma = configuration.get('yield_log_sigma')
    if sigma is not None and (not math.isfinite(sigma) or not 0 <= sigma <= .5):
        raise ValueError('Yield log standard deviation must be between 0 and 0.5')
    exposure = {}
    for key, label, unit in [('T2M','ambient_temperature','C'),('RH2M','relative_humidity','%'),('WS10M','wind_speed','m/s'),('PRECTOTCORR','precipitation_rate','mm/hour')]:
        values = weather[key].dropna() if key in weather else []
        exposure[label] = {'mean':float(values.mean()),'maximum':float(values.max()),'unit':unit} if len(values) else {'status':'MISSING'}
    projections = []
    for row in energy:
        first = params['capacity_mwp'] * row['net_ac_kwh_kwp']
        annual = [{'year':y,'energy_mwh':first*(1-degradation)**(y-1)} for y in range(1,years+1)]
        lifetime = sum(a['energy_mwh'] for a in annual)
        uncertainty = {'status':'NOT_QUANTIFIED','reason':'Supply log-yield sigma; one weather year and electrical RMSE do not establish plant uncertainty.'}
        if sigma is not None:
            factor = math.exp(NormalDist().inv_cdf(.1)*sigma)
            uncertainty = {'status':'ASSUMPTION_CONDITIONAL','year1_p50_mwh':first,'year1_p90_mwh':first*factor,'lifetime_p50_mwh':lifetime,'lifetime_p90_mwh':lifetime*factor,'log_sigma':sigma,'model':'Lognormal multiplicative yield; deterministic yield assumed median. Common persistent factor across all years; degradation fixed. P90 is 10th percentile (90% exceedance). Not empirically calibrated.'}
        projections.append({'module_id':row['module_id'],'model':row['model'],'annual':annual,'lifetime_mwh':lifetime,'uncertainty':uncertainty})
    ranking = []
    if economics:
        for rank, item in enumerate(economics['results'],1):
            cash = -item['capex_eur']
            payback = None
            for a in item['annual']:
                previous = cash
                cash += a['cash_eur']
                if payback is None and cash >= 0 and a['cash_eur'] > 0:
                    payback = a['year']-1 + (-previous/a['cash_eur'])
            pv_revenue = sum(a['revenue_eur']*a['discount_factor'] for a in item['annual'])
            # Exact one-at-a-time financial sensitivities, holding physical yield shape fixed.
            sensitivity = {'yield_minus_5pct_npv_eur':item['npv_eur']-.05*pv_revenue,'yield_plus_5pct_npv_eur':item['npv_eur']+.05*pv_revenue,'module_price_plus_001_eur_w_npv_eur':item['npv_eur']-.01*params['capacity_mwp']*1e6}
            row = next(r for r in energy if r['module_id']==item['candidate'])
            ranking.append({'rank':rank,'module_id':item['candidate'],'model':row['model'],'npv_eur':item['npv_eur'],'lcoe_eur_mwh':item['lcoe_eur_mwh'],'capex_eur':item['capex_eur'],'lifetime_revenue_eur':sum(a['revenue_eur'] for a in item['annual']),'lifetime_opex_eur':sum(a['cost_eur'] for a in item['annual']),'simple_payback_years':payback,'sensitivity':sensitivity,'why':f"Ranked by scenario NPV using {row['net_ac_kwh_kwp']:.2f} kWh/kWp annual net AC, supplied module price and project costs. Physical evidence gates remain controlling."})
    physical = []
    for row in energy:
        candidate = next((c for c in physics.get('candidates', []) if c['module_id'] == row['module_id']), {})
        metrics = candidate.get('metrics', {})
        physical.append({
            'module_id': row['module_id'], 'model': row['model'],
            'net_ac_kwh_kwp': row['net_ac_kwh_kwp'], 'dc_kwh_kwp': row.get('dc_kwh_kwp'),
            'temperature_response_pct': metrics.get('temperature_response_effect_pct'),
            'off_stc_response_pct': metrics.get('off_stc_irradiance_response_pct'),
            'rear_gain_pct': metrics.get('bifacial_rear_gain_pct'),
            'p95_cell_temperature_c': metrics.get('p95_cell_temperature_c_daylight'),
            'decision_eligible': candidate.get('decision_eligible', False),
        })
    physical = ranked(physical, 'net_ac_kwh_kwp')
    projections = ranked(projections, 'lifetime_mwh')
    ranking = ranked(ranking, 'npv_eur')
    gap = (100 * (physical[0]['net_ac_kwh_kwp'] / physical[1]['net_ac_kwh_kwp'] - 1)
           if len(physical) >= 2 else None)
    guardrail = physics['decision'].get('required_decision_gap_pct', 2.0)
    physical_leaders = [r['module_id'] for r in physical if r['rank'] == 1]
    commercial_leaders = [r['module_id'] for r in ranking if r['rank'] == 1]
    physical_status = ('COMPARISON_INCOMPLETE' if gap is None else
                       'UNRESOLVED_WITHIN_GUARDRAIL' if gap <= guardrail else 'NUMERICAL_SEPARATION_ONLY')
    if not ranking:
        explanation = 'Physical and lifetime outputs are available. Enter a quote for every selected module to compare commercial scenarios.'
    elif len(physical_leaders) != 1 or len(commercial_leaders) != 1:
        explanation = 'A numerical tie prevents a unique physical or commercial leader. Display order does not resolve the tie.'
    elif physical_leaders == commercial_leaders:
        explanation = 'The same module has the highest modeled annual net AC and scenario NPV under these inputs. This agreement is not evidence of procurement suitability.'
    else:
        physical_name = physical[0]['model']
        commercial_name = ranking[0]['model']
        explanation = (f'{physical_name} has the highest modeled annual net AC; {commercial_name} has the highest scenario NPV at the supplied prices and financial assumptions. '
                       'These are different objectives; neither establishes a validated procurement winner.')
    if physical_status == 'UNRESOLVED_WITHIN_GUARDRAIL':
        explanation += f' The top annual net AC gap is {gap:.2f}%, within the {guardrail:.2f}% decision policy guardrail; physical superiority is unresolved.'
    return {
        'schema_version': 'decision-chain-2.0', 'climate_exposure': exposure,
        'physical': {'ranking': physical, 'basis': 'Annual net AC per installed DC kWp; independent of prices and financial assumptions. Energy comparison, not complete physical suitability.',
                     'status': physical_status, 'top_gap_pct': gap, 'guardrail_pct': guardrail,
                     'numerical_leader_ids': physical_leaders,
                     'evidence_status': physics['decision']['status'], 'evidence_reasons': physics['decision'].get('reasons', []),
                     'geometry_scope': 'Common row geometry and rear irradiance enabled.' if configuration.get('row_geometry') else 'Front-only baseline: rear generation is disabled, including for bifacial modules.'},
        'lifetime': projections,
        'aging_scope': 'E_y = E_1 (1-d)^(y-1). All candidates use the same declared degradation scenario, so lifetime ranking follows annual energy. No climate-specific aging is inferred from technology labels.',
        'commercial': {'ranking': ranking, 'numerical_leader_ids': commercial_leaders,
                       'status': 'CONDITIONAL_NPV_COMPARISON' if ranking else 'PRICES_REQUIRED'},
        'recommendation': {'status': 'REVIEW_REQUIRED' if ranking else 'PRICES_REQUIRED',
                           'recommended_module_id': None, 'explanation': explanation,
                           'physical_evidence_status': physics['decision']['status'], 'confidence': 'NOT_CALIBRATED',
                           'ranking': ranking, 'ties': 'Equal NPVs share a numerical rank. No automatic procurement recommendation.'}}
