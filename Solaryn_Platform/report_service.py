"""Pure immutable-result renderers. No physics, degradation or finance imports.

SVG layout patterns refactored from Pilot epc_report._svg_line/_svg_hbar:
current contract, navy/yellow palette, zero axes, exact data attributes and no
legacy aggregation or probability graphics.
"""
import base64
import csv
import hashlib
from html import escape
import io
import json
import math
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = 'epc-report-1.0'
COLORS = ['#c48d00','#123b54','#367c9c','#737b83']
STYLE = '''
.epc{color:#062338;font:14px/1.65 "Segoe UI",Arial,sans-serif;max-width:1160px;margin:auto}.epc *{box-sizing:border-box}.epc h1{font-size:32px;line-height:1.2}.epc h2{font-size:21px;margin:0 0 14px}.epc h3{font-size:16px}.epc p{margin:8px 0 16px}.epc .muted{color:#617380;font-size:12px}.epc .chapter{background:white;border:1px solid #dde5e9;border-radius:10px;padding:26px;margin:22px 0;break-inside:avoid}.epc .lead{border-top:5px solid #f7b800}.epc .kicker{font-size:11px;letter-spacing:2px;color:#637581;font-weight:700}.epc .logo{width:240px;height:auto}.epc .note{padding:14px;background:#fff8e5;border-left:3px solid #edb300;font-size:12px;margin:14px 0}.epc .charts{display:grid;grid-template-columns:1fr;gap:20px}.epc .charts>.chapter{margin:0;min-width:0}.epc .plot-scroll{overflow-x:auto;max-width:100%}.epc .plot-scroll svg{min-width:620px}.epc svg{display:block;width:100%;height:auto;overflow:visible}.epc .axis{font-size:12px;fill:#627582}.epc .grid{stroke:#e0e7ea}.epc .legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;margin:12px 0}.epc .legend i{display:inline-block;width:10px;height:10px;margin-right:6px;border-radius:50%}.epc table{width:100%;border-collapse:collapse;font-size:12px}.epc td,.epc th{padding:10px;text-align:left;border-bottom:1px solid #e1e7ea;vertical-align:top}.epc th{background:#f5f7f9;color:#617380}.epc .table-scroll{overflow:auto}.epc pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px;background:#f4f7f8;padding:15px}.epc a{color:#195879}.epc .flow{display:flex;flex-wrap:wrap;gap:10px;align-items:stretch}.epc .flow-card{flex:1 1 130px;border:1px solid #dbe4e9;border-top:3px solid #eeb500;padding:13px;border-radius:6px;position:relative}.epc .flow-card:not(:last-child):after{content:'→';position:absolute;right:-10px;top:35%;background:white}.epc .flow-card b,.epc .flow-card small{display:block;font-size:11px}.epc .status{font-size:10px;color:#697b85}.epc summary{cursor:pointer;padding:12px 0;font-weight:600}.epc .headline-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.epc .headline-grid>div{background:#f5f8fa;padding:16px;border-radius:6px}.epc .headline-grid strong{display:block;font-size:21px}.epc .unit{font-size:11px;color:#677987}
@media(max-width:800px){.epc .charts{grid-template-columns:1fr}.epc .chapter{padding:18px}.epc .headline-grid{grid-template-columns:1fr}.epc h1{font-size:26px}}
@media print{body{background:white!important;padding:0!important}.epc{max-width:none;font-size:10pt}.epc .chapter{border:0;border-bottom:1px solid #ccc;border-radius:0;margin:12px 0;padding:14px 0}.epc .charts{display:block}.epc details{display:block}.epc svg{max-height:90mm}.epc .plot-scroll{overflow:visible}.epc .plot-scroll svg{min-width:0}.epc .table-scroll{overflow:visible}.epc a{color:inherit;text-decoration:none}}
'''


def e(value):
    return escape(str(value if value is not None else 'Not supplied'),quote=True)


def number(value, digits=1):
    return f'{value:,.{digits}f}' if isinstance(value,(int,float)) and math.isfinite(value) else '—'


def label(row):
    return f"{row.get('manufacturer','')} {row.get('model',row.get('module_id',''))}".strip()


