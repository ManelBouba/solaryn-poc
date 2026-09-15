"""Deterministic AC lifecycle decision model. Monetary inputs use constant EUR."""
from dataclasses import dataclass, asdict, replace
import math
import numpy as np
from scipy.optimize import brentq

MODEL_VERSION = "procurement-1.0.0"


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be numeric")
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be numeric") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}")
    return value


@dataclass(frozen=True)
class Project:
    name: str = "Riyadh procurement study"
    capacity_mwp: float = 100
    years: int = 30
    discount_rate: float = .07
    ppa_eur_mwh: float = 45
    bos_eur_w: float = .40
    om_eur_kw_year: float = 10
    cleaning_eur_kw_year: float = 2
    debt_service_eur_year: float = 0

    def validate(self):
        if not str(self.name).strip():
            raise ValueError("Project name is required")
        number(self.capacity_mwp, "Capacity MWp", .001, 100000)
        number(self.years, "Years", 1, 60)
        if int(self.years) != self.years:
            raise ValueError("Years must be an integer")
        for field, high in [("discount_rate", 1), ("ppa_eur_mwh", 10000),
                            ("bos_eur_w", 100), ("om_eur_kw_year", 10000),
                            ("cleaning_eur_kw_year", 10000), ("debt_service_eur_year", 1e12)]:
            number(getattr(self, field), field, 0, high)


@dataclass(frozen=True)
class Candidate:
    name: str
    model: str
    bom: str
    quote_eur_w: float
    net_ac_kwh_kwp: float
    yield_source: str
    degradation: float = .005
    early_loss: float = 0
    additional_loss: float = 0
    event_year: int = 15
    event_fraction: float = 0
    downtime_days: float = 0
    replacement_eur_w: float = .25
    warranty_recovery: float = 0

    def validate(self, years):
        for field in ["name", "model", "bom", "yield_source"]:
            if not str(getattr(self, field)).strip():
                raise ValueError(f"Candidate {field} is required (use 'Unknown' for missing BOM)")
        number(self.quote_eur_w, "Module price EUR/W", 0, 100)
        number(self.net_ac_kwh_kwp, "Net AC yield kWh/kWp", .001, 8766)
        for field in ["degradation", "early_loss", "additional_loss", "event_fraction", "warranty_recovery"]:
            number(getattr(self, field), field, 0, .99 if field in ["degradation", "early_loss", "additional_loss"] else 1)
        number(self.event_year, "Event year", 1, years)
        if int(self.event_year) != self.event_year:
            raise ValueError("Event year must be an integer")
        number(self.downtime_days, "Downtime days", 0, 365)
        number(self.replacement_eur_w, "Replacement EUR/W", 0, 100)


def screening_physics(poa, ambient, wind, *, gamma=-.0035, u0=25., u1=6.84,
                      cell_delta=3., dc_ac_ratio=1.3, efficiency=.97, loss=.10, hours=1.):
    """One interval, per kWp: POA W/m2 -> temperature C -> AC kWh/kWp.

    Front-only linear power screening model; no transposition, bifacial, spectral,
    inverter curve or low-light calibration. Never a bankable annual yield.
    """
    for value, name, lo, hi in [(poa, "POA", 0, 2000), (ambient, "Ambient", -90, 90),
                               (wind, "Wind", 0, 100), (gamma, "Gamma", -.02, 0),
                               (u0, "U0", .01, 100), (u1, "U1", 0, 100),
                               (cell_delta, "Cell delta", 0, 30), (dc_ac_ratio, "DC/AC", .1, 5),
                               (efficiency, "Efficiency", .01, 1), (loss, "Loss", 0, 1),
                               (hours, "Interval hours", .001, 24)]:
        number(value, name, lo, hi)
    tm = ambient + poa / (u0 + u1 * wind)
    tc = tm + poa / 1000 * cell_delta
    dc = max(0., poa / 1000 * (1 + gamma * (tc - 25)))
    ac = min(dc * (1 - loss) * efficiency, 1 / dc_ac_ratio)
    return {"module_c": tm, "cell_c": tc, "dc_kw_kwp": dc,
            "ac_kw_kwp": ac, "ac_kwh_kwp": ac * hours}


def irr(cash):
    """Report only a unique conventional-cashflow IRR; ambiguous cases return None."""
    nonzero = np.asarray(cash)[np.asarray(cash) != 0]
    if len(nonzero) < 2 or np.sum(np.sign(nonzero[1:]) != np.sign(nonzero[:-1])) != 1:
        return None
    def f(rate):
        return sum(float(c) * math.exp(-t * math.log1p(rate)) for t, c in enumerate(cash))
    lo, hi = -.99, 1.
    while f(lo) * f(hi) > 0 and hi < 1e6:
        hi *= 2
    return float(brentq(f, lo, hi)) if f(lo) * f(hi) <= 0 else None


