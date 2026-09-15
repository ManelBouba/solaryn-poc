from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = ROOT / "app" / "assets" / "solaryn_logo.png"
sys.path.append(str(ROOT))

from src.climate_fingerprint import compute_climate_fingerprint
from src.copilot_prompt import build_explanation_payload, local_copilot_explanation
from src.data_fetchers import (
    fetch_nasa_power_hourly_dataframe,
    fetch_pvgis_hourly_dataframe,
    nasa_hourly_to_site_summary,
)
from src.forecast_engine import forecast_25_years
from src.outdoor_validation import validate_iec61853_pmax_layer
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.recommendation_engine import (
    decision_leaders,
    filter_candidate_universe,
    project_decision_summary,
    rank_technologies,
)
from app.epc_module_mode import render_epc_module_mode
from app.pilot_ui import render_pilot, render_archive
from app.procurement_ui import render_procurement

st.set_page_config(
    page_title="Solaryn | PV decision intelligence",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1500px;}
    [data-testid="stSidebar"] {border-right: 1px solid rgba(49, 80, 73, .15);}
    h1 {letter-spacing: -0.03em;}
    div[data-testid="stMetric"] {border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)



def _navigate(destination: str) -> None:
    st.session_state.app_destination = destination


st.session_state.setdefault("app_destination", "Overview")

with st.sidebar:
    st.image(str(LOGO_PATH), width="stretch")
    st.caption("PV DECISION INTELLIGENCE")
    nav_items = [
        ("Overview", ":material/home:"),
        ("Module Recommendation", ":material/solar_power:"),
        ("Procurement Workspace", ":material/balance:"),
        ("Technology Library", ":material/science:"),
        ("Validation Center", ":material/verified:"),
        ("Downloads", ":material/download:"),
        ("Method & Evidence", ":material/fact_check:"),
    ]
    for destination, icon in nav_items:
        st.button(
            destination,
            icon=icon,
            key=f"nav_{destination.lower().replace(' ', '_').replace('&', 'and')}",
            type="primary" if st.session_state.app_destination == destination else "tertiary",
            width="stretch",
            on_click=_navigate,
            args=(destination,),
        )

    st.divider()
    st.caption("ACTIVE PROJECT")
    active_project = st.session_state.get("city_search_query", "").strip() or st.session_state.get("resolved_city", "").strip()
    if st.session_state.get("location_configured") and active_project:
        st.button(
            active_project,
            icon=":material/location_on:",
            key="nav_current_project",
            type="primary" if st.session_state.app_destination == "Module Recommendation" else "secondary",
            width="stretch",
            on_click=_navigate,
            args=("Module Recommendation",),
        )
        st.caption("Project location selected")
    else:
        st.button(
            "Start a project",
            icon=":material/add_location_alt:",
            key="nav_current_project",
            type="primary" if st.session_state.app_destination == "Module Recommendation" else "secondary",
            width="stretch",
            on_click=_navigate,
            args=("Module Recommendation",),
        )
        st.caption("Choose any city or map location")


destination = st.session_state.app_destination

if destination == "Procurement Workspace":
    render_procurement(ROOT)
    st.stop()

if destination == "Module Recommendation":
    render_pilot(ROOT)
    st.stop()

if destination == "Downloads":
    render_archive(ROOT)
    st.stop()

