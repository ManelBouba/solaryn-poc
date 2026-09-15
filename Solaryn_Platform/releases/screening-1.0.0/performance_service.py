"""Deterministic, provisional Path C adapter over frozen climate and module inputs.

Only the isolated Pilot PVWatts scalar kernel is reused: importing the legacy
orchestrator would apply different evidence policies and fetch new weather.
"""
import calendar
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
from typing import Literal

import numpy as np
import pandas as pd
import pvlib
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parent
CORE = ROOT.parent / 'Solaryn_Pilot/src/climate_physics.py'
spec = importlib.util.spec_from_file_location('solaryn_frozen_climate_kernel', CORE)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
VERSION = 'screening-1.0.0'


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Lifetime(Strict):
    years: int = Field(ge=1, le=50)
    degradation_pct: float = Field(ge=0, le=10)


class AC(Strict):
    dc_ac_ratio: float = Field(ge=.5, le=3)
    efficiency: float = Field(ge=.5, le=1)
    availability: float = Field(ge=.01, le=1)
    curtailment: float = Field(ge=0, le=.99)


class Economics(Strict):
    reference_id: str
    energy_value_eur_kwh: float = Field(ge=0, le=10)
    discount_rate_pct: float = Field(ge=0, le=30)
    quotes_eur_w: dict[str, float]
    incremental_cost_pv_eur_w: dict[str, float]

    @model_validator(mode='after')
    def valid_money(self):
        for mapping in (self.quotes_eur_w, self.incremental_cost_pv_eur_w):
            if any(not math.isfinite(v) or v < 0 for v in mapping.values()):
                raise ValueError('Prices and present-value costs must be finite and nonnegative')
        return self


class Configuration(Strict):
    objective: Literal['annual_dc', 'annual_ac', 'lifetime_dc', 'procurement_headroom']
    tilt_deg: float = Field(ge=0, le=90)
    azimuth_deg: float = Field(ge=0, lt=360)
    albedo: float = Field(ge=0, le=1)
    soiling_pct: float = Field(ge=0, le=50)
    u0: float = Field(gt=0, le=100)
    u1: float = Field(ge=0, le=30)
    wind_factor: float = Field(gt=0, le=2)
    lifetime: Lifetime | None = None
    ac: AC | None = None
    economics: Economics | None = None

    @model_validator(mode='after')
    def dependencies(self):
        if self.objective == 'annual_ac' and not self.ac:
            raise ValueError('Annual AC objective requires AC inputs')
        if self.objective == 'lifetime_dc' and not self.lifetime:
            raise ValueError('Lifetime objective requires lifetime inputs')
        if self.economics and (not self.ac or not self.lifetime):
            raise ValueError('Economics requires lifetime and AC inputs')
        if self.objective == 'procurement_headroom' and not self.economics:
            raise ValueError('Procurement objective requires commercial inputs')
        return self


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def weather(source, site, config):
    if source.get('requested_location') != {k: site[k] for k in ('latitude', 'longitude')}:
        raise ValueError('Climate coordinates do not match the frozen site')
    if source.get('geometry', {}).get('plane') != 'horizontal':
        raise ValueError('This adapter requires horizontal source irradiance')
    expected_units = {'ghi_w_m2': 'W/m²', 'air_temperature_c': '°C', 'wind_speed_m_s': 'm/s'}
    if any(source.get('canonical_units', {}).get(k) != v for k, v in expected_units.items()):
        raise ValueError('Climate units do not match the normalized model boundary')
    df = pd.DataFrame(source['hourly'])
    times = pd.DatetimeIndex(pd.to_datetime(df.timestamp_utc, utc=True))
    year = int(source['year'])
    expected = 8784 if calendar.isleap(year) else 8760
    if len(times) != expected or times.has_duplicates or not times.is_monotonic_increasing:
        raise ValueError('A complete, ordered hourly year is required')
    slots = times.floor('h')
    required = pd.date_range(f'{year}-01-01', periods=expected, freq='h', tz='UTC')
    if not slots.equals(required) or len(set(times.minute)) != 1 or (times.second != 0).any():
        raise ValueError('Climate must cover each UTC hour once, with a consistent sampling offset')
    if source.get('sample_duration_hours') != 1 or source.get('time_standard') != 'UTC':
        raise ValueError('Climate integration requires normalized UTC one-hour samples')
    for key in ('ghi_w_m2', 'air_temperature_c', 'wind_speed_m_s'):
        values = pd.to_numeric(df[key], errors='coerce').to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError(f'Climate has missing {key}; no interpolation or provider blending is applied')
    ghi = df.ghi_w_m2.to_numpy(float)
    wind = df.wind_speed_m_s.to_numpy(float)
    if (ghi < 0).any() or (wind < 0).any():
        raise ValueError('Negative irradiance or wind speed')
    if config.tilt_deg == 0:
        poa = ghi.copy()
        transposition = 'Horizontal: POA = saved GHI; no decomposition required'
    else:
        sun = pvlib.solarposition.get_solarposition(times, site['latitude'], site['longitude'], altitude=0)
        # Use the same GHI-only decomposition for both resource providers. The
        # original GHI is not replaced, and derived components remain explicit.
        split = pvlib.irradiance.erbs(ghi, sun.zenith, times)
        components = pvlib.irradiance.get_total_irradiance(
            config.tilt_deg, config.azimuth_deg, sun.apparent_zenith, sun.azimuth,
            split.dni, ghi, split.dhi, albedo=config.albedo, model='isotropic')
        poa = np.asarray(components['poa_global'], float)
        transposition = 'Erbs GHI decomposition + isotropic transposition; elevation 0 m; provider timestamps retained'
    if not np.isfinite(poa).all() or (poa < 0).any():
        raise ValueError('Invalid plane-of-array irradiance')
    temperature = np.array([core.faiman_cell_temperature_c(g, t, w * config.wind_factor, config.u0, config.u1)
                            for g, t, w in zip(poa, df.air_temperature_c, wind)])
    if not np.isfinite(temperature).all():
        raise ValueError('Invalid modeled cell temperature')
    return times, poa, temperature, transposition


