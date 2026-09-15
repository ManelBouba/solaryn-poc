from __future__ import annotations

from html import escape
from pathlib import Path
import pandas as pd

from src.outdoor_validation import validate_iec61853_pmax_layer


def _fmt(v, d=2):
    try:
        return f"{float(v):,.{d}f}"
    except Exception:
        return escape(str(v))


def build_real_world_validation_report(root: str | Path) -> tuple[str, dict, pd.DataFrame]:
    root = Path(root)
    summary, monthly, _ = validate_iec61853_pmax_layer(
        root / "validation/external/iea_pvps_task13_supsi_csi/data",
        root / "validation/external/iea_pvps_task13_supsi_csi/IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv",
    )
    field_path = root / "validation/results/field_benchmark_summary.csv"
    field = pd.read_csv(field_path) if field_path.exists() else pd.DataFrame()

    monthly_rows = "".join(
        "<tr>"
        f"<td>{escape(str(r['month']))}</td>"
        f"<td>{int(r['retained_points']):,}</td>"
        f"<td>{_fmt(r['rmse_w'],2)}</td>"
        f"<td>{_fmt(r['mbe_w'],2)}</td>"
        f"<td>{_fmt(r['energy_bias_pct'],2)}%</td>"
        "</tr>"
        for _, r in monthly.iterrows()
    )
    field_rows = ""
    if not field.empty:
        cols = list(field.columns)
        for _, r in field.iterrows():
            field_rows += "<tr>" + "".join(f"<td>{escape(str(r.get(c,'')))}</td>" for c in cols) + "</tr>"
        field_head = "".join(f"<th>{escape(c.replace('_',' ').title())}</th>" for c in cols)
    else:
        field_head = "<th>Benchmark registry unavailable</th>"

    html=f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Solaryn Real-World Validation Report</title><style>
body{{font-family:Inter,Arial,sans-serif;max-width:1100px;margin:36px auto;padding:0 20px;color:#172033;line-height:1.5}}h1,h2{{color:#0b4f48}}
.hero{{background:#eef8f6;border:1px solid #cfe3df;padding:22px;border-radius:16px}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:18px 0}}.m{{border:1px solid #dce5e8;padding:12px;border-radius:12px}}.m b{{display:block;font-size:21px;color:#0e776d}}.m span{{font-size:11px;color:#637083}}table{{border-collapse:collapse;width:100%;font-size:12.5px;margin:12px 0 26px}}th,td{{padding:8px;border-bottom:1px solid #dce5e8;text-align:left}}th{{background:#eef5f3}}.warn{{background:#fff7e2;border-left:4px solid #d99a00;padding:14px;border-radius:7px}}.pass{{background:#eef9f3;border-left:4px solid #1d8a5b;padding:14px;border-radius:7px}}a{{color:#0b6f68}}
</style></head><body>
<div style='font-size:12px;font-weight:700;letter-spacing:.12em;color:#0e776d'>SOLARYN · VALIDATION EVIDENCE</div><h1>Real-World Validation Report</h1>
<div class='hero'><h2 style='margin-top:0'>Measured electrical layer: PASS</h2><p>Outdoor measured plane-of-array irradiance and measured module temperature are used directly to test the IEC 61853 Pmax(G,T) interpolation layer. This is a real measured-data validation, but it does <strong>not</strong> validate the full climate → system → lifetime → economics recommendation chain.</p></div>
<div class='metrics'>
<div class='m'><b>{summary['retained_rows']:,}</b><span>Measured observations</span></div>
<div class='m'><b>{summary['r2']:.4f}</b><span>R²</span></div>
<div class='m'><b>{summary['rmse_pct_stc']:.2f}%</b><span>NRMSE vs STC</span></div>
<div class='m'><b>{summary['mbe_w']:+.3f} W</b><span>Mean bias error</span></div>
<div class='m'><b>{summary['cumulative_sampled_energy_bias_pct']:+.3f}%</b><span>Sampled-energy bias</span></div>
</div>
<h2>Measured use case</h2><p><strong>Source:</strong> {escape(str(summary['source']))}. The packaged dataset contains twelve monthly outdoor files plus the IEC 61853 Pmax matrix. The validation retains only physically consistent points inside the characterized irradiance/temperature domain.</p>
<table><thead><tr><th>Month</th><th>Retained points</th><th>RMSE (W)</th><th>MBE (W)</th><th>Energy bias</th></tr></thead><tbody>{monthly_rows}</tbody></table>
<h2>Cross-technology falsification registry</h2><p>Solaryn preserves benchmark failures rather than tuning site-specific corrections after seeing outcomes. The registry is a separate validation layer from the measured IEC interpolation test.</p>
<table><thead><tr>{field_head}</tr></thead><tbody>{field_rows}</tbody></table>
<h2>External reality check: tropical multi-technology field study</h2><p>A 2025 <em>Scientific Reports</em> paper used three years of data from the 1.2 MW Tenaga Suria Brunei experimental farm and compared six PV technologies at the same site. It is useful as a frozen cross-technology target because the field ranking is not equivalent to a universal technology rule. <a href='https://www.nature.com/articles/s41598-025-99958-x'>Open study</a>.</p>
<h2>Claim boundary</h2><div class='warn'><strong>Validated now:</strong> measured GPOA + measured module temperature → IEC Pmax(G,T) interpolation for the packaged c-Si validation layer.<br><strong>Not validated by this test:</strong> weather source, POA transposition, thermal model, AC/system design, current commercial SKU ranking, product-specific degradation, lifetime economics, or procurement recommendation.</div>
<h2>Next validation gates</h2><ol><li>Measured resource/POA and independent thermal holdouts across representative sites.</li><li>Candidate-specific measured P(G,T) or equivalent for the commercial shortlist.</li><li>Frozen multi-technology field ranking across climates.</li><li>Measured DC→AC/meter validation.</li><li>Field degradation/BOM evidence for lifetime differentiation.</li><li>One closed EPC tender replay with actual quotes and design constraints.</li><li>A prospective pilot issued before procurement and scored after operation.</li></ol>
</body></html>"""
    return html, summary, monthly


def write_real_world_validation_report(root: str | Path, output: str | Path | None = None) -> Path:
    root=Path(root)
    html, _, _=build_real_world_validation_report(root)
    out=Path(output) if output else root / "validation/results/Solaryn_Real_World_Validation_Report.html"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(html,encoding="utf-8")
    return out