if destination == "Overview":
    st.caption("SOLARYN")
    st.title("Choose the PV technology that creates the most project value.")
    st.write(
        "Solaryn connects site climate, module physics, lifetime evidence and project economics "
        "to compare real PV candidates under one transparent decision framework."
    )
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1.container(border=True):
        st.badge("SITE", color="blue", icon=":material/location_on:")
        st.subheader("Climate-specific")
        st.caption("Hourly irradiance, temperature, wind, humidity and geometry drive the comparison.")
    with c2.container(border=True):
        st.badge("EVIDENCE", color="green", icon=":material/fact_check:")
        st.subheader("Candidate-specific")
        st.caption("Measured data is preferred; fallbacks remain visible and widen uncertainty.")
    with c3.container(border=True):
        st.badge("VALUE", color="orange", icon=":material/paid:")
        st.subheader("Decision-specific")
        st.caption("Technical leader, lifetime leader and commercial switching value stay separate.")

    st.subheader("Project workspace")
    with st.container(border=True):
        a, b = st.columns([3, 1], vertical_alignment="center")
        with a:
            current_project = st.session_state.get("city_search_query", "").strip() or st.session_state.get("resolved_city", "").strip()
            if st.session_state.get("location_configured") and current_project:
                st.subheader(current_project)
                st.caption("Site-specific PV module comparison")
                st.write("Continue the current analysis, compare candidates, and export a project package named for this location.")
            else:
                st.subheader("Start with any project location")
                st.caption("Search a city, click the map, or enter coordinates")
                st.write("Solaryn creates a site-specific comparison and saves the result using the selected city/project name.")
        b.button(
            "Open analysis",
            icon=":material/arrow_forward:",
            type="primary",
            width="stretch",
            on_click=_navigate,
            args=("Module Recommendation",),
        )

    st.subheader("Decision flow")
    st.markdown(
        ":blue-badge[1 Site]  →  :blue-badge[2 Feasibility]  →  "
        ":green-badge[3 Physics]  →  :green-badge[4 Lifetime]  →  "
        ":orange-badge[5 Economics]  →  :gray-badge[6 Uncertainty & evidence]"
    )
    o1, o2, o3 = st.columns(3)
    o1.metric("Sourced commercial SKUs", "10", border=True)
    o2.metric("Technology research records", "30", border=True)
    o3.metric("Measured validation points", "28,286", border=True)
    st.caption("Solaryn separates robust modeled advantage, provisional leadership, effective ties and insufficient evidence.")
    st.stop()

@st.cache_data(show_spinner=False)
def _measured_validation_bundle(root_str: str):
    root = Path(root_str)
    summary, monthly, retained = validate_iec61853_pmax_layer(
        root / "validation/external/iea_pvps_task13_supsi_csi/data",
        root / "validation/external/iea_pvps_task13_supsi_csi/IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv",
    )
    scatter = retained.loc[:, ["Pm", "predicted_pmax_w"]].iloc[::40].copy()
    scatter = scatter.rename(columns={"Pm": "Measured Pmax (W)", "predicted_pmax_w": "Predicted Pmax (W)"})
    return summary, monthly, scatter


if destination == "Validation Center":
    st.caption("MEASURED DATA / FALSIFICATION")
    st.title("Real-world validation center")
    st.write(
        "Solaryn keeps model validation separate from product recommendation. This page shows measured-data tests, "
        "their error metrics, and the exact claims they do — and do not — support."
    )
    summary, monthly, scatter = _measured_validation_bundle(str(ROOT))

    st.success(
        "Measured electrical-layer validation passed on the packaged IEA PVPS Task 13 / SUPSI outdoor dataset. "
        "This validates measured GPOA + measured module temperature → IEC Pmax(G,T) interpolation, not the full end-to-end recommendation engine.",
        icon=":material/verified:",
    )
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Measured points", f"{summary['retained_rows']:,}", border=True)
    m2.metric("R²", f"{summary['r2']:.4f}", border=True)
    m3.metric("NRMSE vs STC", f"{summary['rmse_pct_stc']:.2f}%", border=True)
    m4.metric("MBE", f"{summary['mbe_w']:+.3f} W", border=True)
    m5.metric("Sampled energy bias", f"{summary['cumulative_sampled_energy_bias_pct']:+.3f}%", border=True)

    v1, v2 = st.columns(2, gap="large")
    with v1:
        st.markdown("### Measured vs predicted power")
        st.scatter_chart(scatter, x="Measured Pmax (W)", y="Predicted Pmax (W)", height=360)
        st.caption("Downsampled only for rendering; all retained observations are used in the metrics above.")
    with v2:
        st.markdown("### Monthly model error")
        monthly_plot = monthly.set_index("month")[["energy_bias_pct", "rmse_w"]].copy()
        st.line_chart(monthly_plot[["energy_bias_pct"]], height=180)
        st.bar_chart(monthly_plot[["rmse_w"]], height=180)

    st.markdown("### Frozen field benchmark registry")
    field = pd.read_csv(ROOT / "validation/results/field_benchmark_summary.csv")
    st.dataframe(field, hide_index=True, width="stretch")
    st.caption(
        "Failures remain visible by design. A benchmark is not allowed to inject a site-specific winner correction into production code."
    )

    st.markdown("### External multi-technology reality check")
    st.info(
        "Brunei's 1.2 MW Tenaga Suria Brunei field study compared six PV technologies at the same tropical site over three years. "
        "Solaryn keeps this as a cross-technology falsification target rather than turning the paper's winner into a tropical technology bonus."
    )
    st.markdown("[Open the 2025 Scientific Reports study](https://www.nature.com/articles/s41598-025-99958-x)")

    st.markdown("### Validation ladder")
    gates = pd.DataFrame([
        ("V1", "Resource / POA", "Measured POA validation", "Required for site irradiance confidence"),
        ("V2", "Thermal", "Independent measured module-temperature holdout", "Packaged thermal holdout evidence"),
        ("V3", "Electrical", "Measured P(G,T) / outdoor power", "Passed for the packaged SUPSI c-Si layer"),
        ("V4", "System", "Measured DC → AC / meter output", "Still required for delivered-energy validation"),
        ("V5", "Cross-technology rank", "Frozen multi-technology field benchmarks", "In progress; failures preserved"),
        ("V6", "Lifetime", "Field degradation / calibrated reliability", "Still required for lifetime differentiation"),
        ("V7", "Procurement", "Closed tender replay with real offers", "Next client-validation target"),
        ("V8", "Prospective pilot", "Recommendation before build, then monitored", "Strongest future validation"),
    ], columns=["Gate", "Layer", "Required proof", "Current Solaryn status"])
    st.dataframe(gates, hide_index=True, width="stretch")
    st.warning(
        "Do not call the current measured test 'full-product validation'. It is strong evidence for one electrical layer. "
        "End-to-end, cross-technology, lifetime and procurement claims require the later gates above.",
        icon=":material/gpp_maybe:",
    )
    st.stop()