def lifecycle(project, candidate):
    project.validate()
    candidate.validate(project.years)
    p, c = project, candidate
    watts, kw = p.capacity_mwp * 1e6, p.capacity_mwp * 1000
    capex = watts * (p.bos_eur_w + c.quote_eur_w)
    annual = []
    for year in range(1, int(p.years) + 1):
        event = year == c.event_year
        retention = (1 - c.early_loss) * (1 - c.degradation) ** (year - 1)
        energy = p.capacity_mwp * c.net_ac_kwh_kwp * retention * (1 - c.additional_loss)
        energy *= 1 - (c.event_fraction * c.downtime_days / 365 if event else 0)
        replacement = watts * c.event_fraction * c.replacement_eur_w if event else 0
        recovery = replacement * c.warranty_recovery
        cost = kw * (p.om_eur_kw_year + p.cleaning_eur_kw_year) + replacement - recovery
        revenue = energy * p.ppa_eur_mwh
        annual.append({"year": year, "energy_mwh": energy, "retention": retention,
                       "revenue_eur": revenue, "cost_eur": cost, "replacement_eur": replacement,
                       "recovery_eur": recovery, "cash_eur": revenue - cost,
                       "discount_factor": (1 + p.discount_rate) ** -year,
                       "dscr_proxy": (revenue - cost) / p.debt_service_eur_year if p.debt_service_eur_year else None})
    pv_cost = capex + sum(a["cost_eur"] * a["discount_factor"] for a in annual)
    pv_energy = sum(a["energy_mwh"] * a["discount_factor"] for a in annual)
    if pv_energy <= 0:
        raise ValueError("Scenario produces no lifetime energy; LCOE and ranking are undefined")
    operating_value = sum(a["cash_eur"] * a["discount_factor"] for a in annual)
    return {"candidate": c.name, "capex_eur": capex, "year1_mwh": annual[0]["energy_mwh"],
            "lifetime_mwh": sum(a["energy_mwh"] for a in annual),
            "npv_eur": operating_value - capex, "lcoe_eur_mwh": pv_cost / pv_energy,
            "irr": irr([-capex] + [a["cash_eur"] for a in annual]),
            "operating_value_eur": operating_value, "annual": annual}


def evidence_gaps(candidate, claims):
    required = ["net_ac_kwh_kwp", "quote_eur_w", "degradation", "bom"]
    def supports(field):
        return any(e.get("candidate") == candidate.name and e.get("model") == candidate.model
                   and e.get("bom") == candidate.bom and e.get("field") == field
                   and str(e.get("value", "")) == str(getattr(candidate, field))
                   and e.get("status") == "Reviewed" and str(e.get("source", "")).strip()
                   and str(e.get("section", "")).strip() and str(e.get("reviewer", "")).strip()
                   and str(e.get("date", "")).strip() for e in claims)
    return [field for field in required if not supports(field) or (field == "bom" and candidate.bom.lower() == "unknown")]


def compare(project, candidates, claims=(), degradation_add=0., yield_haircut=0.):
    project.validate()
    if not 2 <= len(candidates) <= 20:
        raise ValueError("Compare 2 to 20 candidates")
    if len({c.name for c in candidates}) != len(candidates):
        raise ValueError("Candidate names must be unique")
    number(degradation_add, "Additional degradation", 0, .2)
    number(yield_haircut, "Yield haircut", 0, .99)
    results = []
    for c in candidates:
        c.validate(project.years)
        scenario = replace(c, degradation=c.degradation + degradation_add,
                           net_ac_kwh_kwp=c.net_ac_kwh_kwp * (1 - yield_haircut))
        result = lifecycle(project, scenario)
        result["evidence_gaps"] = evidence_gaps(c, claims)
        results.append(result)
    baseline = results[0]
    for result in results:
        premium = (result["operating_value_eur"] - baseline["operating_value_eur"]) / (project.capacity_mwp * 1e6)
        result["justified_premium_eur_w_vs_first"] = premium
        result["break_even_quote_eur_w"] = candidates[0].quote_eur_w + premium
    results.sort(key=lambda r: (-r["npv_eur"], r["candidate"]))
    tied = abs(results[0]["npv_eur"] - results[1]["npv_eur"]) <= .01
    status = "Effectively tied" if tied else "Provisional scenario leader"
    if any(r["evidence_gaps"] for r in results):
        status += " — evidence review required"
    return {"model_version": MODEL_VERSION, "project": asdict(project),
            "candidates": [asdict(c) for c in candidates], "claims": list(claims),
            "scenario": {"degradation_add": degradation_add, "yield_haircut": yield_haircut,
                         "interpretation": "Deterministic sensitivity; not statistical P50/P90"},
            "status": status, "leader": None if tied else results[0]["candidate"], "results": results}
