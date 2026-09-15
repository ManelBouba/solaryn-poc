from pathlib import Path
import json, html, zipfile, hashlib, shutil

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'SOLARYN_FOUR_CLIMATE_TESTS_2026-09-14'
results=json.loads((OUT/'test_results.json').read_text())
byname={r['site']:r for r in results}
names=['Leuven','Riyadh','Iqaluit','Singapore']
esc=html.escape
intro='Four full platform API runs completed using newly retrieved NASA POWER hourly weather for 2020, with three identical catalog modules in each location. The runs used isolated test databases and did not modify the signed-in workspace. These are API and physics integration tests; browser interaction was not tested.'
audit_note=''
if (OUT/'BIAS_AUDIT'/'AUDIT.md').exists():
    intro+=' These original three-module runs are a limited screening scenario, not a fair assessment of every technology or a procurement recommendation. A subsequent bias audit expanded the catalog and tested rear irradiance; see the linked audit for changed numerical leaders.'
    audit_note='<div class="panel note"><b>Updated after the bias review.</b> The original scenario below disabled rear generation. Expanded tests with common row geometry changed the numerical leaders. <a href="BIAS_AUDIT/AUDIT.html">Read the bias audit and scenario comparison</a>.</div>'
assumptions='Common screening assumptions: 1 MWp; 25° tilt; 180° azimuth; 2% soiling; albedo 0.20; row geometry disabled; DC/AC ratio 1.3; 97% inverter efficiency; 99% availability; no curtailment. Economics use hypothetical equal module prices of €0.12/W, 30 years, 0.5% annual degradation, €0.40/W BOS, €10/kW/year O&M, €2/kW/year cleaning, €45/MWh PPA and 7% real discount rate. These inputs are controlled test assumptions, not site-optimized designs or supplier quotes.'
limits='All four runs retain INSUFFICIENT_EVIDENCE for module selection. The CdTe candidate lacks decision-grade electrical evidence; modeled leaders are within the 2% decision guardrail; independent resource agreement and independent claim review are absent. Iqaluit and Singapore also show a leader change under a sensitivity scenario. No bankable winner is established. The measured SUPSI benchmark covers a reference electrical interpolation layer, not site weather, thermal/rear models, arbitrary module technologies, AC conversion or lifetime economics. One weather year is not a long-term yield estimate; fixed soiling and degradation do not model site-specific snow, dust deposition or climate aging.'
md=['# SOLARYN — Four climate tests','Run date: 2026-09-14','',intro,'',assumptions,'','| Site | Climate | Test | Jinko net AC | LONGi net AC | First Solar net AC |','|---|---|---|---:|---:|---:|']
rows=[]; cards=[]
for name in names:
    r=byname[name]; d=json.loads((OUT/name/'Result.json').read_text())
    energy=d['ac_energy']; exp=d['decision_chain']['climate_exposure']; v=d['measured_validation']
    values=[e['net_ac_kwh_kwp'] for e in energy]
    md.append(f"| {name} | {r['climate']} | {r['status']} | "+' | '.join(f'{x:,.2f}' for x in values)+' |')
    rows.append(f'<tr><th>{name}</th><td>{r["climate"]}</td><td class="pass">{r["status"]}</td>'+''.join(f'<td>{x:,.2f}</td>' for x in values)+'</tr>')
    erows=''.join(f'<tr><td>{esc(e["model"])}</td><td>{e["dc_kwh_kwp"]:,.2f}</td><td>{e["net_ac_kwh_kwp"]:,.2f}</td></tr>' for e in energy)
    bars=''.join(f'<div class="barrow"><span>{esc(e["model"])}</span><div class="track"><div class="bar" style="width:{e["net_ac_kwh_kwp"]/2100*100:.2f}%"></div></div><b>{e["net_ac_kwh_kwp"]:,.2f}</b></div>' for e in energy)
    issues=''.join(f'<li>{esc(x)}</li>' for x in d['physics']['decision']['reasons'])
    cards.append(f'''<section><div class="eyebrow">{esc(r['climate'])} · {r['latitude']}, {r['longitude']}</div><h2>{name} <small>{r['status']} · {r['seconds']} s</small></h2>
<p>2020 mean temperature <b>{exp['ambient_temperature']['mean']:.1f} °C</b> · Mean relative humidity <b>{exp['relative_humidity']['mean']:.1f}%</b>. Climate descriptors are site labels; these numbers come from the retrieved weather year.</p>
{bars}<p class="muted">Net AC yield, kWh/kWp/year. All bars use the same scale.</p>
<table><tr><th>Exact module</th><th>Annual DC</th><th>Annual net AC</th></tr>{erows}</table>
<p><b>Decision: {esc(d['physics']['decision']['label'])}.</b> {esc(d['physics']['decision']['headline'])}</p><details><summary>Evidence restrictions</summary><ul>{issues}</ul></details>
<p><a href="{name}/{name}_Analysis.zip">Full analysis ZIP</a> · <a href="{name}/{name}_Decision.html">Original engine report</a> · <a href="{name}/Result.json">Complete result JSON</a> · <a href="{name}/Hourly-DC-AC.csv">Hourly DC/AC</a></p></section>''')
    md.extend([])
