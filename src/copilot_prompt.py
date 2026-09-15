from __future__ import annotations
import json
import pandas as pd

def build_explanation_payload(site: pd.Series, leader_label: str, leader_row: pd.Series, ranking_df: pd.DataFrame, forecast_df: pd.DataFrame, decision_summary: dict | None=None) -> dict:
    payload={
        "site":{k:(float(site[k]) if k in ["latitude","longitude","system_size_mw","ghi_kwh_m2_year","avg_temp_c","max_temp_c","humidity_pct","rainfall_mm_year","dust_soiling_risk","salinity_risk"] else site[k]) for k in ["project_name","country","region","latitude","longitude","system_size_mw","ghi_kwh_m2_year","avg_temp_c","max_temp_c","humidity_pct","rainfall_mm_year","dust_soiling_risk","salinity_risk"]},
        "recommendation":{
            "objective":leader_label,"technology":leader_row["technology_name"],"project_fit_score":float(leader_row.get("project_fit_score",0)),
            "annual_yield_kwh_kwp":float(leader_row["annual_yield_kwh_kwp"]),"lifetime_energy_index_25y":float(leader_row["lifetime_energy_index_25y"]),
            "temperature_effect_pct":float(leader_row.get("temperature_effect_pct",0)),"spectral_effect_pct":float(leader_row.get("spectral_effect_pct",0)),
            "soiling_loss_pct":float(leader_row.get("soiling_loss_pct",0)),"adjusted_degradation_pct_year":float(leader_row["adjusted_degradation_pct_year"]),
            "degradation_stress_factor":float(leader_row.get("degradation_stress_factor",1)),"source_quality":leader_row.get("source_quality","unknown"),
            "reasons":leader_row.get("decision_reasons",leader_row.get("reasons",[])),"tradeoffs":leader_row.get("tradeoffs",leader_row.get("risks",[])),
        },
        "forecast":{"year_1_yield_kwh":float(forecast_df.iloc[0]["annual_yield_kwh"]),"year_25_yield_kwh":float(forecast_df.iloc[-1]["annual_yield_kwh"]),"year_25_retained_performance_pct":float(forecast_df.iloc[-1]["retained_performance_pct"]),"cumulative_25_year_yield_kwh":float(forecast_df.iloc[-1]["cumulative_yield_kwh"])},
        "ranking":ranking_df[["technology_name","project_fit_score","annual_yield_kwh_kwp","lifetime_energy_index_25y","temperature_effect_pct","spectral_effect_pct","adjusted_degradation_pct_year","source_quality"]].head(10).to_dict(orient="records"),
    }
    if decision_summary is not None:
        payload["decision_status"]={"separation":decision_summary["decision_separation_label"],"lifetime_gap_pct":float(decision_summary["lifetime_energy_gap_to_second_pct"]),"scientific_status":decision_summary["scientific_status"]}
        payload["objective_weights"]=decision_summary.get("objective_weights",{})
    return payload

def local_copilot_explanation(payload: dict) -> str:
    s=payload["site"]; r=payload["recommendation"]; f=payload["forecast"]; d=payload.get("decision_status",{})
    why="\n".join("- "+x for x in r["reasons"]); trade="\n".join("- "+x for x in r["tradeoffs"])
    return f"""For the **{r['objective']}** objective, the current Solaryn screening model ranks **{r['technology']}** first at {s['region']}.

Physical result:
- Annual specific yield: {r['annual_yield_kwh_kwp']:.0f} kWh/kWp
- 25-year average-year energy index: {r['lifetime_energy_index_25y']:.0f}
- Temperature effect: {r['temperature_effect_pct']:+.2f}% relative to 25 °C reference
- Spectral effect: {r['spectral_effect_pct']:+.2f}%
- Common site soiling loss: {r['soiling_loss_pct']:.2f}%
- Database degradation scenario: {r['adjusted_degradation_pct_year']:.2f}%/year
- Environmental stress proxy: {r['degradation_stress_factor']:.2f}× (diagnostic only)
- Database source quality: {r['source_quality']}

Decision separation: {d.get('separation','not calculated')} ({d.get('lifetime_gap_pct',0):+.2f}% lifetime-energy gap to #2).

Why:
{why}

Trade-offs / validation:
{trade}

25-year scenario for {s['system_size_mw']:g} MW: year-1 {f['year_1_yield_kwh']:,.0f} kWh; year-25 retained {f['year_25_retained_performance_pct']:.1f}%; cumulative {f['cumulative_25_year_yield_kwh']:,.0f} kWh.

This is a research hypothesis, not a procurement recommendation or bankability opinion. Material and device data cannot determine a commercial decision until validated.""".strip()

def azure_openai_prompt(payload: dict) -> str:
    return f"""You are Solaryn AI Copilot. Explain the deterministic screening result using only supplied data. Do not invent values, do not call a score scientific confidence, and do not claim bankability validation. Make clear that material/device diagnostics are preserved but do not directly force the commercial ranking. Structured input:
{json.dumps(payload,indent=2)}""".strip()
