from __future__ import annotations

from html import escape
import math
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


def build_epc_html_report(
    site: dict,
    project: dict,
    results: pd.DataFrame,
    decision: dict,
    modules: pd.DataFrame,
    stress: pd.DataFrame,
    switching: pd.DataFrame | None = None,
    pvgis_note: str | None = None,
) -> str:
    """Create an expert-reviewable PoC validation report with evidence diagnostics."""
    keep = [
        "module_id", "manufacturer", "model", "technology_label",
        "pmax_w", "module_efficiency_pct", "gamma_pmax_pct_c",
        "first_year_retention_pct", "annual_warranty_degradation_pct_year",
        "quote_usd_w", "source_url", "evidence_status", "project_segment",
        "spectral_evidence_level", "iec61853_matrix_file",
    ]
    keep = [c for c in keep if c in modules.columns]
    merged = results.merge(
        modules[keep],
        on=[c for c in ["module_id", "manufacturer", "model", "technology_label"] if c in keep],
        how="left",
    )
    sort_col = "lifetime_energy_common_degradation_scenario_kwh_kwp"
    rows = []
    for _, r in merged.sort_values(sort_col, ascending=False).iterrows():
        rows.append(
            "<tr>"
            f"<td>{escape(str(r['manufacturer']))} {escape(str(r['model']))}</td>"
            f"<td>{escape(str(r.get('technology_label', '')))}</td>"
            f"<td>{_fmt(r.get('annual_dc_specific_energy_broadband_kwh_kwp'),0)}</td>"
            f"<td>{_fmt(r.get('annual_dc_specific_energy_spectral_sensitivity_kwh_kwp'),0)}</td>"
            f"<td>{_fmt(r.get('annual_project_dc_energy_mwh'),0)}</td>"
            f"<td>{_fmt(r.get('lifetime_energy_common_degradation_scenario_kwh_kwp'),0)}</td>"
            f"<td>{_fmt(r.get('lifetime_energy_warranty_scenario_kwh_kwp'),0)}</td>"
            f"<td>{_fmt(r.get('spectral_effect_pct'),2)}%</td>"
            f"<td>{_fmt(r.get('p95_cell_temperature_c_daylight'),1)}°C</td>"
            f"<td>{escape(str(r.get('electrical_model', '')))}</td>"
            f"<td>{escape(str(r.get('model_evidence_level', '')))}</td>"
            f"<td>{'Yes' if bool(r.get('decision_eligible', False)) else 'No'}</td>"
            "</tr>"
        )

    econ_html = "<p>Economic switching analysis not run because quotes/assumptions were incomplete.</p>"
    if switching is not None and not switching.empty:
        erows = []
        for _, r in switching.iterrows():
            erows.append(
                "<tr>"
                f"<td>{escape(str(r['manufacturer']))} {escape(str(r['model']))}</td>"
                f"<td>{_fmt(r['actual_quote_usd_w'],4)}</td>"
                f"<td>{_fmt(r['indifference_module_price_usd_w'],4)}</td>"
                f"<td>{_fmt(r['indifference_module_price_warranty_sensitivity_usd_w'],4)}</td>"
                f"<td>{_fmt(r['allowable_module_price_premium_vs_baseline_usd_w'],4)}</td>"
                "</tr>"
            )
        econ_html = (
            "<table><thead><tr><th>Candidate</th><th>Actual quote $/W</th>"
            "<th>Primary indifference price $/W</th><th>Warranty-sensitivity threshold $/W</th>"
            "<th>Allowable premium vs baseline $/W</th>"
            "</tr></thead><tbody>" + "".join(erows) + "</tbody></table>"
        )

    stress_rows = []
    for _, r in stress.iterrows():
        stress_rows.append(
            "<tr>"
            f"<td>{escape(str(r['manufacturer']))} {escape(str(r['model']))}</td>"
            f"<td>{int(r['hot_cell_hours_gt_65c'])}</td>"
            f"<td>{int(r['hot_humid_hours_rh85_t40'])}</td>"
            f"<td>{_fmt(r['mean_daily_cell_temp_range_c'],1)}</td>"
            f"<td>{int(r['days_cell_temp_range_gt_30c'])}</td>"
            "</tr>"
        )

    evidence_items = []
    for _, r in modules.iterrows():
        name = f"{escape(str(r.get('manufacturer','')))} {escape(str(r.get('model','')))}"
        url = _safe_url(r.get("source_url", ""))
        status = escape(str(r.get("evidence_status", "")))
        if url:
            evidence_items.append(f"<li>{name}: <a href='{url}'>{status}</a></li>")
        else:
            evidence_items.append(f"<li>{name}: {status}</li>")

    ineligible = ", ".join(map(str, decision.get("decision_ineligible_module_ids", []))) or "none"
    project_segment = escape(str(project.get("project_segment", "not specified")))

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>SOLARYN V9.2.1 POC Validation Report</title>
<style>
body{{font-family:Arial,sans-serif;max-width:1200px;margin:36px auto;color:#172033;line-height:1.45}}
h1,h2{{color:#0b5f58}} .box{{padding:16px 18px;background:#f4f8f7;border-left:4px solid #0b766e;margin:16px 0}}
.warn{{padding:16px 18px;background:#fff7e6;border-left:4px solid #d97706;margin:16px 0}}
table{{border-collapse:collapse;width:100%;margin:12px 0 24px;font-size:13px}} th,td{{border:1px solid #d9e1e7;padding:7px;text-align:left;vertical-align:top}} th{{background:#eef4f3}}
small{{color:#5f6b78}}
</style></head><body>
<h1>SOLARYN V9.2.1 — POC Validation Module Comparison</h1>
<div class="box"><strong>Deterministic scientific conclusion:</strong> {escape(str(decision.get('headline')))}<br>
<strong>PoC workflow status:</strong> {escape(str(decision.get('status')))}<br>
<strong>Validation confidence:</strong> {escape(str(decision.get('validation_confidence', 'not assessed')))}<br>
<small>{escape(str(decision.get('claim_scope')))}. A nominal modeled leader is not automatically a robust winner; this is not a bankability opinion.</small></div>

<h2>Validation diagnostics</h2>
<ul>
<li>Validation threshold: {_fmt(decision.get('required_decision_gap_pct'),2)}%. In PoC mode this controls the confidence label; it does not suppress the provisional ranking.</li>
<li>All selected candidates have decision-grade evidence: {escape(str(decision.get('evidence_complete_for_all_selected_candidates')))}.</li>
<li>Candidates requiring stronger evidence before commercial/bankability claims: {escape(ineligible)}.</li>
<li>Secondary strict-evidence status: {escape(str(decision.get('robust_status', 'not assessed')))} — {escape(str(decision.get('robust_headline', '')))}.</li>
<li>Technology-class spectral proxy changes leader: {escape(str(decision.get('spectral_sensitivity_changes_leader')))} — sensitivity only unless module-specific spectral evidence exists.</li>
<li>Manufacturer-warranty sensitivity changes leader: {escape(str(decision.get('warranty_sensitivity_changes_leader')))} — warranty is not field degradation.</li>
</ul>

<h2>Project</h2>
<p><strong>Location:</strong> {site.get('latitude')}, {site.get('longitude')}<br>
<strong>Reference year:</strong> {escape(str(project.get('reference_year')))}<br>
<strong>Project DC size:</strong> {_fmt(project.get('system_size_mw'),1)} MWp<br>
<strong>Project segment:</strong> {project_segment}<br>
<strong>Geometry:</strong> fixed-tilt, monofacial; tilt {project.get('tilt_deg')}°, azimuth {project.get('azimuth_deg')}°<br>
<strong>Common soiling:</strong> {project.get('soiling_loss_pct')}%<br>
<strong>Primary common-degradation sensitivity:</strong> {project.get('common_degradation_pct_year')}%/year<br>
<strong>Energy-rating uncertainty guardrail:</strong> {project.get('uncertainty_guardrail_pct')}%</p>

<h2>Module comparison</h2>
<table><thead><tr><th>Module</th><th>Technology</th><th>Broadband kWh/kWp</th><th>Spectral sensitivity kWh/kWp</th>
<th>Project DC MWh/y</th><th>25-y common-degradation scenario</th><th>25-y warranty sensitivity</th><th>Spectral effect</th><th>P95 cell T</th><th>Electrical model</th><th>Evidence</th><th>Decision eligible</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>

<h2>Environmental stress exposure</h2>
<p>Exposure descriptors below are not converted into annual degradation rates or failure probabilities without calibrated module/BOM evidence.</p>
<table><thead><tr><th>Module</th><th>Hours Tcell &gt;65°C</th><th>Hours RH≥85% & Tcell≥40°C</th>
<th>Mean daily T range</th><th>Days range &gt;30°C</th></tr></thead><tbody>{''.join(stress_rows)}</tbody></table>

<h2>Switching-point economics</h2>
<p>The primary switching threshold uses one common project degradation sensitivity. Manufacturer warranty is shown separately. This is a module + area-BOS threshold analysis, not full LCOE.</p>
{econ_html}

<h2>Independent resource check</h2>
<p>{escape(pvgis_note or 'PVGIS cross-check not run.')}</p>

<div class="warn"><strong>Scientific boundary.</strong> V9.2.1 is a validation PoC. It ranks every candidate that produces a finite transparent physics simulation, including exploratory model classes, so the climate-aware decision workflow can be tested end-to-end. Evidence grade and the uncertainty threshold are retained as confidence/validation diagnostics rather than hard blockers. Module-specific IEC 61853 evidence remains the preferred route for stronger claims. Generic technology-class spectral corrections and manufacturer warranty slopes remain sensitivities, not hidden winner-making scores. Full IEC 61853-3 conformity, lender-grade uncertainty, BOM-specific degradation calibration, inverter/AC design, bifacial rear-side gain, shading, mismatch, availability and O&M remain outside this PoC.</div>

<h2>Evidence</h2>
<ul>{''.join(evidence_items)}</ul>
</body></html>"""
