from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from src.physics_model import STATUS_SCORE, bounded, site_adjusted_performance

# Explicit project preferences. These are decision preferences, not laws of physics.
OBJECTIVE_PROFILES = {
    "Balanced project fit": {"lifetime_relative":0.55,"risk_relative":0.20,"area_lifetime_relative":0.15,"readiness_absolute":0.10},
    "Lifetime energy": {"lifetime_relative":0.75,"annual_yield_relative":0.15,"degradation_relative":0.10},
    "Economic value": {"value_relative":0.55,"lifetime_relative":0.25,"risk_relative":0.10,"readiness_absolute":0.10},
    "Lowest climate risk": {"degradation_relative":0.35,"temperature_relative":0.30,"risk_relative":0.20,"readiness_absolute":0.15},
    "Area-constrained project": {"area_lifetime_relative":0.70,"area_annual_relative":0.20,"degradation_relative":0.10},
}


def _commercial_readiness(tech: pd.Series) -> float:
    status=STATUS_SCORE.get(str(tech.get("commercialization_status","")).lower(),50.0)
    return bounded(0.45*float(tech.get("maturity_score",50))+0.35*float(tech.get("bankability_score",50))+0.20*status)


def filter_candidate_universe(technology_df: pd.DataFrame, mode: str="Commercial deployment", include_niche: bool=False, include_bifacial: bool=False) -> pd.DataFrame:
    """Preserve the full Solaryn database while choosing an appropriate active universe."""
    df=technology_df.copy()
    if mode=="R&D exploration": return df.reset_index(drop=True)
    status=df["commercialization_status"].astype(str).str.lower()
    commercial=status.isin(["commercial","commercial_niche"]) if include_niche else status.eq("commercial")
    df=df[(pd.to_numeric(df["TRL_level"],errors="coerce").fillna(0)>=8)&commercial]
    if not include_bifacial:
        df=df[~df["technology_name"].astype(str).str.contains("bifacial",case=False,na=False)]
    return df.reset_index(drop=True)


def _relative_score(series: pd.Series, higher_is_better: bool=True) -> pd.Series:
    s=pd.to_numeric(series,errors="coerce").astype(float)
    if s.isna().all(): return pd.Series(np.full(len(s),50.0),index=s.index)
    s=s.fillna(s.median()); lo=float(s.min()); hi=float(s.max())
    out=pd.Series(np.full(len(s),50.0),index=s.index) if abs(hi-lo)<1e-12 else (s-lo)/(hi-lo)*100.0
    return (out if higher_is_better else 100.0-out).clip(0,100)


def score_technology(site: pd.Series, tech: pd.Series, weather: pd.DataFrame | None=None) -> Dict:
    """Compute raw physical and database metrics; no material-quality score enters the winner."""
    perf=site_adjusted_performance(site,tech,weather=weather)
    readiness=_commercial_readiness(tech)
    cost=float(tech.get("module_cost_usd_w",np.nan))
    if not np.isfinite(cost) or cost<=0: cost=np.nan
    cost_energy_proxy=cost/max(float(perf["lifetime_energy_index_25y"]),1e-9)*1000.0 if np.isfinite(cost) else np.nan
    eff=max(float(tech.get("efficiency_commercial_percent",0.0)),0.0)/100.0
    annual_m2=float(perf["annual_yield_kwh_kwp"])*eff
    lifetime_m2=float(perf["lifetime_energy_index_25y"])*eff
    source_quality=str(tech.get("source_quality","unknown"))
    reasons=[
        f"Full-year modeled specific yield: {perf['annual_yield_kwh_kwp']:.0f} kWh/kWp.",
        f"25-year average-year energy index: {perf['lifetime_energy_index_25y']:.0f} using the common project degradation scenario.",
    ]
    if bool(perf.get("spectral_model_applied",False)):
        reasons.append(f"Technology-class spectral correction applied ({perf['spectral_model_note']}).")
    risks=[]
    if source_quality.lower()!="validated": risks.append(f"Technology parameters are tagged '{source_quality}' in the Solaryn database; verify before EPC procurement use.")
    if not bool(perf.get("spectral_model_applied",False)):
        risks.append("No validated default spectral class is applied for this technology in the compact screening model.")
    if float(perf.get("degradation_stress_factor",1.0))>3.0:
        risks.append("Environmental degradation-stress proxy is elevated; it is diagnostic and not a calibrated annual degradation rate.")
    return {
        "technology_id":tech["technology_id"],"technology_name":tech["technology_name"],"family":tech["family"],"subfamily":tech.get("subfamily",""),
        "TRL_level":float(tech.get("TRL_level",0)),"commercialization_status":tech.get("commercialization_status",""),
        "source_quality":source_quality,"source_url":tech.get("source_url",""),
        "module_cost_usd_w":cost,"module_efficiency_pct":eff*100.0,
        "annual_yield_kwh_m2":round(annual_m2,2),"lifetime_energy_index_kwh_m2":round(lifetime_m2,2),
        "commercial_readiness_score":round(readiness,2),
        "module_cost_to_lifetime_energy_proxy":round(cost_energy_proxy,6) if np.isfinite(cost_energy_proxy) else np.nan,
        **perf,"reasons":reasons,"risks":risks,
    }