def table(headers, rows):
    return '<div class="table-scroll"><table><thead><tr>'+''.join(f'<th>{e(h)}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{e(v)}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def bars(items, title, unit, chart_id):
    clean=[(str(k),v) for k,v in items if v is not None and math.isfinite(v)]
    if not clean:return '<p class="muted">No stored values for this chart.</p>'
    lo=min(0,min(v for _,v in clean)); hi=max(0,max(v for _,v in clean)); span=hi-lo or 1
    left,width=285,380
    sx=lambda v:left+(v-lo)/span*width
    height=65+len(clean)*40
    parts=[f'<svg data-chart="{e(chart_id)}" role="img" aria-label="{e(title)}" viewBox="0 0 800 {height}"><title>{e(title)} · {e(unit)}</title>']
    for i in range(5):
        v=lo+span*i/4;x=sx(v)
        parts.append(f'<line x1="{x}" x2="{x}" y1="16" y2="{height-30}" class="grid"/><text x="{x}" y="{height-8}" text-anchor="middle" class="axis">{number(v,3 if unit=="€/W" else 0)}</text>')
    for i,(name,v) in enumerate(clean):
        y=25+i*40
        parts.append(f'<text x="0" y="{y+14}" class="axis">{e(name[:42])}</text><rect data-value="{v}" x="{min(sx(0),sx(v))}" y="{y}" width="{abs(sx(v)-sx(0))}" height="22" rx="3" fill="{COLORS[i%len(COLORS)]}"><title>{e(name)}: {v} {e(unit)}</title></rect><text x="680" y="{y+15}" class="axis">{number(v,4 if unit=="€/W" else 1)}</text>')
    parts.append('</svg>')
    return '<div class="plot-scroll" tabindex="0" aria-label="Scrollable chart">'+''.join(parts)+'</div>'+f'<p class="muted">{e(unit)} · Zero included on the axis. Hover over a bar for the stored value.</p>'


def lines(series,title,unit,chart_id):
    points=[p for _,vals in series for p in vals if p[1] is not None]
    if not points:return '<p class="muted">This scenario has no stored curve.</p>'
    xmin=min(x for x,y in points); xmax=max(x for x,y in points)
    ymax=max(y for x,y in points) or 1
    sx=lambda x:60+(x-xmin)/max(1,xmax-xmin)*690
    sy=lambda y:245-y/ymax*205
    parts=[f'<svg data-chart="{e(chart_id)}" role="img" aria-label="{e(title)}" viewBox="0 0 800 285"><title>{e(title)} · {e(unit)}</title>']
    for j in range(5):
        v=ymax*j/4; yy=sy(v)
        parts.append(f'<line x1="60" x2="750" y1="{yy}" y2="{yy}" class="grid"/><text x="52" y="{yy+4}" text-anchor="end" class="axis">{number(v,0)}</text>')
    for idx,(name,vals) in enumerate(series):
        vals=[(x,y) for x,y in vals if y is not None]
        color=COLORS[idx%len(COLORS)]
        pts=' '.join(f'{sx(x)},{sy(y)}' for x,y in vals)
        parts.append(f'<polyline data-series="{e(name)}" points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for x,y in vals:
            parts.append(f'<circle data-series="{e(name)}" data-x="{x}" data-y="{y}" cx="{sx(x)}" cy="{sy(y)}" r="3" fill="{color}"><title>{e(name)} · {x}: {y} {e(unit)}</title></circle>')
    ticks=sorted(set(x for x,y in points))
    for i,x in enumerate(ticks):
        if len(ticks)<=12 or i%5==0 or i==len(ticks)-1:
            tick=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(x)-1] if chart_id=='monthly' else str(x)
            parts.append(f'<text x="{sx(x)}" y="273" text-anchor="middle" class="axis">{e(tick)}</text>')
    parts.append('</svg></div><div class="legend">')
    parts.extend(f'<span><i style="background:{COLORS[i%len(COLORS)]}"></i>{e(name)}</span>' for i,(name,_) in enumerate(series))
    return '<div class="plot-scroll" tabindex="0" aria-label="Scrollable chart">'+''.join(parts)+'</div>'+f'<p class="muted">{e(unit)} · Points show stored backend values.</p>'


def chapter(title,body):return f'<section class="chapter"><h2>{e(title)}</h2>{body}</section>'


def flow(a):
    c=a.get('configuration') or {}; path=a.get('model_path') or 'Not run'
    stages=[('Site','Saved','Exact WGS84 coordinate'),('Climate','Available' if a.get('climate_snapshot') else 'Unavailable',(a.get('climate_snapshot') or {}).get('provider','No source')),
            ('Operating conditions','Modeled','Shared Faiman / fixed geometry'),('Candidate physics','Evidence limited',path),('Year-1 energy','Calculated' if a.get('decision',{}).get('ranking') else 'Unavailable','Stored hourly integration'),
            ('Lifetime','Scenario' if c.get('lifetime') else 'Not requested','Common supplied degradation' if c.get('lifetime') else 'No rate assumed'),
            ('Economics','Scenario' if c.get('economics') else 'Not requested','Supplied EUR inputs' if c.get('economics') else 'No quotes assumed'),('Recommendation',(a.get('decision') or {}).get('strength') or 'Unavailable','Separate scientific status')]
    return '<div class="flow" data-chart="decision-flow" role="img" aria-label="Site to recommendation decision flow">'+''.join(f'<div class="flow-card"><b>{e(n)}</b><span class="status">{e(s)}</span><small>{e(source)}</small></div>' for n,s,source in stages)+'</div>'


def dashboard(a):
    rows=a.get('decision',{}).get('ranking',[]); top=rows[:3]; c=a.get('configuration') or {}; snapshot=a.get('climate_snapshot') or {}
    if not rows:return chapter('Calculation required','<p>Run an analysis to generate report charts.</p>')
    content=[chapter('How the decision was made',flow(a))]
    content.append('<div class="charts">'+chapter('Annual specific energy',bars([(label(r),r['annual_dc_kwh_kwp']) for r in rows],'Annual DC specific energy','kWh/kWp/year','annual'))+
                   chapter('Seasonal production',lines([(label(r),[(m['month'],m['dc_kwh_kwp']) for m in r['monthly']]) for r in top],'Top 3 monthly DC energy','kWh/kWp/month','monthly'))+'</div>')
    if c.get('lifetime'):
        years=c['lifetime']['years']; title=f'{years}-year common degradation sensitivity'
        body=lines([(label(r),[(v['year'],v['dc_kwh_kwp']) for v in r['annual_lifetime']]) for r in top],title,'kWh/kWp/year','lifetime')
        body+='<p class="note">The same degradation scenario is applied to every candidate. This chart shows lifetime impact but does not claim candidate-specific degradation differentiation.</p>'
        body+=f'<p>Supplied scenario: {e(c["lifetime"]["degradation_pct"])}% per year for {years} years. Warranty slopes are not used as measured degradation.</p>'
        content.append(chapter(title,body))
        if all(r.get('cumulative_lifetime') for r in top):
            content.append(chapter('Cumulative lifetime energy',lines([(label(r),[(v['year'],v['dc_kwh_kwp']) for v in r['cumulative_lifetime']]) for r in top],'Cumulative lifetime DC energy','kWh/kWp','cumulative')))
    else:content.append(chapter('Lifetime scenario','<p>No lifetime scenario was supplied. Enable a 25-year scenario in Analysis and enter a common degradation rate to generate the 25-year curve.</p>'))
    drivers=(a.get('visual_data') or {}).get('driver_differences')
    if drivers:
        content.append(chapter('Why #1 differs from #2',bars([(d['label'],d['value']) for d in drivers],'Stored top-two contribution differences','kWh/kWp/year','drivers')+f'<p>{e(a.get("explanation"))}</p>'))
    else:
        effects=[(label(r),r.get('contributions',{}).get('temperature_effect_kwh_kwp')) for r in top[:2]]
        content.append(chapter('Modeled temperature contribution',bars(effects,'Top-two stored temperature effects','kWh/kWp/year','drivers')+f'<p>{e(a.get("explanation"))}</p><p class="muted">Effects relative to each candidate’s 25°C reference; common soiling is non-differentiating. Unsupported model layers are omitted.</p>'))
    if c.get('economics'):
        econ=c['economics']; reference=next((label(r) for r in rows if r['module_id']==econ['reference_id']),econ['reference_id'])
        body=f'<p>Reference: <strong>{e(reference)}</strong>. Energy value {e(econ["energy_value_eur_kwh"])} €/kWh net AC; discount {e(econ["discount_rate_pct"])}% at year end.</p>'
        body+=bars([(label(r),r.get('headroom_eur_w')) for r in rows],'Procurement headroom','€/W','economics')
        body+=table(['Candidate','Actual premium €/W','Maximum justified premium €/W','Headroom €/W'],[(label(r),number(r.get('actual_premium_eur_w'),4),number(r.get('max_premium_eur_w'),4),number(r.get('headroom_eur_w'),4)) for r in rows])
        body+='<p class="note">A quoted premium within the justified premium has nonnegative modeled headroom. A premium above that threshold is unsupported relative to the explicit reference under these inputs. This is a switching threshold, not full LCOE.</p>'
        content.append(chapter('Procurement economics',body))
    cross=snapshot.get('crosscheck') or {}
    resource=bars([('PVGIS',cross.get('pvgis_annual_ghi_kwh_m2')),('NASA POWER',cross.get('nasa_annual_ghi_kwh_m2'))],'Independent horizontal resource estimates','kWh/m²/year','resource')
    resource+=f'<p>Primary: {e(snapshot.get("provider"))} · NASA relative to PVGIS: {number(cross.get("difference_pct"))}% · {e(cross.get("status"))}.</p><p class="muted">No acceptance threshold has been scientifically configured. Difference is descriptive, not a calibrated uncertainty or validation pass. Providers are not averaged.</p>'
    content.append(chapter('Resource cross-check',resource))
    diag=(a.get('visual_data') or {}).get('diagnostics')
    if diag:content.append(chapter('Operating-condition diagnostics',table(['Metric','Stored value','Unit'],[(k,v['value'],v['unit']) for k,v in diag.items()])+'<p class="muted">Descriptive exposure only; these values do not become degradation rates.</p>'))
    return ''.join(content)


def html_report(a):
    rows=a.get('decision',{}).get('ranking',[])
    if not rows:raise ValueError('A completed ranked analysis is required for the EPC report')
    d=a['decision']; leader=rows[0]; c=a.get('configuration') or {}; site=a['site']
    logo=base64.b64encode((ROOT.parent/'frontend/public/brand/solaryn-logo.png').read_bytes()).decode()
    body=f'<img class="logo" alt="SOLARYN" src="data:image/png;base64,{logo}"><p class="kicker">EPC DECISION REPORT · {e(a["created_at"])}</p>'
    body+=f'<section class="chapter lead"><p class="kicker">RECOMMENDED · {e(d.get("objective"))}</p><h1>{e(label(leader))}</h1><p>Recommendation strength: <strong>{e(d.get("strength"))}</strong><br>Scientific status: <strong>Model-based / provisional</strong></p><p class="note">{e(d.get("strength_reason"))}</p>'
    body+='<div class="headline-grid">'+''.join(f'<div><span>#{i+1} · {e(label(r))}</span><strong>{number(r["annual_dc_kwh_kwp"])}</strong><span class="unit">kWh/kWp/year DC</span></div>' for i,r in enumerate(rows[:3]))+'</div>'
    if len(rows)>1:body+=f'<p>Next ranked alternative: {e(label(rows[1]))}. DC difference from leader: {number(rows[1].get("dc_difference_from_leader_pct"))}%.</p>'
    body+=f'<p>{e((a.get("visual_data") or {}).get("decision_changer") or "Geometry, thermal response, measured electrical evidence and supplied commercial assumptions may change the result; no validated switching sensitivity was supplied.")}</p></section>'
    body+=chapter('Project and comparison boundary',table(['Latitude','Longitude','Resource year','Primary provider','Tilt','Azimuth','Project life'],[[site['latitude'],site['longitude'],(a.get('climate_snapshot') or {}).get('year'),(a.get('climate_snapshot') or {}).get('provider'),c.get('tilt_deg'),c.get('azimuth_deg'),(c.get('lifetime') or {}).get('years')]])+f'<p>Application: {e(c.get("application","Not declared in this saved run"))}. Market: {e(c.get("market_region","Not declared"))}. Normalization: equal installed DC kWp.</p>')
    metrics=(a.get('climate_snapshot') or {}).get('metrics',{});units=(a.get('climate_snapshot') or {}).get('units',{})
    body+=chapter('Site / climate summary',table(['Metric','Value','Unit'],[(k,number(v),units.get(k)) for k,v in metrics.items()]))
    body+=chapter('Candidate shortlist',table(['Rank','Exact candidate','DC kWh/kWp/year','Lifetime DC kWh/kWp','Model / evidence'],[(r['rank'],label(r),number(r['annual_dc_kwh_kwp']),number(r.get('lifetime_dc_kwh_kwp')),r['model_path']) for r in rows]))
    body+=dashboard(a)
    body+=chapter('Sensitivity / what changes the decision',f'<p>{e((a.get("visual_data") or {}).get("decision_changer") or "No calibrated sensitivity threshold is available for this historical run.")}</p>')
    evidence_rows=[]
    for m in a.get('selected_modules',[]):
        evidence_rows.append((label(m),m.get('commercial_status'),m.get('application'),m.get('market_regions'),m.get('source_checked_at'),m.get('source_url')))
    body+=chapter('Evidence and validation',table(['Candidate','Market status','Application','Regions','Checked','Official source'],evidence_rows)+''.join(f'<p class="note">{e(w)}</p>' for w in a.get('warnings',[]))+''.join(f'<p>{e(s)}</p>' for s in a.get('assumptions',[])))
    provenance={'analysis_id':a['id'],'model_version':a.get('model_version'),'catalog_release':a.get('catalog_release'),'validation_status':a.get('validation_status'),'strength_policy':d.get('strength_policy'),'manifest':a.get('manifest'),'report_renderer':VERSION}
    body+=chapter('Reproducibility',f'<pre>{e(json.dumps(provenance,indent=2))}</pre><p>Figures render the immutable analysis. The report does not rerun physics, degradation or economics. Original JSON remains the authoritative full-precision result.</p>')
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'"><title>SOLARYN EPC · {e(a["id"])}</title><style>body{{background:#f5f8fa;padding:30px;margin:0}}{STYLE}</style></head><body><main class="epc">{body}</main></body></html>'


def csv_bytes(headers, rows):
    out=io.StringIO(newline=''); writer=csv.writer(out);writer.writerow(headers)
    for row in rows:
        writer.writerow([("'"+v if v[:1] in ('=','+','-','@','\t','\r') else v) if isinstance(v,str) else v for v in row])
    return out.getvalue().encode('utf-8-sig')


def evidence_package(a):
    rows=a['decision']['ranking'];c=a.get('configuration') or {}
    encode=lambda value:json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False).encode('utf-8')
    files={'EPC_Report.html':html_report(a).encode('utf-8'),'result.json':encode(a),
           'candidate_comparison.csv':csv_bytes(['module_id','manufacturer','model','rank','annual_dc_kwh_kwp','annual_ac_kwh_kwp','lifetime_dc_kwh_kwp','model_path'],[[r.get(k) for k in ['module_id','manufacturer','model','rank','annual_dc_kwh_kwp','annual_ac_kwh_kwp','lifetime_dc_kwh_kwp','model_path']] for r in rows]),
           'monthly_energy.csv':csv_bytes(['module_id','month','dc_kwh_kwp','ac_kwh_kwp'],[[r['module_id'],m['month'],m['dc_kwh_kwp'],m.get('ac_kwh_kwp')] for r in rows for m in r['monthly']]),
           'provenance.json':encode({'analysis_id':a['id'],'catalog_release':a['catalog_release'],'configuration':c,'manifest':a.get('manifest'),'providers':(a.get('climate_snapshot') or {}).get('providers'),'selected_modules':a.get('selected_modules'),'renderer_version':VERSION})}
    if c.get('lifetime'):
        years=c['lifetime']['years']
        files[f'lifetime_{years}y.csv']=csv_bytes(['module_id','year','retention','dc_kwh_kwp','ac_kwh_kwp'],[[r['module_id'],v['year'],v['retention'],v['dc_kwh_kwp'],v.get('ac_kwh_kwp')] for r in rows for v in r['annual_lifetime']])
    if c.get('economics'):
        fields=['module_id','quote_eur_w','actual_premium_eur_w','max_premium_eur_w','headroom_eur_w']
        files['economics.csv']=csv_bytes(fields,[[r.get(k) for k in fields] for r in rows])
    files['manifest.json']=encode({'algorithm':'SHA-256','analysis_id':a['id'],'renderer_version':VERSION,'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},'note':'Manifest excludes its own hash. Lifetime/economics CSVs exist only for supplied scenarios.'})
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():
            info=zipfile.ZipInfo(f'SOLARYN_{a["id"]}/{name}',date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
    return out.getvalue()
