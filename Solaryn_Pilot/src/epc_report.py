from __future__ import annotations

from html import escape
import math
from typing import Iterable
import pandas as pd


def _fmt(v, digits=2):
    try:
        x = float(v)
        if not math.isfinite(x):
            return "—"
        return f"{x:,.{digits}f}"
    except Exception:
        return escape(str(v))


def _safe_url(v) -> str:
    text = str(v or "").strip()
    if not text or text.lower() == "nan":
        return ""
    return escape(text, quote=True)


def _label(row: pd.Series) -> str:
    return " ".join(x for x in [str(row.get("manufacturer", "")).strip(), str(row.get("model", "")).strip()] if x)


def _svg_hbar(items: Iterable[tuple[str, float]], *, width: int = 860, row_h: int = 34, suffix: str = "", decimals: int = 0) -> str:
    clean = [(str(k), float(v)) for k, v in items if v is not None and math.isfinite(float(v))]
    if not clean:
        return "<p class='muted'>No chart data available.</p>"
    clean = sorted(clean, key=lambda x: x[1], reverse=True)
    maxv = max(v for _, v in clean) or 1.0
    left = 245
    right = 115
    chart_w = width - left - right
    height = 36 + row_h * len(clean)
    parts = [f"<svg class='chart' viewBox='0 0 {width} {height}' role='img'>"]
    for i, (name, value) in enumerate(clean):
        y = 22 + i * row_h
        bw = max(1.0, chart_w * value / maxv)
        parts.append(f"<text x='0' y='{y+15}' class='svg-label'>{escape(name[:38])}</text>")
        parts.append(f"<rect x='{left}' y='{y}' width='{chart_w}' height='20' rx='7' class='bar-bg'/>")
        parts.append(f"<rect x='{left}' y='{y}' width='{bw:.1f}' height='20' rx='7' class='bar'/>")
        parts.append(f"<text x='{left+chart_w+8}' y='{y+15}' class='svg-value'>{value:,.{decimals}f}{escape(suffix)}</text>")
    parts.append("</svg>")
    return "".join(parts)


def _svg_line(series: dict[str, list[tuple[float, float]]], *, width: int = 860, height: int = 300, y_suffix: str = "") -> str:
    points = [(x, y) for vals in series.values() for x, y in vals if math.isfinite(float(x)) and math.isfinite(float(y))]
    if not points:
        return "<p class='muted'>No chart data available.</p>"
    xmin, xmax = min(x for x, _ in points), max(x for x, _ in points)
    ymin, ymax = min(y for _, y in points), max(y for _, y in points)
    if xmax == xmin: xmax += 1
    if ymax == ymin: ymax += 1
    l, r, t, b = 58, 24, 28, 48
    pw, ph = width-l-r, height-t-b
    def sx(x): return l + (x-xmin)/(xmax-xmin)*pw
    def sy(y): return t + (ymax-y)/(ymax-ymin)*ph
    parts=[f"<svg class='chart' viewBox='0 0 {width} {height}' role='img'>"]
    for j in range(5):
        v=ymin+(ymax-ymin)*j/4
        yy=sy(v)
        parts.append(f"<line x1='{l}' y1='{yy:.1f}' x2='{width-r}' y2='{yy:.1f}' class='grid'/>")
        parts.append(f"<text x='{l-8}' y='{yy+4:.1f}' text-anchor='end' class='axis'>{v:,.0f}{escape(y_suffix)}</text>")
    colors=["#0e776d","#1662a4","#b47b00","#7a4fa3","#d45644","#3d8e3d","#6b7280","#b83c82","#2384a8","#845d24"]
    for idx,(name, vals) in enumerate(series.items()):
        pts=" ".join(f"{sx(float(x)):.1f},{sy(float(y)):.1f}" for x,y in vals if math.isfinite(float(y)))
        if pts:
            parts.append(f"<polyline points='{pts}' fill='none' stroke='{colors[idx%len(colors)]}' stroke-width='2.5' stroke-linejoin='round' stroke-linecap='round'/>")
    # x labels for integer-like ranges (months/years)
    tick_count=min(12, max(2, int(round(xmax-xmin))+1))
    for j in range(tick_count):
        x=xmin+(xmax-xmin)*j/max(tick_count-1,1)
        parts.append(f"<text x='{sx(x):.1f}' y='{height-18}' text-anchor='middle' class='axis'>{int(round(x))}</text>")
    # compact legend
    lx=l
    ly=13
    for idx,name in enumerate(series):
        parts.append(f"<circle cx='{lx}' cy='{ly}' r='4' fill='{colors[idx%len(colors)]}'/>")
        parts.append(f"<text x='{lx+8}' y='{ly+4}' class='legend'>{escape(name[:24])}</text>")
        lx += 142
        if lx > width-150:
            lx=l; ly += 15
    parts.append("</svg>")
    return "".join(parts)