def objective_weights(objective: str, budget_level: str="medium") -> Dict[str,float]:
    return dict(OBJECTIVE_PROFILES.get(objective,OBJECTIVE_PROFILES["Lifetime energy"]))


def _add_scores(df: pd.DataFrame, objective: str) -> Tuple[pd.DataFrame,Dict[str,float]]:
    out=df.copy()
    out["lifetime_relative"]=_relative_score(out["lifetime_energy_index_25y"],True)
    out["annual_yield_relative"]=_relative_score(out["annual_yield_kwh_kwp"],True)
    out["degradation_relative"]=_relative_score(out["adjusted_degradation_pct_year"],False)
    out["temperature_relative"]=_relative_score(out["temperature_loss_pct"],False)
    out["area_annual_relative"]=_relative_score(out["annual_yield_kwh_m2"],True)
    out["area_lifetime_relative"]=_relative_score(out["lifetime_energy_index_kwh_m2"],True)
    out["readiness_absolute"]=pd.to_numeric(out["commercial_readiness_score"],errors="coerce").fillna(50).clip(0,100)
    out["value_relative"]=_relative_score(out["module_cost_to_lifetime_energy_proxy"],False)
    # Risk is deliberately compact: measured/modelled temperature behavior + baseline degradation + commercial readiness.
    out["risk_relative"]=(0.45*out["degradation_relative"]+0.35*out["temperature_relative"]+0.20*out["readiness_absolute"]).clip(0,100)
    # Preserve the three decision lenses without using material 'physics quality' or generic 0.75 confidence.
    out["best_lifetime_score"]=(0.80*out["lifetime_relative"]+0.20*out["degradation_relative"]).clip(0,100).round(2)
    out["best_value_score"]=(0.70*out["value_relative"]+0.20*out["lifetime_relative"]+0.10*out["readiness_absolute"]).clip(0,100).round(2)
    out["lowest_risk_score"]=out["risk_relative"].round(2)
    weights=objective_weights(objective)
    score=pd.Series(np.zeros(len(out)),index=out.index,dtype=float)
    for metric,w in weights.items(): score += out[metric]*float(w)
    out["project_fit_score"]=score.round(2)
    out["project_rank"]=out["project_fit_score"].rank(method="first",ascending=False).astype(int)
    return out,weights


