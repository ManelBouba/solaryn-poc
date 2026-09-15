"""Render immutable JSON only. No physics, finance or decision calculation occurs here."""
from html import escape
import io
import re
import zipfile
import pandas as pd

def summary_table(result):
    return pd.DataFrame([{
        "Module": f"{c['manufacturer']} {c['model']}", "Technology": c["technology"],
        "Simulation": c["simulation_status"],
        "Annual DC kWh/kWp": c["metrics"].get("annual_yield_kwh_kwp"),
        "Project MWh/year": c["metrics"].get("annual_project_dc_energy_mwh"),
        "Lifetime scenario kWh/kWp": c["metrics"].get("lifetime_energy_common_degradation_scenario_kwh_kwp"),
        "Evidence eligible": c["metrics"].get("decision_eligible", False),
    } for c in result["candidates"]])

def explain(result):
    """Grounded local explanation; no external model or confidential data transfer."""
    return {"run_id": result["run_id"], "text": result["decision"]["headline"],
            "reasons": result["decision"].get("reasons", []), "limitations": result["limitations"]}

def render_report(r):
    d, p = r["decision"], r["project"]
    table = summary_table(r).to_html(index=False, escape=True, na_rep="Unavailable", float_format=lambda n: f"{n:,.2f}")
    reasons = "".join(f"<li>{escape(str(x))}</li>" for x in d.get("reasons", []))
    limits = "".join(f"<li>{escape(x)}</li>" for x in r["limitations"])
    assumptions = pd.DataFrame([{"Input": k, "Value": str(v)} for k, v in p.items()]).to_html(index=False, escape=True)
    gates = pd.DataFrame([{"Gate": k.replace('_', ' '), "Status": v} for k, v in r["validation_gates"].items()]).to_html(index=False)
    evidence = []
    for c in r["candidates"]:
        url = str(c["inputs"].get("source_url") or "")
        link = f'<a href="{escape(url, quote=True)}">Manufacturer source</a>' if url.startswith(("https://", "http://")) else "No usable source link"
        evidence.append(f"<li><b>{escape(c['manufacturer']+' '+c['model'])}</b> · {escape(str(c['metrics'].get('model_evidence_level','Unavailable')))} · {link}<br>{escape('; '.join(c['warnings']))}</li>")
    monthly = pd.DataFrame(r["monthly"]).to_html(index=False, escape=True, float_format=lambda n: f"{n:,.2f}")
    benchmark = pd.DataFrame(r["resource"]["benchmark"]).to_html(index=False, escape=True, float_format=lambda n: f"{n:,.2f}")
    econ = r["economics"]
    economic_table = (pd.DataFrame(econ["switching_threshold"]).to_html(index=False, escape=True, na_rep="Unavailable", float_format=lambda n: f"{n:,.4f}")
                      if econ["switching_threshold"] else "<p>Procurement economics unavailable. " + escape(econ.get("reason", "A real baseline supplier quote is required.")) + "</p>")
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Solaryn | {escape(p['project_name'])}</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;color:#102a36;margin:0;background:#f4f8f9}}main{{max-width:1120px;margin:32px auto;background:white;padding:40px;border-radius:16px}}h1{{font-size:38px;margin:0}}h2{{margin-top:32px;color:#076775}}.status{{background:#e8f3f4;padding:24px;border-left:5px solid #087f8c;border-radius:8px}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid #d3e4e6;text-align:left;vertical-align:top}}th{{background:#e8f3f4}}code{{overflow-wrap:anywhere}}a{{color:#087f8c}}@media(max-width:700px){{main{{margin:0;padding:20px}}}}@media print{{body{{background:white}}main{{margin:0;padding:0}}.scroll{{overflow:visible}}table{{font-size:9px}}}}</style>
<main><p>SOLARYN / PROJECT DECISION</p><h1>{escape(p['project_name'])}</h1><p>{escape(str(p['latitude']))}, {escape(str(p['longitude']))} · DC module comparison</p>
<section class="status"><h2>{escape(d['label'])}</h2><p>{escape(d['headline'])}</p><ul>{reasons}</ul><p>The separation guardrail is a decision policy, not statistical confidence.</p></section>
<h2>Candidate comparison</h2><div class="scroll">{table}</div>
<h2>Resource agreement</h2><p>{escape(r['resource']['reason'])}</p><div class="scroll">{benchmark}</div><p>Monthly contributions in kWh/m²; the two providers remain separate.</p>
<h2>Monthly DC energy</h2><div class="scroll">{monthly}</div>
<h2>Economics · {escape(econ['currency'])}/W</h2><p>Module + area-BOS switching sensitivity; constant declared currency and year-end discounting. No foreign-exchange conversion or full LCOE.</p><div class="scroll">{economic_table}</div>
<h2>Evidence</h2><ul>{''.join(evidence)}</ul>
<h2>Project assumptions</h2><div class="scroll">{assumptions}</div>
<h2>Validation gates</h2>{gates}<h2>Limitations</h2><ul>{limits}</ul>
<h2>Reproducibility</h2><p>Run <code>{r['run_id']}</code></p><p>Model release {escape(r['versions']['model_release'])} · decision policy {escape(r['versions']['decision_policy'])}</p><p>Code checksum <code>{r['versions']['code_sha256']}</code></p><p>Result.json contains exact values, source metadata, inputs and release identifiers. Manifest.json verifies the included artifact bytes. Local hashes are not digital signatures.</p></main></html>'''

def package_run(store, run_id):
    r = store.read(run_id)
    leader = next((c for c in r["candidates"] if c["module_id"] == r["decision"].get("provisional_leader_module_id")), None)
    slug = lambda s: re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip('_')[:80] or "Project"
    label = leader["technology"] if leader else "No_Unique_Leader"
    name = f"Solaryn_{slug(r['project']['project_name'])}_{slug(label)}_Analysis"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted((store.root / run_id).rglob("*")):
            if file.is_file():
                info = zipfile.ZipInfo(name + "/" + file.relative_to(store.root / run_id).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, file.read_bytes())
    return name + ".zip", out.getvalue()