def _svg_signed_hbar(items: Iterable[tuple[str, float]], *, width: int = 860, row_h: int = 38, suffix: str = " pp") -> str:
    """Centered horizontal bars for top-two driver deltas."""
    clean = [(str(k), float(v)) for k, v in items if v is not None and math.isfinite(float(v))]
    if not clean:
        return "<p class='muted'>Driver decomposition is unavailable for this run.</p>"
    maxabs = max(abs(v) for _, v in clean) or 1.0
    label_w = 245
    plot_w = width - label_w - 90
    zero_x = label_w + plot_w / 2
    height = 36 + row_h * len(clean)
    parts = [f"<svg class='chart' viewBox='0 0 {width} {height}' role='img'>"]
    parts.append(f"<line x1='{zero_x:.1f}' y1='12' x2='{zero_x:.1f}' y2='{height-8}' class='grid'/>")
    for i, (name, value) in enumerate(clean):
        y = 22 + i * row_h
        half = plot_w / 2
        bw = half * abs(value) / maxabs
        x = zero_x if value >= 0 else zero_x - bw
        parts.append(f"<text x='0' y='{y+15}' class='svg-label'>{escape(name[:38])}</text>")
        parts.append(f"<rect x='{x:.1f}' y='{y}' width='{max(1.0,bw):.1f}' height='20' rx='6' class='bar'/>")
        parts.append(f"<text x='{label_w+plot_w+8}' y='{y+15}' class='svg-value'>{value:+.2f}{escape(suffix)}</text>")
    parts.append("</svg>")
    return "".join(parts)


def _monthly_profile(hourly: pd.DataFrame | None, modules: pd.DataFrame) -> pd.DataFrame:
    if hourly is None or hourly.empty or "module_id" not in hourly.columns:
        return pd.DataFrame()
    h = hourly.copy()
    if "timestamp" in h.columns:
        ts = pd.to_datetime(h["timestamp"], utc=True, errors="coerce")
    elif "time_utc" in h.columns:
        ts = pd.to_datetime(h["time_utc"], utc=True, errors="coerce")
    elif isinstance(h.index, pd.DatetimeIndex):
        ts = pd.to_datetime(h.index, utc=True, errors="coerce")
    else:
        return pd.DataFrame()
    h["month_num"] = ts.dt.month
    h["specific_power_kw_per_kwp"] = pd.to_numeric(h.get("specific_power_kw_per_kwp"), errors="coerce")
    weights = pd.to_numeric(h.get("days_weight", 1.0), errors="coerce")
    if not isinstance(weights, pd.Series):
        weights = pd.Series(float(weights), index=h.index)
    h["weighted_specific_energy"] = h["specific_power_kw_per_kwp"] * weights.fillna(1.0)
    out = (
        h.dropna(subset=["month_num", "weighted_specific_energy"])
         .groupby(["module_id", "month_num"], as_index=False)["weighted_specific_energy"].sum()
    )
    names = modules.assign(display=modules["manufacturer"].astype(str)+" "+modules["model"].astype(str))[["module_id","display"]]
    return out.merge(names,on="module_id",how="left").rename(columns={"weighted_specific_energy":"monthly_specific_energy_kwh_kwp"})


