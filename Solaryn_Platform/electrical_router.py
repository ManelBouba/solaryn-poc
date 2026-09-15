"""Evidence-first A/B/C electrical routing, without technology-family policy."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

PILOT_MATRIX = Path(__file__).resolve().parents[1] / 'Solaryn_Pilot/src/iec61853_engine.py'
spec = importlib.util.spec_from_file_location('solaryn_reviewed_iec_matrix', PILOT_MATRIX)
matrix_core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = matrix_core
spec.loader.exec_module(matrix_core)
VERSION = 'evidence-routing-1.0'


def power(module, irradiance, temperature, fallback):
    """Return kW/kWp, routing evidence and explicit daylight domain fractions.

    Catalog evidence is frozen into the module row, never read by a report.
    No datasheet-to-CEC fit is promoted to validated coefficients here.
    """
    g, t = np.asarray(irradiance, float), np.asarray(temperature, float)
    if g.shape != t.shape or not np.isfinite(g).all() or not np.isfinite(t).all():
        raise ValueError('Invalid electrical operating conditions')
    evidence = module.get('electrical_evidence')
    if not evidence:
        gamma = module.get('temperature_coefficient_pct_per_c')
        if gamma is None or not np.isfinite(gamma) or not -2 < gamma <= 0:
            raise ValueError('Missing or invalid datasheet temperature coefficient')
        return np.array([fallback(x,y,gamma/100) for x,y in zip(g,t)]), {
            'model_path':'C_DATASHEET_PVWATTS','evidence':'PROVISIONAL_DATASHEET',
            'interpolation_fraction':None,'extrapolation_fraction':None,
            'extrapolation_status':'UNCHARACTERIZED: no measured irradiance/temperature domain supplied'}
    if evidence.get('module_id') != module['module_id'] or evidence.get('review_status') != 'APPROVED':
        raise ValueError('Electrical evidence requires exact SKU identity and an approved review')
    if not all(evidence.get(k) for k in ('source_url','reviewed_by','reviewed_at','scope')):
        raise ValueError('Electrical evidence lacks provenance or review scope')
    pmax = module['rated_power_w']
    day = g > 0
    if evidence.get('kind') == 'IEC61853':
        m = pd.DataFrame(evidence['matrix'])
        if not np.isfinite(m[matrix_core.REQUIRED_MATRIX_COLUMNS].to_numpy(float)).all():
            raise ValueError('Measured matrix contains nonfinite values')
        validation = matrix_core.validate_iec61853_matrix(m,module_pmax_w=pmax)
        if not validation.has_stc_anchor:
            raise ValueError('Reviewed SKU matrix must contain the STC identity anchor')
        watts, diagnostics = matrix_core.interpolate_iec61853_pmax(m,g,t)
        # Count the union of envelope and convex-hull fallback hours, rather than
        # summing overlapping percentages from the inherited diagnostics.
        outside = (g<m.irradiance_w_m2.min()) | (g>m.irradiance_w_m2.max()) | (t<m.module_temperature_c.min()) | (t>m.module_temperature_c.max())
        linear, _ = matrix_core._build_interpolators(m)
        outside |= ~np.isfinite(linear(np.column_stack([g,t])))
        fraction = float(np.count_nonzero(outside & day)/max(1,np.count_nonzero(day)))
        values = np.asarray(watts,float)/pmax
        path='A_MEASURED_IEC61853'
    elif evidence.get('kind') == 'CEC_VALIDATED':
        coefficients=evidence['coefficients']
        keys=('alpha_sc_A_C','a_ref','I_L_ref','I_o_ref','R_sh_ref','R_s','Adjust')
        if not all(k in coefficients and np.isfinite(coefficients[k]) for k in keys):
            raise ValueError('Incomplete validated CEC coefficients')
        if any(coefficients[k]<=0 for k in ('a_ref','I_L_ref','I_o_ref','R_sh_ref')) or coefficients['R_s']<0:
            raise ValueError('Invalid validated CEC coefficients')
        domain=evidence.get('validated_domain') or {}
        if not all(k in domain and np.isfinite(domain[k]) for k in ('g_min','g_max','t_min','t_max')) or domain['g_max']<=domain['g_min'] or domain['t_max']<=domain['t_min']:
            raise ValueError('CEC evidence requires a validated operating domain')
        # Same reviewed primitive sequence as Pilot module_iv_engine._pmp_from_cec.
        def solve(gg,tt):
            params=pvlib.pvsystem.calcparams_cec(gg,tt,alpha_sc=coefficients['alpha_sc_A_C'],a_ref=coefficients['a_ref'],I_L_ref=coefficients['I_L_ref'],I_o_ref=coefficients['I_o_ref'],R_sh_ref=coefficients['R_sh_ref'],R_s=coefficients['R_s'],Adjust=coefficients['Adjust'])
            return np.asarray(pvlib.pvsystem.singlediode(*params,method='lambertw')['p_mp'],float)
        anchor=float(solve(np.array([1000.]),np.array([25.]))[0])
        if abs(anchor-pmax)/pmax>.03:
            raise ValueError('CEC STC output fails the 3% SKU identity consistency gate')
        values=np.zeros_like(g)
        if day.any(): values[day]=solve(g[day],t[day])/pmax
        fraction=float(np.count_nonzero(day & ((g<domain['g_min']) | (g>domain['g_max']) | (t<domain['t_min']) | (t>domain['t_max'])))/max(1,np.count_nonzero(day)))
        diagnostics={'validated_domain':domain,'temperature_basis':'effective cell temperature'}
        path='B_VALIDATED_CEC'
    else:
        raise ValueError('Unsupported electrical evidence kind; no silent fallback')
    if not np.isfinite(values).all() or (values<0).any():
        raise ValueError('Electrical model returned invalid power')
    return values, {'model_path':path,'evidence':'REVIEWED_CANDIDATE_ELECTRICAL',
                    'interpolation_fraction':1-fraction,'extrapolation_fraction':fraction,
                    'extrapolation_status':'EXPLICIT_DOMAIN_ACCOUNTING', 'model_diagnostics':diagnostics,
                    'electrical_scope':evidence['scope'],'electrical_source_url':evidence['source_url']}