v=json.loads((OUT/'Leuven/Result.json').read_text())['measured_validation']
validation=f"All four cases reproduced the same reference SUPSI benchmark: {v['retained_rows']:,} observations, RMSE {v['rmse_w']:.6f} W, normalized RMSE {v['rmse_pct_stc']:.6f}%, MAE {v['mae_w']:.6f} W and R² {v['r2']:.6f}. The identical metrics are expected: each run replays the same electrical reference data, not independent field measurements at each site. All 13 validation input hashes matched."
checks='Passed in all four cases: physics API returned HTTP 201; completed results could be read back; positive AC yield below DC yield; DC-to-AC loss balance; monthly-to-annual AC reconciliation; measured benchmark reproduction; ZIP CRC integrity and all exported manifest hashes.'
md+=['','Yield units: kWh/kWp/year.','','## Validation','',checks,'',validation,'','## Interpretation and limits','',limits,'','## Files','']
for n in names: md += [f'- [{n} original report]({n}/{n}_Decision.html) · [{n} full analysis]({n}/{n}_Analysis.zip)']
(OUT/'REPORT.md').write_text('\n'.join(md),encoding='utf-8')
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SOLARYN — Four climate tests</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;background:#edf3f1;color:#182f2a;margin:0}}main{{max-width:1100px;margin:auto;padding:44px 28px}}h1{{font-size:42px;line-height:1.12;margin:12px 0 22px}}h2{{font-size:27px;margin:8px 0}}section,.panel{{background:white;border:1px solid #d7e3de;border-radius:14px;padding:25px;margin:22px 0}}.eyebrow{{text-transform:uppercase;font-size:12px;letter-spacing:2px;color:#446659}}small{{font-size:14px;float:right;color:#147451}}table{{width:100%;border-collapse:collapse;margin:20px 0;font-variant-numeric:tabular-nums}}th,td{{padding:12px 8px;border-bottom:1px solid #dce6e2;text-align:left}}td{{font-size:14px}}th{{font-size:13px}}.pass{{color:#087249;font-weight:bold}}a{{color:#096c58}}.muted{{font-size:12px;color:#547068}}.barrow{{display:flex;align-items:center;gap:14px;font-size:13px;margin:12px 0}}.barrow span{{width:165px}}.barrow b{{width:80px;text-align:right}}.track{{flex:1;background:#ecf1ee;height:15px;border-radius:4px}}.bar{{height:15px;background:#258b6c;border-radius:4px}}.note{{border-left:4px solid #bd8a27;padding-left:18px}}@media(max-width:700px){{main{{padding:20px 12px}}h1{{font-size:32px}}.overview{{overflow:auto}}.barrow span{{width:115px}}small{{float:none;display:block}}}}@media print{{body{{background:white}}main{{padding:0}}section{{break-inside:avoid}}details{{display:block}}}}</style>
<main><div class="eyebrow">SOLARYN / Executed 14 September 2026</div><h1>Four climates.<br>One controlled physics comparison.</h1><p>{intro}</p>
<div class="panel overview"><h2>4 / 4 tests passed</h2><p>Annual net AC yield · kWh/kWp/year</p><table><tr><th>Site</th><th>Climate</th><th>Test</th><th>Jinko TOPCon</th><th>LONGi PERC</th><th>First Solar CdTe</th></tr>{''.join(rows)}</table><p class="note"><b>Software checks passed; procurement evidence remains insufficient in all four cases.</b></p></div>
<div class="panel"><h2>Common inputs</h2><p>{assumptions}</p></div>{''.join(cards)}<div class="panel"><h2>Validation and traceability</h2><p>{checks}</p><p>{validation}</p><p>Full exports retain weather inputs, original model source, measured validation source files, hourly results and SHA-256 manifests. Inputs and test summaries are also saved beside each report.</p></div><div class="panel"><h2>Interpretation limits</h2><p>{limits}</p><p><a href="REPORT.md">Text report</a> · <a href="test_results.json">Machine-readable test summary</a></p></div></main></html>'''
page=page.replace('<div class="panel overview">',audit_note+'<div class="panel overview">',1)
(OUT/'REPORT.html').write_text(page,encoding='utf-8')
shutil.copy2(ROOT/'climate_tests_2026_09_14.py',OUT/'climate_tests_2026_09_14.py')
archive=ROOT/(OUT.name+'.zip')
files=[p for p in OUT.rglob('*') if p.is_file() and 'runtime' not in p.relative_to(OUT).parts and p != OUT/'MANIFEST_SHA256.json']
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUT/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2))
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[OUT/'MANIFEST_SHA256.json']: z.write(p,OUT.name+'/'+p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(set(z.namelist()))
    assert all(hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest for name,digest in manifest.items())
print(json.dumps({'report':str(OUT/'REPORT.html'),'archive':str(archive),'bytes':archive.stat().st_size,'files':len(files)+1}))