def _explain(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy(); rr=[]; tt=[]
    for _,r in out.iterrows():
        reasons=[]; trade=[]
        if r["lifetime_relative"]>=70: reasons.append("Strong modeled lifetime-specific energy among active candidates.")
        if r["annual_yield_relative"]>=70: reasons.append("Strong modeled annual specific yield under the same site weather.")
        if r["temperature_relative"]>=70: reasons.append("Favourable temperature response relative to the active candidates.")
        if r["area_lifetime_relative"]>=70: reasons.append("Strong lifetime-energy density for area-constrained projects.")
        if pd.notna(r["module_cost_usd_w"]) and r["value_relative"]>=70: reasons.append("Strong database cost-to-lifetime-energy proxy; replace with actual EPC quote for commercial use.")
        if r["source_quality"]!="validated": trade.append("Database values are literature-range/assumption level rather than module-specific validated inputs.")
        if not r["spectral_model_applied"]: trade.append("Spectral differentiation is not modeled for this technology class in the compact screening.")
        if not reasons: reasons.append("Competitive result under the selected objective, but no dominant physical advantage was identified.")
        if not trade: trade.append("No major model-boundary flag triggered; module-specific validation is still required.")
        rr.append(reasons[:3]); tt.append(trade[:3])
    out["decision_reasons"]=rr; out["tradeoffs"]=tt
    return out


def rank_technologies(site: pd.Series, technology_df: pd.DataFrame, weather: pd.DataFrame | None=None, objective: str="Lifetime energy", budget_level: str | None=None) -> pd.DataFrame:
    if technology_df.empty: raise ValueError("No technology candidates are available.")
    df=pd.DataFrame([score_technology(site,r,weather) for _,r in technology_df.iterrows()])
    df,weights=_add_scores(df,objective); df=_explain(df)
    df["lifetime_rank"]=df["best_lifetime_score"].rank(method="dense",ascending=False).astype(int)
    df["value_rank"]=df["best_value_score"].rank(method="dense",ascending=False).astype(int)
    df["risk_rank"]=df["lowest_risk_score"].rank(method="dense",ascending=False).astype(int)
    df.attrs["objective"]=objective; df.attrs["objective_weights"]=weights; df.attrs["budget_level"]=budget_level or str(site.get("budget_level","medium"))
    return df.sort_values(["project_rank","lifetime_rank","value_rank","risk_rank"]).reset_index(drop=True)


def decision_leaders(ranking: pd.DataFrame) -> dict:
    return {
        "best_lifetime":ranking.sort_values("best_lifetime_score",ascending=False).iloc[0],
        "best_value":ranking.sort_values("best_value_score",ascending=False).iloc[0],
        "lowest_risk":ranking.sort_values("lowest_risk_score",ascending=False).iloc[0],
    }


def project_decision_summary(ranking: pd.DataFrame) -> dict:
    if ranking.empty: raise ValueError("Ranking is empty.")
    ordered=ranking.sort_values("project_fit_score",ascending=False).reset_index(drop=True)
    winner=ordered.iloc[0]; runner=ordered.iloc[1] if len(ordered)>1 else winner
    gap=float(winner["project_fit_score"]-runner["project_fit_score"])
    raw_gap_pct=100.0*(float(winner["lifetime_energy_index_25y"])-float(runner["lifetime_energy_index_25y"]))/max(abs(float(runner["lifetime_energy_index_25y"])),1e-9)
    if abs(raw_gap_pct)<1.0: sep="Essentially tied on modeled lifetime energy"
    elif abs(raw_gap_pct)<3.0: sep="Close modeled result"
    else: sep="Separated in the current model"
    # Evidence gate: a numerical leader is not automatically a commercial recommendation.
    # Cross-family comparisons (e.g. c-Si vs CdTe) require measured electrical
    # response evidence for the leaders; otherwise we expose only a modeled leader.
    families=set(str(x).strip().lower() for x in ordered.get("family",pd.Series(dtype=str)).head(3) if str(x).strip())
    cross_family=len(families)>1
    measured_flags=[]
    if "electrical_model_measured" in ordered.columns:
        measured_flags=[bool(x) for x in ordered.head(min(2,len(ordered)))["electrical_model_measured"].tolist()]
    leaders_measured=bool(measured_flags) and all(measured_flags)
    source_validated=all(str(x).lower()=="validated" for x in ordered.head(min(2,len(ordered)))["source_quality"].tolist()) if "source_quality" in ordered.columns else False
    decision_eligible = (not cross_family and (leaders_measured or source_validated)) or (cross_family and leaders_measured)
    if decision_eligible:
        claim_level="screening result; decision-eligible modeled recommendation"
        withholding_reason=""
    elif cross_family:
        claim_level="screening result; exploratory cross-technology modeled leader; recommendation withheld"
        withholding_reason="Cross-technology leaders lack measured Pmax(G,T) evidence for both candidates."
    else:
        claim_level="screening result; modeled leader; recommendation withheld"
        withholding_reason="Candidate-specific measured electrical evidence is incomplete."
    return {
        "winner":winner,"top3":ordered.head(3),"score_gap_to_second":round(gap,2),
        "lifetime_energy_gap_to_second_pct":round(raw_gap_pct,2),"decision_separation_label":sep,
        "objective":ranking.attrs.get("objective","Lifetime energy"),
        "objective_weights":ranking.attrs.get("objective_weights",{}),
        "budget_level":ranking.attrs.get("budget_level","medium"),
        "scientific_status":claim_level,
        "decision_eligible":decision_eligible,
        "cross_family_comparison":cross_family,
        "withholding_reason":withholding_reason,
    }