if destination == "Downloads":
    st.caption("CLIENT OUTPUTS")
    st.title("Downloads")
    st.write("Run a module recommendation, then export the recommendation report and comparison datasets directly from the analysis page.")
    st.info(
        "After each run, Solaryn creates a complete ZIP named from the selected city/project and the technical-leading technology, plus standalone HTML and CSV exports.",
        icon=":material/info:",
    )
    st.button(
        "Open module recommendation",
        icon=":material/arrow_forward:",
        type="primary",
        on_click=_navigate,
        args=("Module Recommendation",),
    )
    st.stop()

if destination == "Method & Evidence":
    st.caption("METHOD & EVIDENCE")
    st.title("How Solaryn reaches a recommendation")
    st.write(
        "Every feasible candidate sees the same site and project conditions. Differences are introduced only by "
        "candidate-specific physical evidence, system constraints and commercial inputs."
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Measured electrical validation", "28,286 points", border=True)
    m2.metric("Thermal holdout RMSE", "1.39 K", border=True)
    m3.metric("Decision outputs", "P(best) + regret", border=True)

    st.subheader("Evidence routing")
    st.write(
        "**Electrical:** measured IEC 61853 matrix → validated device model → datasheet fit → evidence-limited fallback.  \n"
        "**Thermal:** measured/module-specific coefficients → mounting-class model → conservative fallback.  \n"
        "**Lifetime:** same-SKU field data → BOM analogue → calibrated mechanism model → neutral shared scenario."
    )
    st.subheader("Decision boundary")
    st.warning(
        "A technical leader is not automatically the final procurement recommendation. "
        "Solaryn keeps evidence-limited candidates visible, widens their uncertainty, and can request better evidence before final selection.",
        icon=":material/gpp_maybe:",
    )
    st.caption("See docs/PILOT_MODEL_CARD.md and docs/PILOT_DELIVERY.md for the active model and validation scope.")
    st.button("Open validation center", icon=":material/verified:", type="primary", on_click=_navigate, args=("Validation Center",))
    st.stop()

if destination != "Technology Library":
    st.stop()

st.warning(
    "Technology Intelligence preserves SOLARYN's scientific knowledge base, but its current literature-range parameters and weighted scores are heuristic. "
    "Treat outputs as research hypotheses only. They cannot be approved as procurement decisions or override EPC Module Comparison evidence."
)


@st.cache_data
def load_technology_data() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data/raw/technology_master.csv")


@st.cache_data(show_spinner=True)
def nasa_hourly(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    return fetch_nasa_power_hourly_dataframe(lat, lon, start, end)


@st.cache_data(show_spinner=True)
def pvgis_hourly(lat: float, lon: float, start_year: int, end_year: int) -> pd.DataFrame:
    return fetch_pvgis_hourly_dataframe(lat, lon, start_year, end_year)


def _candidate_frame(all_tech: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "Commercial + niche":
        return filter_candidate_universe(all_tech, "Commercial deployment", include_niche=True, include_bifacial=False)
    if scope == "R&D exploration":
        return filter_candidate_universe(all_tech, "R&D exploration")
    return filter_candidate_universe(all_tech, "Commercial deployment", include_niche=False, include_bifacial=False)


def _weight_label(metric: str) -> str:
    labels = {
        "lifetime_relative": "Lifetime energy",
        "annual_yield_relative": "Annual yield",
        "value_relative": "Economic value",
        "risk_relative": "Climate/project resilience",
        "degradation_relative": "Degradation",
        "temperature_relative": "Temperature",
        "soiling_relative": "Soiling",
        "area_annual_relative": "Area yield",
        "area_lifetime_relative": "Area lifetime energy",
        "readiness_absolute": "Commercial readiness",
        "confidence_absolute": "Data confidence",
    }
    return labels.get(metric, metric)


all_tech = load_technology_data()
st.session_state.setdefault("selected_lat", 24.7136)
st.session_state.setdefault("selected_lon", 46.6753)

st.caption("TECHNOLOGY INTELLIGENCE")
st.title("Technology Intelligence")
st.write("Explore material and technology hypotheses using the preserved SOLARYN knowledge base.")
st.caption("Literature-range and assumed inputs are research diagnostics, not procurement evidence.")
st.subheader("Project setup")
with st.container(border=True):
    row1 = st.columns([1.05, 1.05, .85, .95, .9])
    with row1[0]:
        start = st.date_input("Reference-year start", date(2023, 1, 1))
    with row1[1]:
        end = st.date_input("Reference-year end", date(2023, 12, 31))
    with row1[2]:
        system_size = st.number_input("System size (MW)", 0.001, 5000.0, 1.0)
    with row1[3]:
        site_type = st.selectbox("Use case", ["utility", "commercial", "rooftop", "research"])
    with row1[4]:
        budget = st.selectbox("Budget", ["low", "medium", "high"], index=1)

    row2 = st.columns([1.35, 1.15, 1, .9])
    with row2[0]:
        objective = st.selectbox(
            "Decision objective",
            [
                "Balanced project fit",
                "Lifetime energy",
                "Economic value",
                "Lowest climate risk",
                "Area-constrained project",
            ],
            index=1,
        )
    with row2[1]:
        candidate_scope = st.selectbox(
            "Candidate universe",
            ["Commercial technologies", "Commercial + niche", "R&D exploration"],
            index=0,
        )
    with row2[2]:
        use_pvgis = st.toggle("Run PVGIS cross-check", value=True)
    with row2[3]:
        run = st.button("Run Solaryn analysis", type="primary", width="stretch")

    assumptions = st.columns([1, 1, 2.3])
    with assumptions[0]:
        project_degradation = st.number_input("Project degradation scenario (%/year)", 0.0, 3.0, 0.50, 0.05)
    with assumptions[1]:
        project_soiling = st.number_input("Project soiling loss assumption (%)", 0.0, 30.0, 2.0, 0.5)
    with assumptions[2]:
        st.caption("These assumptions are shared by all technologies. Database-specific degradation and resilience fields remain visible for research, but cannot determine a commercial decision.")

candidate_tech = _candidate_frame(all_tech, candidate_scope)

if candidate_scope == "R&D exploration":
    st.warning("R&D exploration mixes commercial, pilot, and research technologies. Use it to generate hypotheses, not procurement decisions.")
else:
    st.caption("Default screening scope excludes research/pilot candidates. Bifacial gain is used only when rear-side irradiance and bifaciality evidence are explicitly supplied; no generic bifacial bonus is assumed.")

st.subheader("Select project location")
lat = float(st.session_state.selected_lat)
lon = float(st.session_state.selected_lon)

map_col, info_col = st.columns([2.15, 1])
with map_col:
    m = folium.Map([lat, lon], zoom_start=4, tiles="OpenStreetMap", control_scale=True)
    folium.Marker(
        [lat, lon],
        tooltip="Selected project location",
        icon=folium.Icon(color="green", icon="bolt", prefix="fa"),
    ).add_to(m)
    folium.LatLngPopup().add_to(m)
    res = st_folium(m, height=470, returned_objects=["last_clicked"], width=None)
    if res and res.get("last_clicked"):
        new_lat = float(res["last_clicked"]["lat"])
        new_lon = float(res["last_clicked"]["lng"])
        if abs(new_lat - lat) > 1e-7 or abs(new_lon - lon) > 1e-7:
            st.session_state.selected_lat = new_lat
            st.session_state.selected_lon = new_lon
            lat, lon = new_lat, new_lon

with info_col:
    st.badge(f"{lat:.5f}, {lon:.5f}", icon=":material/location_on:", color="blue")
    st.markdown("### Analysis methodology")
    st.write("1. Select the project point and one explicit objective.")
    st.write("2. Download one full reference year of NASA POWER hourly climate.")
    st.write("3. Use pvlib for solar position, Perez-Driesse POA, component-wise IAM optics and atmospheric inputs.")
    st.write("4. Compare only the appropriate candidate universe.")
    st.write("5. Run the evidence hierarchy: measured IEC 61853 Pmax(G,T) first; explicit fallback models second; report every fallback.")
    st.write("6. Separate heat/humidity/UV/salinity exposure from degradation-rate claims, then cross-check irradiation with PVGIS.")

if not run:
    st.space("small")
    preview_cols = st.columns(5)
    preview_cols[0].metric("Active candidates", len(candidate_tech))
    preview_cols[1].metric("Primary decision", objective)
    preview_cols[2].metric("Primary climate", "NASA hourly")
    preview_cols[3].metric("Physics", "pvlib")
    preview_cols[4].metric("External cross-check", "PVGIS" if use_pvgis else "Off")
    st.stop()

if start > end:
    st.error("Start date must be before end date.")
    st.stop()

analysis_days = (end - start).days + 1
if analysis_days < 330 or analysis_days > 370:
    st.error(
        "The screening methodology requires one approximately full reference year (330–370 days). "
        "Short or multi-year periods would otherwise be mislabeled as annual yield and would distort the 25-year comparison."
    )
    st.stop()

with st.spinner("Downloading hourly climate and running Technology Intelligence..."):
    nh = nasa_hourly(lat, lon, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    weather = nasa_hourly_to_pvlib_weather(nh, lat, lon)
    site_raw = nasa_hourly_to_site_summary(
        nh,
        lat,
        lon,
        project_name="Selected project",
        system_size_mw=system_size,
        site_type=site_type,
        budget_level=budget,
    )
    site_raw["degradation_scenario_pct_year"] = float(project_degradation)
    site_raw["soiling_loss_assumption_pct"] = float(project_soiling)
    site = compute_climate_fingerprint(site_raw).iloc[0]
    ranking = rank_technologies(
        site,
        candidate_tech,
        weather=weather,
        objective=objective,
        budget_level=budget,
    )
    leaders = decision_leaders(ranking)
    decision = project_decision_summary(ranking)

    pvgis_df = None
    pvgis_error = None
    if use_pvgis:
        try:
            pvgis_df = pvgis_hourly(lat, lon, start.year, end.year)
            pvgis_df = pvgis_df[
                (pd.to_datetime(pvgis_df["date"]).dt.date >= start)
                & (pd.to_datetime(pvgis_df["date"]).dt.date <= end)
            ].copy()
        except Exception as exc:
            pvgis_error = str(exc)

outputs = ROOT / "outputs"
outputs.mkdir(exist_ok=True)
nh.to_csv(outputs / "nasa_power_hourly_selected_point.csv", index=False)
weather.to_csv(outputs / "pvlib_hourly_physics_weather.csv", index=False)
ranking.drop(columns=["reasons", "risks", "decision_reasons", "tradeoffs"]).to_csv(
    outputs / "recommendations_selected_point.csv", index=False
)
decision["top3"].drop(columns=["reasons", "risks", "decision_reasons", "tradeoffs"]).to_csv(
    outputs / "top3_project_recommendation.csv", index=False
)
if pvgis_df is not None:
    pvgis_df.to_csv(outputs / "pvgis_hourly_crosscheck.csv", index=False)

st.space("small")
st.subheader("Climate + physics snapshot")
metric_cols = st.columns(4) + st.columns(3)
metrics = [
    ("NASA hourly rows", f"{len(nh):,}"),
    ("Reference-year GHI", f"{site['ghi_kwh_m2_year']:.0f} kWh/m²"),
    ("Avg air temp", f"{site['avg_temp_c']:.1f} °C"),
    ("P95 cell temp", f"{weather['temp_cell_c'].quantile(.95):.1f} °C"),
    ("Heat stress", f"{site['heat_stress_index']:.0f}/100"),
    ("Soiling stress", f"{site['soiling_stress_index']:.0f}/100"),
    ("Active candidates", f"{len(candidate_tech)}"),
]
for col, (label, value) in zip(metric_cols, metrics):
    col.metric(label, value)

st.subheader("Leading research hypotheses")
status_cols = st.columns([1.2, 1, 2.4])
status_cols[0].metric("Lifetime-energy gap to #2", f"{decision['lifetime_energy_gap_to_second_pct']:+.2f}%")
status_cols[1].metric("Composite score gap", f"{decision['score_gap_to_second']:.1f} pts")
status_cols[2].info(
    f"Objective: **{objective}** · **{decision['decision_separation_label']}**. "
    "Solaryn no longer displays a numerical scientific-confidence percentage until uncertainty is actually quantified."
)

card_cols = st.columns(3, gap="large")
for idx, (_, result) in enumerate(decision["top3"].iterrows(), start=1):
    with card_cols[idx - 1]:
        badge = ("No clear separation · leading candidate" if idx == 1 and decision["decision_separation_label"].startswith(("Essentially", "Close")) else ("Leading research candidate" if idx == 1 else f"Research alternative #{idx}"))
        first_reason = result["decision_reasons"][0] if result["decision_reasons"] else "Competitive project result."
        with st.container(border=True):
            st.badge(badge, color="orange" if idx == 1 else "gray")
            st.subheader(result["technology_name"])
            st.caption(f"{result['family']} · {result['commercialization_status']}")
            st.metric("Research-screening score", f"{result['project_fit_score']:.1f}/100")
            st.write(f"Annual yield: **{result['annual_yield_kwh_kwp']:.0f} kWh/kWp**")
            st.write(f"25-year energy index: **{result['lifetime_energy_index_25y']:.0f}**")
            st.write(f"Energy / area: **{result['annual_yield_kwh_m2']:.0f} kWh/m²**")
            st.write(f"DB module-cost proxy: **${result['module_cost_usd_w']:.2f}/W**")
            st.write(f"Risk resilience: **{result['lowest_risk_score']:.1f}/100**")
            st.caption(first_reason)

st.subheader("Explore the research results")
tab_decision, tab_lenses, tab_physics, tab_pvgis, tab_forecast, tab_model = st.tabs([
    "Research results",
    "Lifetime / value / risk lenses",
    "NASA hourly + pvlib",
    "PVGIS cross-check",
    "25-year scenario + Copilot",
    "Model boundaries",
])

with tab_decision:
    st.markdown("### Explicit objective weights")
    weights = decision["objective_weights"]
    weight_df = pd.DataFrame(
        [{"Decision component": _weight_label(k), "Weight %": v * 100.0} for k, v in weights.items()]
    )
    st.dataframe(
        weight_df,
        width="stretch",
        hide_index=True,
        column_config={"Weight %": st.column_config.ProgressColumn(min_value=0.0, max_value=100.0, format="%.0f%%")},
    )
    st.caption("Weights are visible decision preferences, not physics. The raw energy, temperature, spectral and degradation-scenario outputs remain visible beside the score.")

    show = [
        "project_rank", "technology_name", "family", "project_fit_score",
        "annual_yield_kwh_kwp", "annual_yield_kwh_m2", "lifetime_energy_index_25y",
        "module_cost_usd_w", "adjusted_degradation_pct_year", "database_degradation_pct_year", "degradation_stress_factor", "temperature_effect_pct",
        "spectral_effect_pct", "soiling_loss_pct", "source_quality", "best_lifetime_score", "best_value_score", "lowest_risk_score",
        "commercial_readiness_score",
    ]
    st.dataframe(ranking[show], width="stretch", hide_index=True)
    st.bar_chart(ranking.set_index("technology_name")[["project_fit_score"]])

    choice = st.selectbox("Inspect technology", ranking["technology_name"].tolist())
    selected = ranking[ranking.technology_name == choice].iloc[0]
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("### Why it scores where it does")
        for item in selected["decision_reasons"]:
            st.success(item)
    with c2:
        st.markdown("### Trade-offs / validation")
        for item in selected["tradeoffs"]:
            st.warning(item)
        for item in selected["risks"]:
            st.warning(item)

with tab_lenses:
    st.caption("These independent research lenses keep the composite screening score from hiding important trade-offs.")
    lens_cols = st.columns(3, gap="large")
    lens_specs = [
        ("Best lifetime performance", leaders["best_lifetime"], "best_lifetime_score"),
        ("Best economic value", leaders["best_value"], "best_value_score"),
        ("Lowest climate/project risk", leaders["lowest_risk"], "lowest_risk_score"),
    ]
    for col, (label, result, score_key) in zip(lens_cols, lens_specs):
        with col:
            st.markdown(f"### {label}")
            st.metric(result["technology_name"], f"{result[score_key]:.1f}/100")
            st.write(f"Annual yield: **{result['annual_yield_kwh_kwp']:.0f} kWh/kWp**")
            st.write(f"Project degradation scenario: **{result['adjusted_degradation_pct_year']:.2f}%/y**")
            st.write(f"Database technology degradation field: **{result['database_degradation_pct_year']:.2f}%/y** (reference only)")
            st.write(f"Environmental stress factor: **{result['degradation_stress_factor']:.2f}×**")
            st.write(f"Database module-cost proxy: **${result['module_cost_usd_w']:.2f}/W** — replace with an actual EPC quote before commercial use.")

with tab_physics:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Mean POA", f"{weather['poa_w_m2'].mean():.1f} W/m²")
    c2.metric("P95 POA", f"{weather['poa_w_m2'].quantile(.95):.1f} W/m²")
    c3.metric("Mean Tcell", f"{weather['temp_cell_c'].mean():.1f} °C")
    c4.metric("P95 Tcell", f"{weather['temp_cell_c'].quantile(.95):.1f} °C")
    c5.metric("Mean wind", f"{weather['wind_speed_m_s'].mean():.1f} m/s")
    direct_source = (
        "NASA POWER hourly"
        if (weather["dni_source"] == "NASA POWER hourly").all()
        else "NASA hourly GHI + pvlib Erbs fallback for missing DNI/DHI"
    )
    st.info(f"DNI/DHI path: {direct_source}. Solar position, POA and Sandia cell temperature are calculated with pvlib.")
    st.dataframe(weather.head(1500), width="stretch", hide_index=True)

with tab_pvgis:
    nasa_poa_kwh_m2 = float(pd.to_numeric(weather["poa_w_m2"], errors="coerce").fillna(0).sum() / 1000.0)
    if not use_pvgis:
        st.info("Enable ‘Run PVGIS cross-check’ and rerun to compare independent hourly in-plane irradiation.")
    elif pvgis_df is None:
        st.warning(f"PVGIS cross-check was unavailable for this request. {pvgis_error or ''}")
    else:
        pvgis_poa_kwh_m2 = float(pd.to_numeric(pvgis_df["poa_w_m2"], errors="coerce").fillna(0).sum() / 1000.0)
        delta_pct = 100.0 * (pvgis_poa_kwh_m2 - nasa_poa_kwh_m2) / max(nasa_poa_kwh_m2, 1e-9)
        abs_delta = abs(delta_pct)
        if abs_delta <= 10:
            check_label = "Close cross-check — continue, but do not treat as calibration."
        elif abs_delta <= 20:
            check_label = "Material difference — review assumptions/data before presenting the result."
        else:
            check_label = "Large difference — treat the screening result as needing investigation before use."
        c1, c2, c3 = st.columns(3)
        c1.metric("NASA→pvlib POA", f"{nasa_poa_kwh_m2:.0f} kWh/m²")
        c2.metric("PVGIS in-plane", f"{pvgis_poa_kwh_m2:.0f} kWh/m²")
        c3.metric("PVGIS vs NASA/pvlib", f"{delta_pct:+.1f}%")
        st.info(check_label)
        st.caption("This is an independent irradiation source cross-check, not automatic calibration or field validation.")
        st.dataframe(pvgis_df.head(1500), width="stretch", hide_index=True)

with tab_forecast:
    leading_candidate = decision["winner"]
    tech_row = all_tech[all_tech["technology_name"] == leading_candidate["technology_name"]].iloc[0]
    forecast = forecast_25_years(
        site,
        tech_row,
        degradation_pct_year=leading_candidate["adjusted_degradation_pct_year"],
        weather=weather,
    )
    st.line_chart(forecast.set_index("year")[["annual_yield_kwh", "retained_performance_pct"]])
    c1, c2, c3 = st.columns(3)
    c1.metric("Year-1 yield", f"{forecast.iloc[0]['annual_yield_kwh']:,.0f} kWh")
    c2.metric("Year-25 retained", f"{forecast.iloc[-1]['retained_performance_pct']:.1f}%")
    c3.metric("25-year cumulative", f"{forecast.iloc[-1]['cumulative_yield_kwh']:,.0f} kWh")
    st.warning("The 25-year result uses the existing Solaryn database baseline degradation as a scenario. Arrhenius/Peck remains a separate stress diagnostic and is not multiplied into the field degradation rate.")
    payload = build_explanation_payload(site, objective, leading_candidate, ranking, forecast, decision_summary=decision)
    st.markdown("### Research hypothesis explanation")
    st.markdown(local_copilot_explanation(payload))

with tab_model:
    st.markdown(
        """
### Current physics chain

**Hourly environment → optics → effective irradiance → temperature → electrical response → energy → reliability evidence → lifetime → decision gate**

1. **Resource:** NASA POWER hourly GHI/DNI/DHI, temperature, humidity, wind and precipitation; PVGIS remains an independent irradiation cross-check.
2. **Solar geometry / POA:** pvlib solar position + Perez-Driesse transposition. Direct, sky-diffuse and ground-diffuse irradiance are kept separate.
3. **IAM optics:** component-wise incidence-angle correction is applied once. The current engine explicitly prevents the previous double-IAM path.
4. **Bifacial:** rear contribution is permitted only when `poa_rear_w_m2` and a candidate bifaciality factor are supplied. No fixed generic rear-gain percentage exists.
5. **Spectrum:** atmospheric spectral mismatch uses air mass + precipitable-water models where supported; technology-class spectral proxies are identified as proxies, not measurements.
6. **Soiling:** common fixed project loss or a rain-reset/dry-deposition time series. Technology differentiation requires explicit susceptibility evidence.
7. **Snow / shading:** only externally supplied hourly transmission factors are applied. Missing evidence means neutral factor 1.0.
8. **Temperature evidence hierarchy:** measured module/cell temperature → module-specific Faiman U0/U1 → upstream modeled temperature → common Sandia fallback. Modeled temperatures are never relabeled as measured.
9. **Electrical evidence hierarchy:** module-specific measured IEC 61853 Pmax(G,T) matrix → explicit PVWatts temperature-coefficient fallback for technology screening. Commercial EPC mode retains its stricter module-specific CEC/IEC policy.
10. **Reliability:** hot-cell hours, damp-heat exposure, thermal cycling, UV proxy and salinity are reported as exposure diagnostics. They do not become annual degradation rates without calibrated field evidence.
11. **Lifetime degradation:** candidate-specific field-validated degradation may be used; otherwise all candidates use the same project degradation scenario so uncalibrated climate heuristics cannot manufacture a winner.
12. **Decision:** a numerical leader is separated from a decision-eligible recommendation. Cross-technology recommendations require comparable measured electrical evidence.

### Equations and evidence

See the system uncertainty and validation documentation and the physics-equation documentation for equations, evidence levels and known limitations.

### Deliberate limitations

- **Not investment-grade:** no lender-grade P50/P90 uncertainty propagation yet.
- **No hidden calibration to historical winners:** field benchmarks are validation targets, never ranking bonuses.
- **Spectral class models are not substitutes for module EQE + measured spectra.**
- **Dynamic soiling is not decision-grade until deposition/cleaning parameters are calibrated to the site.**
- **Reliability exposure is not a degradation-rate prediction unless long-term field evidence exists.**
- **Shading, snow and bifacial effects require explicit project data.**
- Material/device diagnostics remain research context unless a validated bridge to module performance is available.
        """
    )
    st.json({
        "model_revision": "current",
        "coordinates": {"latitude": lat, "longitude": lon},
        "analysis_period": {"start": str(start), "end": str(end), "days": analysis_days},
        "system_size_mw": system_size,
        "site_type": site_type,
        "budget": budget,
        "decision_objective": objective,
        "candidate_scope": candidate_scope,
        "active_candidate_count": len(candidate_tech),
        "primary_climate_source": "NASA POWER hourly",
        "physics_engine": "hourly POA -> single-pass component IAM -> optional rear bifacial -> spectral -> soiling/shading/snow -> evidence-ordered temperature -> IEC 61853 Pmax(G,T) preferred -> explicit fallback -> reliability exposure -> evidence-gated decision",
        "pvgis_crosscheck": bool(use_pvgis),
    })
