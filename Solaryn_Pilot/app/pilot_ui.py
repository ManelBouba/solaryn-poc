"""Local pilot UI: inputs and rendering only; scientific outputs come from the service."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from src.pilot_service import analyze
from src.pilot_report import summary_table, package_run, explain
from src.run_store import RunStore, sha
from src.module_offer_io import load_module_offer_csv
from src.evidence_policy import project_segment_compatible
from src.data_fetchers import fetch_nasa_power_hourly_dataframe, fetch_pvgis_hourly_dataframe, pvlib_azimuth_to_pvgis_aspect

@st.cache_data(ttl=86400, max_entries=12, show_spinner=False)
def load_live(lat, lon, first, last):
    return fetch_nasa_power_hourly_dataframe(lat, lon, f"{first}-01-01", f"{last}-12-31", time_standard="UTC")

@st.cache_data(ttl=86400, max_entries=12, show_spinner=False)
def load_crosscheck(lat, lon, first, last, tilt, azimuth):
    return fetch_pvgis_hourly_dataframe(lat, lon, first, last, tilt, pvlib_azimuth_to_pvgis_aspect(azimuth))

def render_result(root, result):
    d = result["decision"]
    st.caption("COMPLETED RUN" if result["status"] == "completed" else "FAILED RUN · NO VALID RANKING")
    st.subheader(d["label"])
    st.info(d["headline"])
    if d.get("reasons"):
        with st.expander("Why this status", expanded=True):
            for reason in d["reasons"]: st.write("• " + reason)
    st.caption(f"Project: {result['project']['project_name']} · Recorded {result['created_at']} · immutable inputs")
    st.dataframe(summary_table(result), hide_index=True, width="stretch", column_config={
        "Annual DC kWh/kWp": st.column_config.NumberColumn(format="%.1f"),
        "Project MWh/year": st.column_config.NumberColumn(format="%.0f"),
        "Lifetime scenario kWh/kWp": st.column_config.NumberColumn(format="%.0f"),
    })
    tabs = st.tabs(["Energy & lifetime", "Resource", "Economics", "Evidence & validation", "Explain & export"])
    with tabs[0]:
        good = [c for c in result["candidates"] if c["simulation_status"] == "completed"]
        if good:
            chart = pd.DataFrame([{"Module": c["model"], "kWh/kWp/year": c["metrics"]["annual_yield_kwh_kwp"]} for c in good])
            st.bar_chart(chart, x="Module", y="kWh/kWp/year", horizontal=True, color="#087F8C")
        if result["monthly"]:
            st.subheader("Seasonal production")
            names = {c["module_id"]: c["model"] for c in result["candidates"]}
            st.line_chart(pd.DataFrame(result["monthly"]).pivot(index="month", columns="module_id", values="energy_kwh_kwp").rename(columns=names))
        with st.expander("Lifetime scenario and stress diagnostics"):
            st.caption("Declared common degradation; no product-specific lifetime forecast.")
            st.dataframe(pd.DataFrame(result["lifetime"]), hide_index=True)
            st.dataframe(pd.DataFrame(result["stress"]), hide_index=True)
    with tabs[1]:
        st.info(result["resource"]["reason"])
        st.dataframe(pd.DataFrame(result["resource"]["benchmark"]), hide_index=True)
        st.caption("Monthly contributions in kWh/m². Independent sources are not blended.")
        st.json(result["resource"]["providers"], expanded=False)
    with tabs[2]:
        e = result["economics"]
        st.caption(f"Declared currency: {e['currency']} · no currency conversion")
        if e["switching_threshold"]:
            st.dataframe(pd.DataFrame(e["switching_threshold"]), hide_index=True)
            st.caption("Module + area-BOS sensitivity; evidence eligibility remains binding. Not full LCOE.")
        else: st.info(e.get("reason", "Add a real supplier quote for the baseline to enable switching economics."))
    with tabs[3]:
        for c in result["candidates"]:
            with st.expander(c["manufacturer"] + " " + c["model"]):
                st.write("Simulation: " + c["simulation_status"])
                st.json({"inputs": c["inputs"], "model": c["metrics"].get("electrical_model"), "evidence": c["metrics"].get("model_evidence_level"), "warnings": c["warnings"]}, expanded=False)
        st.dataframe(pd.DataFrame([{"Gate": k.replace('_', ' '), "Status": v} for k, v in result["validation_gates"].items()]), hide_index=True)
        for text in result["limitations"]: st.write("• " + text)
    with tabs[4]:
        grounded = explain(result)
        st.write(grounded["text"])
        st.caption("Deterministic explanation of this saved result. No external AI service receives project data.")
        st.code(result["run_id"], language=None)
        st.json(result["versions"], expanded=False)
        store = RunStore(root / "workspace/runs")
        name, payload = package_run(store, result["run_id"])
        st.download_button("Download Solaryn analysis", payload, name, "application/zip", type="primary", key="pilot_zip")
        folder = store.root / result["run_id"]
        st.download_button("Download exact result JSON", (folder / "Result.json").read_bytes(), "Solaryn_Result.json", "application/json")
        st.download_button("Download decision report", (folder / "Decision.html").read_bytes(), "Solaryn_Decision.html", "text/html")

def render_archive(root):
    st.title("Saved project analyses")
    store = RunStore(root / "workspace/runs")
    try: runs = store.list_runs()
    except ValueError as exc:
        st.error(str(exc)); return
    if store.unreadable_runs:
        st.warning("Some development records are not readable under the current operating-system permissions. They were left untouched.")
    if not runs:
        st.info("Complete an analysis to create a persistent project record."); return
    selected = st.selectbox("Analysis revision", list(range(len(runs))), format_func=lambda i: f"{runs[i]['project']['project_name']} · {runs[i]['created_at']} · {runs[i]['decision']['label']}")
    render_result(root, runs[selected])

def render_pilot(root):
    st.caption("SOLARYN / PROJECT WORKSPACE")
    st.title("Compare modules. Understand the evidence.")
    st.write("Project → Site & climate → Candidates → Decision → Export")
    if "pilot_last_run" in st.session_state:
        if st.session_state.pop("pilot_show_results", False):
            st.session_state.pilot_view = "Results"
        st.session_state.setdefault("pilot_view", "Results")
        mode = st.segmented_control("Workspace view", ["Configure", "Results"], key="pilot_view")
        if mode == "Results":
            render_result(root, RunStore(root / "workspace/runs").read(st.session_state.pilot_last_run)); return
    source = st.selectbox("Climate source", ["Saved Riyadh reference · 2020", "Live NASA POWER"])
    saved = source.startswith("Saved")
    if saved: st.caption("8,784 recorded UTC hours. Source metadata and checksum are preserved. No live climate request.")
    st.session_state.setdefault("pilot_lat", 24.7136)
    st.session_state.setdefault("pilot_lon", 46.6753)
    if not saved:
        query = st.text_input("Search city or place")
        if st.button("Find location"):
            try:
                from app.epc_module_mode import _geocode_city
                place = _geocode_city(query)
                st.session_state.pilot_lat, st.session_state.pilot_lon = place["lat"], place["lon"]
                st.session_state.pilot_place = place["display_name"]
            except Exception as exc: st.error(str(exc))
        with st.expander("Select on map"):
            m = folium.Map(location=[st.session_state.pilot_lat, st.session_state.pilot_lon], zoom_start=5)
            folium.Marker([st.session_state.pilot_lat, st.session_state.pilot_lon]).add_to(m)
            click = st_folium(m, height=300, key="pilot_map", returned_objects=["last_clicked"])
            if click and click.get("last_clicked") and click["last_clicked"] != st.session_state.get("pilot_previous_click"):
                st.session_state.pilot_previous_click = click["last_clicked"]
                st.session_state.pilot_lat = click["last_clicked"]["lat"]
                st.session_state.pilot_lon = click["last_clicked"]["lng"]
                st.rerun()
    st.subheader("1 · Project and site")
    name = st.text_input("Project name", value="Riyadh reference" if saved else st.session_state.get("pilot_place", "Solar project"))
    a, b, c = st.columns(3)
    segment = a.selectbox("Project segment", ["utility", "commercial", "residential", "research"])
    size = b.number_input("DC capacity (MWp)", min_value=.001, value=100.)
    years = c.number_input("Operating life (years)", min_value=1, max_value=100, value=25)
    a, b = st.columns(2)
    if saved:
        lat, lon = 24.7136, 46.6753
        a.write("Latitude: 24.7136°"); b.write("Longitude: 46.6753°")
    else:
        lat = a.number_input("Latitude", min_value=-90., max_value=90., key="pilot_lat", format="%.6f")
        lon = b.number_input("Longitude", min_value=-180., max_value=180., key="pilot_lon", format="%.6f")
    a, b, c = st.columns(3)
    first = a.number_input("First resource year", 2001, 2024, 2020, disabled=saved)
    last = b.number_input("Last resource year", 2001, 2024, 2020, disabled=saved)
    crosscheck = c.checkbox("Independent PVGIS check", value=False, help="Failure remains visible and prevents a robust resource claim.")
    a, b, c = st.columns(3)
    tilt = a.number_input("Fixed tilt (degrees)", 0., 90., 25.)
    azimuth = b.number_input("Azimuth (degrees from north)", 0., 360., 180.)
    soiling = c.number_input("Common soiling (%)", 0., 50., 2.)
    row = st.checkbox("Enable row shading and rear irradiance", value=False)
    with st.expander("Geometry, lifetime and decision assumptions"):
        a, b, c = st.columns(3)
        albedo = a.number_input("Albedo", 0., 1., .2)
        gcr = b.number_input("Ground coverage ratio", .02, .95, .4)
        height = c.number_input("Row center height (m)", .1, 10., 1.5)
        pitch = a.number_input("Row pitch (m)", .1, 30., 5.)
        degradation = b.number_input("Common degradation scenario (%/year)", 0., 20., .5)
        guardrail = c.number_input("Decision separation guardrail (%)", 0., 100., 2.)
        geometry = st.selectbox("Geometry evidence", ["screening_assumptions", "project_design", "measured"])
        stage = st.selectbox("Development stage", ["screening", "feasibility", "procurement_review"])
        objective = st.text_input("Decision objective", "Compare modeled DC energy and evidence under common assumptions")
    st.subheader("2 · Exact module candidates")
    upload = st.file_uploader("Import module offers CSV", type=["csv"])
    try:
        modules = load_module_offer_csv(upload if upload else root / "data/raw/module_candidate_master.csv")
    except ValueError as exc:
        st.error(str(exc)); return
    compatible = modules[modules.apply(lambda r: project_segment_compatible(r, segment), axis=1)]
    defaults = [i for i in compatible.module_id if i.startswith(("MOD_PERC_", "MOD_TOPCON_JINKO", "MOD_CDTE_"))]
    selected = st.multiselect("Candidate modules", compatible.module_id.tolist(), default=defaults,
        format_func=lambda mid: " · ".join(compatible.loc[compatible.module_id == mid, ["manufacturer", "model"]].iloc[0]))
    modules = compatible[compatible.module_id.isin(selected)].copy()
    st.dataframe(modules[["manufacturer", "model", "technology_label", "pmax_w", "gamma_pmax_pct_c", "module_area_m2", "source_url"]], hide_index=True)
    with st.expander("Supplier quotes and financial assumptions"):
        currency = st.selectbox("Quote and cash-flow currency", ["USD", "EUR"])
        st.caption("Enter actual quotes only. Energy value and BOS are declared scenario assumptions in this same currency.")
        quote_col = "quote_usd_w" if currency == "USD" else "quote_eur_w"
        if quote_col not in modules: modules[quote_col] = float("nan")
        edited = st.data_editor(modules[["module_id", "model", quote_col]], disabled=["module_id", "model"], hide_index=True, key="pilot_quotes")
        modules[quote_col] = edited[quote_col].to_numpy()
        baseline = st.selectbox("Quoted baseline module", selected) if selected else None
        a, b, c = st.columns(3)
        value = a.number_input(f"Energy value ({currency}/kWh)", 0., 2., .05)
        discount = b.number_input("Real discount rate (%)", 0., 30., 7.)
        bos = c.number_input(f"Area-sensitive BOS ({currency}/m²)", 0., 1000., 0.)
    st.subheader("3 · Run and review")
    if st.button("Run evidence-based comparison", type="primary", disabled=len(modules) < 2):
        try:
            if not name.strip(): raise ValueError("Project name is required.")
            if first > last: raise ValueError("First year must not exceed last year.")
            with st.status("Preparing immutable analysis", expanded=True) as progress:
                if saved:
                    path = root / "data/reference/riyadh_hourly.csv"
                    meta = json.loads((path.parent / "riyadh_weather.json").read_text())
                    if sha(path.read_bytes()) != meta["sha256"]: raise ValueError("Saved weather checksum mismatch.")
                    nasa = pd.read_csv(path, parse_dates=["time_utc"])
                    nasa.attrs.update(meta["metadata"]); nasa.attrs["source_snapshot_metadata"] = meta
                    first = last = 2020
                else:
                    progress.write("Retrieving NASA POWER UTC climate…")
                    nasa = load_live(lat, lon, first, last)
                pv, provider_warning = None, None
                if crosscheck:
                    try: pv = load_crosscheck(lat, lon, first, last, tilt, azimuth)
                    except Exception as exc: provider_warning = str(exc)
                project = dict(project_name=name, latitude=lat, longitude=lon, system_size_mw=size,
                    target_lifetime_years=years, project_segment=segment, development_stage=stage, objective=objective,
                    geometry_type="fixed_tilt", tilt_deg=tilt, azimuth_deg=azimuth, row_geometry_enabled=row,
                    albedo=albedo, albedo_source="user_assumption", gcr=gcr, row_height_m=height, row_pitch_m=pitch,
                    geometry_confidence=geometry, soiling_loss_pct=soiling, common_degradation_pct_year=degradation,
                    guardrail_pct=guardrail, currency=currency, baseline_module_id=baseline,
                    energy_value_per_kwh=value, discount_rate_pct=discount, area_bos_per_m2=bos,
                    financial_assumptions_basis="user_declared_constant_real_currency", provider_warning=provider_warning)
                progress.write("Calculating physics, evidence gates and decision…")
                result = analyze(root, project, modules, nasa, pv)
                st.session_state.pilot_last_run = result["run_id"]
                st.session_state.pilot_show_results = True
                st.session_state.city_search_query = name
                st.session_state.location_configured = True
                progress.update(label="Analysis recorded", state="complete", expanded=False)
            st.rerun()
        except Exception as exc:
            st.error("Analysis could not complete. No new recommendation was issued.")
            st.code(str(exc), language=None)