def ac_output(dc, config):
    # Same constant-efficiency/clipping boundary as physics_worker.ac_from_dc.
    preclip = dc * config.efficiency
    clipped = np.minimum(preclip, 1 / config.dc_ac_ratio)
    net = clipped * config.availability * (1 - config.curtailment)
    return net, {'conversion_loss_kwh_kwp': float(np.sum(dc - preclip)),
                 'clipping_loss_kwh_kwp': float(np.sum(preclip - clipped)),
                 'availability_curtailment_loss_kwh_kwp': float(np.sum(clipped - net))}


def lifetime_rows(dc, ac, config):
    if config is None:
        return []
    return [{'year': y, 'retention': (1 - config.degradation_pct / 100) ** (y - 1),
             'dc_kwh_kwp': dc * (1 - config.degradation_pct / 100) ** (y - 1),
             'ac_kwh_kwp': ac * (1 - config.degradation_pct / 100) ** (y - 1) if ac is not None else None}
            for y in range(1, config.years + 1)]


def rank(rows, config):
    key = {'annual_dc': 'annual_dc_kwh_kwp', 'annual_ac': 'annual_ac_kwh_kwp',
           'lifetime_dc': 'lifetime_dc_kwh_kwp', 'procurement_headroom': 'headroom_eur_w'}[config.objective]
    if config.economics:
        econ = config.economics
        ids = {r['module_id'] for r in rows}
        if econ.reference_id not in ids:
            raise ValueError('The economic reference must be a feasible selected candidate')
        if not ids.issubset(econ.quotes_eur_w) or not ids.issubset(econ.incremental_cost_pv_eur_w):
            raise ValueError('Supply a quote and present-value non-module cost for every feasible candidate (explicit zero if excluded)')
        reference = next(r for r in rows if r['module_id'] == econ.reference_id)
        for row in rows:
            mid = row['module_id']
            advantage = sum((a['ac_kwh_kwp'] - b['ac_kwh_kwp']) * econ.energy_value_eur_kwh /
                            (1 + econ.discount_rate_pct / 100) ** a['year']
                            for a, b in zip(row['annual_lifetime'], reference['annual_lifetime'])) / 1000
            row['max_premium_eur_w'] = advantage - (econ.incremental_cost_pv_eur_w[mid] - econ.incremental_cost_pv_eur_w[econ.reference_id])
            row['quote_eur_w'] = econ.quotes_eur_w[mid]
            row['headroom_eur_w'] = row['max_premium_eur_w'] - (econ.quotes_eur_w[mid] - econ.quotes_eur_w[econ.reference_id])
    ordered = sorted(rows, key=lambda r: (-r[key], r['module_id']))
    for i, row in enumerate(ordered):
        row['rank'] = i + 1
        row['objective_value'] = row[key]
        # Absolute-unit margin also works when headroom is zero or negative.
        row['difference_from_leader'] = ordered[0][key] - row[key]
        row['dc_difference_from_leader_pct'] = 100 * (row['annual_dc_kwh_kwp'] / ordered[0]['annual_dc_kwh_kwp'] - 1) if ordered[0]['annual_dc_kwh_kwp'] > 0 else None
    tied = [r['module_id'] for r in ordered if math.isclose(r[key], ordered[0][key], rel_tol=1e-12, abs_tol=1e-12)] if ordered else []
    return {'recommended_candidate': ordered[0]['module_id'] if ordered else None,
            'strength': 'MARGINAL' if ordered else None,
            'status': 'RECOMMENDED_MARGINAL' if ordered else 'CANNOT_RECOMMEND',
            'objective': config.objective, 'objective_unit': 'EUR/W' if key == 'headroom_eur_w' else 'kWh/kWp',
            'ranking': ordered, 'top_three': ordered[:3], 'co_leaders': tied,
            'tie_policy': 'Unrounded descending objective; stable module ID for identical values. Co-leaders within 1e-12 numerical tolerance have no established physical preference.',
            'strength_reason': 'Provisional datasheet response and common uncalibrated thermal assumptions; no candidate-level external validation or calibrated confidence interval.'}