def build_epc_html_report(
    site: dict,
    project: dict,
    results: pd.DataFrame,
    decision: dict,
    modules: pd.DataFrame,
    stress: pd.DataFrame,
    switching: pd.DataFrame | None = None,
    pvgis_note: str | None = None,
    hourly: pd.DataFrame | None = None,
) -> str:
    """Create a board/client-ready executive recommendation report with embedded charts."""
    keep = [
        "module_id", "manufacturer", "model", "technology_label", "pmax_w",
        "module_efficiency_pct", "gamma_pmax_pct_c", "first_year_retention_pct",
        "annual_warranty_degradation_pct_year", "quote_usd_w", "source_url",
        "evidence_status", "project_segment", "spectral_evidence_level",
        "iec61853_matrix_file", "evidence_tier", "verification_note",
        "bifaciality_factor", "bifaciality_tolerance_pct_points", "bifaciality_source",
    ]
    keep = [c for c in keep if c in modules.columns]
    join_cols = [c for c in ["module_id", "manufacturer", "model", "technology_label"] if c in keep]
    merged = results.merge(modules[keep], on=join_cols, how="left")

    sort_col = "lifetime_energy_common_degradation_scenario_kwh_kwp"
    rows = []
    for _, r in merged.sort_values(sort_col, ascending=False).iterrows():
        pbest = decision.get("probability_by_candidate_pct", {}).get(str(r["module_id"]), float("nan"))
        rows.append(
            "<tr>"
            f"<td><strong>{escape(str(r['manufacturer']))} {escape(str(r['model']))}</strong><br><span class='muted'>{escape(str(r.get('technology_label','')))}</span></td>"
            f"<td>{_fmt(r.get('annual_dc_specific_energy_broadband_kwh_kwp'),0)}</td>"
            f"<td>{_fmt(r.get('annual_project_dc_energy_mwh'),0)}</td>"
            f"<td>{_fmt(r.get('lifetime_energy_common_degradation_scenario_kwh_kwp'),0)}</td>"
            f"<td>{(_fmt(pbest,1) + '%') if math.isfinite(float(pbest)) else '—'}</td>"
            f"<td>{_fmt(r.get('p95_cell_temperature_c_daylight'),1)}°C</td>"
            f"<td>{escape(str(r.get('model_evidence_level','')))}</td>"
            f"<td>{'Yes' if bool(r.get('decision_eligible', False)) else 'No'}</td>"
            "</tr>"
        )

    econ_html = "<p class='muted'>Switching economics are unavailable until the baseline offer includes a supplier quote.</p>"
    if switching is not None and not switching.empty:
        erows = []
        for _, r in switching.iterrows():
            erows.append(
                "<tr>"
                f"<td>{escape(str(r['manufacturer']))} {escape(str(r['model']))}</td>"
                f"<td>{_fmt(r.get('actual_quote_usd_w'),4)}</td>"
                f"<td>{_fmt(r.get('indifference_module_price_usd_w'),4)}</td>"
                f"<td>{_fmt(r.get('allowable_module_price_premium_vs_baseline_usd_w'),4)}</td>"
                f"<td>{escape(str(r.get('economic_evidence_note','')))}</td>"
                "</tr>"
            )
        econ_html = "<table><thead><tr><th>Candidate</th><th>Quote $/W</th><th>Indifference $/W</th><th>Max premium $/W</th><th>Evidence status</th></tr></thead><tbody>" + "".join(erows) + "</tbody></table>"

    stress_rows = []
    for _, r in stress.iterrows():
        stress_rows.append(
            "<tr>"
            f"<td>{escape(str(r['manufacturer']))} {escape(str(r['model']))}</td>"
            f"<td>{int(r.get('hot_cell_hours_gt_65c',0))}</td>"
            f"<td>{int(r.get('hot_humid_hours_rh85_t40',0))}</td>"
            f"<td>{_fmt(r.get('mean_daily_cell_temp_range_c'),1)}</td>"
            f"<td>{int(r.get('days_cell_temp_range_gt_30c',0))}</td>"
            "</tr>"
        )

    evidence_items = []
    for _, r in modules.iterrows():
        name = f"{escape(str(r.get('manufacturer','')))} {escape(str(r.get('model','')))}"
        url = _safe_url(r.get("source_url", ""))
        status = escape(str(r.get("evidence_status", "")))
        evidence_items.append(f"<li><strong>{name}</strong> — {status}" + (f" · <a href='{url}'>source</a>" if url else "") + "</li>")

    # Charts
    annual_chart = _svg_hbar(
        [(_label(r), r.get("annual_yield_kwh_kwp", float("nan"))) for _,r in merged.iterrows()],
        suffix="", decimals=0,
    )
    pbest_map=decision.get("probability_by_candidate_pct", {}) or {}
    pbest_chart = _svg_hbar(
        [(_label(r), pbest_map.get(str(r.get("module_id")), float("nan"))) for _,r in merged.iterrows()],
        suffix="%", decimals=1,
    )
    exploratory_map = decision.get("exploratory_probability_by_candidate_pct", {}) or {}
    exploratory_chart = _svg_hbar(
        [(_label(r), exploratory_map.get(str(r.get("module_id")), float("nan"))) for _,r in merged.iterrows()],
        suffix="%", decimals=1,
    )

    decision_rows = merged[merged.get("decision_eligible", False).fillna(False).astype(bool)].copy() if "decision_eligible" in merged.columns else merged.copy()
    decision_rows = decision_rows.sort_values("annual_yield_kwh_kwp", ascending=False)
    driver_deltas = []
    driver_text = "Driver comparison requires at least two decision-eligible candidates."
    if len(decision_rows) >= 2:
        lead = decision_rows.iloc[0]
        runner = decision_rows.iloc[1]
        driver_specs = [
            ("Off-STC irradiance response", "off_stc_irradiance_response_pct"),
            ("Temperature response", "temperature_response_effect_pct"),
            ("Rear-side contribution", "bifacial_rear_gain_pct"),
            ("Front geometry / IAM", "iam_effect_pct"),
        ]
        for label, col in driver_specs:
            a = pd.to_numeric(pd.Series([lead.get(col)]), errors="coerce").iloc[0]
            b = pd.to_numeric(pd.Series([runner.get(col)]), errors="coerce").iloc[0]
            if pd.notna(a) and pd.notna(b):
                driver_deltas.append((label, float(a-b)))
        driver_text = (
            f"Positive values favor {escape(_label(lead))}; negative values favor {escape(_label(runner))}. "
            "These ablation deltas are diagnostics and are not assumed to add exactly to the annual-energy gap."
        )
    driver_chart = _svg_signed_hbar(driver_deltas)
    stress_chart = _svg_hbar(
        [(f"{r.get('manufacturer','')} {r.get('model','')}", r.get("hot_cell_hours_gt_65c", 0)) for _,r in stress.iterrows()],
        suffix=" h", decimals=0,
    )
    degradation=float(project.get("common_degradation_pct_year",0.5))/100.0
    lifetime_series={}
    for _,r in merged.iterrows():
        annual=float(r.get("annual_yield_kwh_kwp",float("nan")))
        if math.isfinite(annual):
            vals=[]
            start_ret=1.0
            for year in range(1,26):
                end_ret=start_ret*(1-degradation)
                vals.append((year, annual*0.5*(start_ret+end_ret)))
                start_ret=end_ret
            lifetime_series[_label(r)] = vals
    lifetime_chart=_svg_line(lifetime_series,y_suffix="")

    monthly=_monthly_profile(hourly,modules)
    monthly_series={}
    if not monthly.empty:
        for name,g in monthly.groupby("display"):
            monthly_series[str(name)]=[(float(x),float(y)) for x,y in zip(g["month_num"],g["monthly_specific_energy_kwh_kwp"])]
    monthly_chart=_svg_line(monthly_series,y_suffix="")

    ineligible = ", ".join(map(str, decision.get("decision_ineligible_module_ids", []))) or "none"
    project_segment = escape(str(project.get("project_segment", "not specified")))
    technical = " ".join(x for x in [str(decision.get("technical_leader_manufacturer", "")).strip(), str(decision.get("technical_leader_model", "")).strip()] if x) or escape(str(decision.get("technical_leader_module_id", "not available")))
    decision_status=escape(str(decision.get("decision_status", decision.get("status", ""))))
    evidence_complete=bool(decision.get("evidence_complete_for_all_selected_candidates",False))
    resource_confidence = escape(str(decision.get("resource_confidence", "Not checked")))
    resource_reason = escape(str(decision.get("resource_confidence_reason", "")))
    lifetime_status = escape(str(decision.get("lifetime_status", "Not differentiated — neutral common degradation sensitivity only")))
    exploratory_leader_id = str(decision.get("exploratory_technical_leader_module_id", ""))
    decision_leader_id = str(decision.get("technical_leader_module_id", ""))
    exploratory_note = ""
    if exploratory_leader_id and exploratory_leader_id != decision_leader_id:
        exploratory_note = f"<div class='warn'><strong>Exploratory leader differs from the decision frontier.</strong> Numerical exploratory leader: {escape(exploratory_leader_id)}. It is not promoted into the procurement recommendation because its model/evidence path does not pass the decision gate.</div>"

    gate_specs = [
        ("Independent resource agreement", decision.get("resource_confidence") == "High", decision.get("resource_confidence_reason", "")),
        ("Multi-year resource history", bool(decision.get("resource_history_ready_for_robust", False)), "Shared empirical interannual scenarios from at least two complete resource years."),
        ("Off-STC electrical evidence", bool(decision.get("robust_evidence_ready", False)), decision.get("robust_evidence_reason", "")),
        ("Thermal evidence", bool(decision.get("robust_thermal_ready", False)), decision.get("robust_thermal_reason", "")),
        ("Project geometry", bool(decision.get("geometry_ready_for_robust", False)), f"Geometry evidence: {str(decision.get('geometry_confidence','screening_assumptions')).replace('_',' ')}."),
        ("Decision-material rear side", bool(decision.get("robust_rear_ready", False)), decision.get("robust_rear_reason", "")),
    ]
    gate_html = "".join(
        "<tr>"
        f"<td><strong>{escape(str(name))}</strong></td>"
        f"<td>{'READY' if ready else 'OPEN'}</td>"
        f"<td>{escape(str(reason))}</td>"
        "</tr>"
        for name, ready, reason in gate_specs
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solaryn Executive Recommendation Report</title>
<style>
:root{{--ink:#142033;--muted:#637083;--brand:#0e776d;--brand2:#0b4f48;--line:#dce5e8;--soft:#f4f9f8;--warn:#fff7e2}}
*{{box-sizing:border-box}}body{{font-family:Inter,Arial,sans-serif;max-width:1220px;margin:0 auto;color:var(--ink);line-height:1.5;padding:34px 28px;background:white}}
h1{{font-size:34px;margin:0 0 8px;color:var(--brand2)}}h2{{font-size:22px;color:var(--brand2);margin:36px 0 10px}}h3{{font-size:16px;margin:18px 0 8px}}
.kicker{{letter-spacing:.12em;text-transform:uppercase;font-weight:700;font-size:12px;color:var(--brand)}}.sub{{font-size:17px;color:var(--muted);margin:0 0 22px}}
.hero{{padding:24px;background:linear-gradient(135deg,#eef8f6,#f8fbfb);border:1px solid #cfe3df;border-radius:18px;margin:18px 0 24px}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.metric{{border:1px solid var(--line);border-radius:14px;padding:14px;background:white}}.metric b{{font-size:22px;display:block;color:var(--brand2)}}.metric span{{font-size:12px;color:var(--muted)}}
.warn{{padding:16px 18px;background:var(--warn);border-left:4px solid #d99a00;margin:16px 0;border-radius:8px}}.ok{{padding:16px 18px;background:#eef9f3;border-left:4px solid #1d8a5b;margin:16px 0;border-radius:8px}}
table{{border-collapse:collapse;width:100%;margin:12px 0 24px;font-size:12.5px}}th,td{{border-bottom:1px solid var(--line);padding:9px 8px;text-align:left;vertical-align:top}}th{{background:#eef5f3;color:#24443f;position:sticky;top:0}}
.muted{{color:var(--muted);font-size:12px}}.status{{font-size:24px;font-weight:800;color:var(--brand)}}.chart-card{{border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:12px 0;overflow:hidden}}.chart{{width:100%;height:auto}}.bar{{fill:#0e776d}}.bar-bg{{fill:#e9f0f0}}.svg-label{{font:12px Arial;fill:#304050}}.svg-value{{font:bold 12px Arial;fill:#173b37}}.grid{{stroke:#e5ecee;stroke-width:1}}.axis{{font:10px Arial;fill:#6b7785}}.legend{{font:10px Arial;fill:#43505f}}
a{{color:#0b6f68;text-decoration:none}}.footer{{margin-top:38px;border-top:1px solid var(--line);padding-top:14px;color:var(--muted);font-size:11px}}
@media(max-width:800px){{.grid4{{grid-template-columns:1fr 1fr}}body{{padding:22px 14px}}}}
</style></head><body>
<div class="kicker">SOLARYN · EXECUTIVE DECISION REPORT</div>
<h1>{escape(str(project.get('project_name','Project')))}</h1>
<p class="sub">PV module decision intelligence · site-specific physics · evidence-aware uncertainty · procurement value</p>

<div class="hero"><div class="status">{decision_status}</div>
<h3>Decision-frontier technical leader — {escape(technical)}</h3>
<p>{escape(str(decision.get('headline','')))}</p>
<div class="grid4">
<div class="metric"><b>{_fmt(decision.get('probability_of_best_pct'),1)}%</b><span>Decision-frontier P(best)</span></div>
<div class="metric"><b>{_fmt(decision.get('expected_regret_pct'),2)}%</b><span>Expected regret</span></div>
<div class="metric"><b>{resource_confidence}</b><span>Independent resource confidence</span></div>
<div class="metric"><b>{'Complete' if evidence_complete else 'Limited'}</b><span>All-selected evidence gate</span></div>
</div>
<p><strong>Resource:</strong> {resource_reason}<br><strong>Electrical gate:</strong> {escape(str(decision.get('robust_evidence_reason','')))}<br><strong>Thermal gate:</strong> {escape(str(decision.get('robust_thermal_reason','')))}<br><strong>Geometry evidence:</strong> {escape(str(decision.get('geometry_confidence','screening_assumptions')).replace('_',' '))}<br><strong>Rear-side gate:</strong> {escape(str(decision.get('robust_rear_reason','')))}</p>
<p><strong>Next evidence request:</strong> {escape(str(decision.get('next_evidence_request','')))}</p></div>
{exploratory_note}

<h2>Decision robustness gates</h2>
<table><thead><tr><th>Gate</th><th>Status</th><th>Reason</th></tr></thead><tbody>{gate_html}</tbody></table>
<p class="muted">These gates control recommendation claim strength only. They do not add hidden bonuses or penalties to modeled energy.</p>

<h2>1. Project snapshot</h2>
<div class="grid4">
<div class="metric"><b>{site.get('latitude')}, {site.get('longitude')}</b><span>Coordinates</span></div>
<div class="metric"><b>{_fmt(project.get('system_size_mw'),1)} MWp</b><span>DC project size</span></div>
<div class="metric"><b>{escape(str(project.get('resource_start_year', project.get('reference_year'))))}–{escape(str(project.get('reference_year')))}</b><span>Resource period</span></div>
<div class="metric"><b>{project_segment}</b><span>Project segment</span></div>
</div>
<p class="muted">Geometry: fixed tilt {project.get('tilt_deg')}° · azimuth {project.get('azimuth_deg')}° · row/rear model {'enabled' if project.get('row_geometry_enabled') else 'disabled'} · albedo {project.get('albedo','—')} · GCR {project.get('gcr','—')} · common soiling {project.get('soiling_loss_pct')}%.</p>

<h2>2. Annual energy comparison</h2><div class="chart-card">{annual_chart}</div>
<p class="muted">Modeled DC specific energy under one common project geometry. Rear-side contribution is only activated from explicit geometry + product bifaciality evidence; technology-class spectral proxies do not make the primary winner.</p>

<h2>3. Seasonal production profile</h2><div class="chart-card">{monthly_chart}</div>
<p class="muted">Monthly specific-energy profile derived from the hourly physics run. Month labels 1–12.</p>

<h2>4. Decision-frontier Probability of best</h2><div class="chart-card">{pbest_chart}</div>
<p class="muted">Only decision-eligible candidates appear in this procurement probability. Multi-year resource scenarios are shared across candidates when available; model uncertainty remains candidate-specific.</p>
<h3>Exploratory model probability — not a procurement probability</h3><div class="chart-card">{exploratory_chart}</div>
<p class="muted">Evidence-ineligible candidates remain visible here for falsification and evidence planning, but a wide exploratory distribution cannot create a procurement recommendation.</p>

<h2>5. 25-year neutral degradation sensitivity</h2><div class="chart-card">{lifetime_chart}</div>
<p class="muted"><strong>Lifetime status:</strong> {lifetime_status}. The same declared degradation sensitivity is applied to every candidate; this preserves scenario planning but does not claim product-specific lifetime differentiation. Warranty curves remain separate.</p>

<h2>6. Why the technical ranking changes</h2><div class="chart-card">{driver_chart}</div>
<p class="muted">{driver_text}</p>

<h2>7. Decision stack</h2>
<table><tbody>
<tr><th>Technical leader</th><td>{escape(technical)} · {_fmt(decision.get('decision_frontier_lead_over_second_pct', decision.get('annual_lead_over_second_pct')),2)}% annual lead over the next decision-eligible candidate</td></tr>
<tr><th>Lifetime differentiation</th><td>{lifetime_status}</td></tr>
<tr><th>Commercial leader</th><td>{'Available only through the quote-based switching table below.' if switching is not None and not switching.empty else 'Not established — supplier quotes are incomplete or unavailable.'}</td></tr>
<tr><th>Final recommendation</th><td>{escape(str(decision.get('recommended_module_id') or 'No procurement recommendation yet'))} · {decision_status}</td></tr>
</tbody></table>

<h2>8. Candidate scorecard</h2>
<table><thead><tr><th>Candidate</th><th>Annual DC kWh/kWp</th><th>Project MWh/y</th><th>25-y common scenario</th><th>P(best)</th><th>P95 cell T</th><th>Electrical evidence path</th><th>Decision eligible</th></tr></thead><tbody>{''.join(rows)}</tbody></table>

<h2>9. Environmental stress diagnostics</h2><div class="chart-card">{stress_chart}</div>
<table><thead><tr><th>Module</th><th>Hours Tcell &gt;65°C</th><th>Hot-humid hours</th><th>Mean daily T range</th><th>Days range &gt;30°C</th></tr></thead><tbody>{''.join(stress_rows)}</tbody></table>
<p class="muted">Exposure metrics are diagnostics only. They are not converted into annual degradation rates without matched BOM/field evidence.</p>

<h2>10. Procurement switching economics</h2>
<p>The switching value answers how much additional module price can be justified by modeled incremental project value relative to the selected baseline. It is a procurement sensitivity, not a complete bankable LCOE.</p>{econ_html}

<h2>11. Independent resource cross-check</h2><p><strong>Resource confidence: {resource_confidence}.</strong> {escape(pvgis_note or 'Cross-check not run.')}</p>

<h2>12. Evidence & model boundary</h2>
<div class="{'ok' if evidence_complete else 'warn'}"><strong>Decision evidence gate:</strong> {'All selected candidates passed the current model-evidence eligibility gate.' if evidence_complete else 'One or more selected candidates remain evidence-limited. A numerical technical leader must not be presented as a validated cross-technology commercial winner.'}<br><strong>Evidence-limited candidate IDs:</strong> {escape(ineligible)}.</div>
<ul>{''.join(evidence_items)}</ul>
<div class="warn"><strong>Validation boundary.</strong> Candidate-specific IEC 61853 or equivalent measured off-STC evidence is preferred. Datasheet-fitted crystalline-silicon models carry larger uncertainty. Bifaciality is only converted into energy through the declared rear-irradiance geometry; technology-class spectral effects and warranty slopes remain sensitivities unless product evidence supports decision use. The packaged external measured validation supports the P(G,T) electrical layer only; it does not by itself validate cross-technology ranking, lifetime, AC delivery, or procurement economics.</div>

<div class="footer">Generated by Solaryn. The report separates modeled technical leadership from the strength of evidence supporting the final decision.</div>
</body></html>"""