def calculate(frozen, configuration):
    config = Configuration.model_validate(configuration)
    source, modules = frozen['source'], frozen['modules']
    times, poa, temp, transposition = weather(source, frozen['site'], config)
    if not poa.sum() > 0:
        raise ValueError('The reference year has no positive solar resource')
    effective = poa * (1 - config.soiling_pct / 100)
    rows, failures = [], []
    for module in modules:
        mid = module['module_id']
        pmax, gamma = module.get('rated_power_w'), module.get('temperature_coefficient_pct_per_c')
        if pmax is None or gamma is None or not math.isfinite(pmax) or not math.isfinite(gamma) or pmax <= 0 or not -2 < gamma <= 0:
            failures.append({'module_id': mid, 'reason': 'Missing or invalid rated power / temperature coefficient'})
            continue
        dc = np.array([core.pvwatts_dc_power_kw_per_kwp(g, t, gamma / 100) for g, t in zip(effective, temp)])
        if not np.isfinite(dc).all():
            failures.append({'module_id': mid, 'reason': 'Nonfinite modeled power'})
            continue
        ac, losses = ac_output(dc, config.ac) if config.ac else (None, {})
        annual = float(dc.sum())
        annual_ac = float(ac.sum()) if ac is not None else None
        life = lifetime_rows(annual, annual_ac, config.lifetime)
        reference25 = float(effective.sum() / 1000)
        rows.append({'module_id': mid, 'manufacturer': module['manufacturer'], 'model': module['model'],
                     'annual_dc_kwh_kwp': annual, 'annual_dc_kwh_module': annual * pmax / 1000,
                     'annual_ac_kwh_kwp': annual_ac, 'lifetime_dc_kwh_kwp': sum(r['dc_kwh_kwp'] for r in life) if life else None,
                     'annual_lifetime': life, 'max_premium_eur_w': None, 'quote_eur_w': None, 'headroom_eur_w': None,
                     'monthly': [{'month': m, 'dc_kwh_kwp': float(dc[times.month == m].sum()),
                                  'ac_kwh_kwp': float(ac[times.month == m].sum()) if ac is not None else None} for m in range(1, 13)],
                     'model_path': 'C_DATASHEET_PVWATTS', 'evidence': 'PROVISIONAL_DATASHEET',
                     'interpolation_fraction': None, 'extrapolation_fraction': None,
                     'extrapolation_status': 'UNCHARACTERIZED: no measured irradiance/temperature domain supplied',
                     'contributions': {'incident_reference25_kwh_kwp': float(poa.sum() / 1000),
                                       'common_soiling_loss_at25_kwh_kwp': float((poa - effective).sum() / 1000),
                                       'temperature_effect_kwh_kwp': annual - reference25, **losses}})
    decision = rank(rows, config)
    top = decision['ranking']
    explanation = 'No feasible candidate has the minimum electrical inputs.'
    if top:
        explanation = 'The ranking uses the declared objective on the same hourly resource and project assumptions.'
        if len(top) > 1:
            delta = top[0]['contributions']['temperature_effect_kwh_kwp'] - top[1]['contributions']['temperature_effect_kwh_kwp']
            explanation += f' Compared with the next ranked candidate, the modeled DC temperature contribution differs by {delta:.3f} kWh/kWp/year. In this fallback, temperature coefficient is the only candidate-specific driver of DC specific yield. Shared soiling and resource are not independent reasons to prefer a candidate.'
        if config.economics:
            explanation += ' Procurement headroom additionally includes the supplied quotes and discounted incremental net-AC value and costs.'
    versions = {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__, 'pvlib': pvlib.__version__}
    code = {p.relative_to(ROOT.parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), CORE)}
    return {'decision': decision, 'candidate_failures': failures, 'explanation': explanation,
            'contributions': [{'module_id': r['module_id'], **r['contributions']} for r in top],
            'model_path': 'C_DATASHEET_PVWATTS', 'model_version': VERSION, 'validation_status': 'PROVISIONAL_NOT_EXTERNALLY_VALIDATED',
            'extrapolation': 'UNCHARACTERIZED', 'configuration': config.model_dump(),
            'manifest': {'inputs_sha256': digest(frozen), 'configuration_sha256': digest(config.model_dump()),
                         'result_sha256': digest(decision), 'code_sha256': code, 'runtime': versions},
            'implementation_sources': {p.relative_to(ROOT.parent).as_posix(): base64.b64encode(p.read_bytes()).decode('ascii')
                                       for p in (Path(__file__), CORE)},
            'assumptions': [transposition, 'Front-side DC specific energy per installed kWp; no rear, spectral, low-light or IAM differentiation; no terrain/row shading.',
                            f'Common Faiman effective cell temperature: U0={config.u0}, U1={config.u1}; provider 10 m wind × {config.wind_factor}. Coefficients and wind-height transfer are uncalibrated project assumptions.',
                            f'Uniform soiling {config.soiling_pct}%; no missing weather filled. One-hour integration at original UTC sample times.',
                            'Lifetime: E_y = E_1 × (1-d)^(y-1), same supplied scenario for all candidates; not warranty-derived.' if config.lifetime else 'Lifetime not requested: no degradation rate assumed.',
                            'AC: constant efficiency, hard clipping at 1/DC:AC, then availability and curtailment; no inverter-specific model.' if config.ac else 'AC conversion not configured; annual results are DC.',
                            'Economics: EUR, end-of-year discounted net-AC value; explicit reference and supplied present-value non-module costs; no LCOE claim. Lifetime AC scales year-1 net AC by common retention, with clipping not recalculated by year.' if config.economics else 'Economics not requested: no price or value assumed.'],
            'warnings': ['Provisional screening recommendation. Candidate-level external validation and current commercial availability remain unverified.',
                         'No measured IEC matrices or validated candidate coefficients are available to this screening path. Datasheet fallback cannot establish cross-technology superiority.',
                         'Thermal, irradiance decomposition and loss assumptions can change the result; recommendation strength is conservatively Marginal, not a probability.']}
