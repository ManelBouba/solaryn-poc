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
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.recommendation_engine import (
    decision_leaders,
    filter_candidate_universe,
    project_decision_summary,
    rank_technologies,
)
from app.epc_module_mode import render_epc_module_mode

st.set_page_config(
    page_title="SOLARYN | Solar intelligence",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)
st.logo(str(LOGO_PATH), size="large")


def _navigate(destination: str) -> None:
    st.session_state.app_destination = destination


st.session_state.setdefault("app_destination", "Projects")

with st.sidebar:
    st.image(str(LOGO_PATH), width="stretch")
    st.space("small")
    st.caption("NAVIGATION")
    nav_items = [
        ("Projects", ":material/folder:"),
        ("New Project", ":material/add_circle:"),
        ("Technology & Materials", ":material/science:"),
        ("Reports", ":material/description:"),
        ("Organization", ":material/domain:"),
        ("Help", ":material/help:"),
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
    st.space("medium")
    st.caption("CURRENT PROJECT")
    st.button(
        "Riyadh module comparison",
        icon=":material/solar_power:",
        key="nav_current_project",
        type="primary" if st.session_state.app_destination == "EPC Module Comparison" else "secondary",
        width="stretch",
        on_click=_navigate,
        args=("EPC Module Comparison",),
    )
    st.caption("Draft · session workspace")

destination = st.session_state.app_destination

if destination == "EPC Module Comparison":
    render_epc_module_mode(ROOT)
    st.stop()

if destination == "Projects":
    st.caption("PROJECT PORTFOLIO")
    st.title("Projects")
    st.write("Open an engineering comparison or start a new project workspace.")
    with st.container(border=True):
        h1, h2 = st.columns([3, 1], vertical_alignment="center")
        with h1:
            st.subheader("Riyadh module comparison")
            st.caption("Utility PV · Riyadh, Saudi Arabia · 3 candidate modules")
            with st.container(horizontal=True):
                st.badge("Draft", color="gray", icon=":material/edit:")
                st.badge("Inputs ready", color="green", icon=":material/check_circle:")
                st.badge("Review pending", color="orange", icon=":material/pending:")
        h2.button(
            "Open project", icon=":material/arrow_forward:", type="primary", width="stretch",
            on_click=_navigate, args=("EPC Module Comparison",), key="open_riyadh_project",
        )
    st.info(
        "This PoC provides a session workspace. Persistent multi-project storage and historical run management are not implemented yet.",
        icon=":material/info:",
    )
    st.stop()

if destination == "New Project":
    st.caption("PROJECT SETUP")
    st.title("Create a project")
    st.write("Define the project context before adding sites, module candidates, and supplier offers.")
    with st.form("new_project_form"):
        c1, c2 = st.columns(2)
        project_name = c1.text_input("Project name", placeholder="e.g. Riyadh utility PV")
        project_type = c2.selectbox("Project type", ["Utility", "Commercial", "Residential", "Research"])
        st.text_area("Project description", placeholder="Optional scope, owner, and procurement context")
        submitted = st.form_submit_button("Continue to module comparison", type="primary", icon=":material/arrow_forward:")
    if submitted:
        st.session_state.app_destination = "EPC Module Comparison"
        st.rerun()
    st.caption("Project persistence, organization ownership, and permissions remain planned platform capabilities.")
    st.stop()

if destination == "Reports":
    st.caption("DECISION RECORDS")
    st.title("Reports")
    st.write("Download locally generated analysis artifacts. Approval workflow and versioned cloud storage are not enabled in this PoC.")
    report_files = [
        ("EPC validation report", ROOT / "outputs" / "solaryn_epc_validation_report.html", "text/html"),
        ("Module comparison data", ROOT / "outputs" / "solaryn_epc_comparison.csv", "text/csv"),
    ]
    available = False
    for label, path, mime in report_files:
        if path.exists():
            available = True
            with st.container(border=True):
                st.subheader(label)
                st.caption(f"Local artifact · {path.name}")
                st.download_button("Download", path.read_bytes(), path.name, mime=mime, icon=":material/download:")
    if not available:
        st.info("No downloadable project reports are available yet. Run an EPC Module Comparison first.", icon=":material/inbox:")
    st.stop()

if destination == "Organization":
    st.caption("WORKSPACE ADMINISTRATION")
    st.title("Organization")
    st.warning("Organization accounts and role-based access are not enabled in this PoC.", icon=":material/lock:")
    st.write("Planned roles: Organization Admin, Analyst, Reviewer, Approver, and Viewer.")
    st.write("Production architecture must add organization isolation, audit history, MFA, controlled exports, and retention policies before confidential project use.")
    st.stop()

if destination == "Help":
    st.caption("PRODUCT GUIDANCE")
    st.title("Help and methodology")
    st.subheader("Two connected workspaces")
    st.write("**EPC Module Comparison** evaluates exact commercial modules and supplier offers using the evidence-controlled comparison path.")
    st.write("**Technology & Material Screening** generates research hypotheses from the broader scientific knowledge base.")
    st.subheader("Validation boundary")
    st.warning("Research hypotheses cannot be approved as procurement decisions or override module-level commercial evidence.")
    st.write("Climate, c-Si off-STC, cross-technology, IEC measured, economics, and historical EPC validation remain pending. Bankability is not claimed.")
    st.stop()

st.warning(
    "Technology & Material Screening preserves SOLARYN's scientific knowledge base, but its current literature-range parameters and weighted scores are heuristic. "
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

st.caption("EXPERT RESEARCH WORKSPACE")
st.title("Technology & Material Screening")
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
            ["Commercial deployment (PoC)", "Commercial + niche", "R&D exploration"],
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
    st.caption("Default PoC scope excludes research/pilot candidates and bifacial variants. Rear-side bifacial gain is not yet modelled.")

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
    st.write("3. Use pvlib for solar position, POA and cell temperature.")
    st.write("4. Compare only the appropriate candidate universe.")
    st.write("5. Present leading research hypotheses with reasons, trade-offs, and explicit model separation.")
    st.write("6. Cross-check irradiation with PVGIS when enabled.")

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

with st.spinner("Downloading hourly climate and running Technology & Material Screening..."):
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
            check_label = "Large difference — treat the PoC result as needing investigation before use."
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
### Database use policy

- **Kept:** all 30 technology records, material physics, layer stack, defects/contacts, costs and evidence files.
- **Commercial energy drivers:** hourly POA, cell temperature, database Pmax temperature coefficient, supported pvlib technology-class spectral correction, common site soiling.
- **Lifetime:** database degradation is a scenario, not a climate-calibrated prediction.
- **Diagnostics only:** mobility, defect density, absorber thickness, physics-quality score, resilience scores, and generic confidence values cannot determine a commercial decision.

### Current screening controls

- A **commercial procurement universe** is separated from research exploration.
- The user explicitly defines what **best** means through the project objective.
- The model presents **leading research hypotheses**, not a procurement recommendation.
- The screening exposes **reasons, trade-offs and score separation**; it does not claim scientific confidence.
- Hourly climate and pvlib remain the physical baseline.
- PVGIS remains an independent irradiation cross-check.
- A full reference year is required so annual/lifetime outputs are not distorted by short analysis periods.

### Deliberate limitations

- It is **not bankability-grade** and has no field-validation accuracy claim yet.
- Technology/material data provenance is not yet complete.
- Degradation activation energies and humidity parameters are PoC proxies requiring evidence and calibration.
- Bifacial rear-side irradiance/gain is not yet modelled, so bifacial variants are excluded from the default commercial ranking.
- Technology & Material Screening remains heuristic and cannot issue a commercial decision. EPC Module Comparison uses module-specific IEC 61853 G-T evidence when available; c-Si may fall back to a datasheet-fitted CEC single-diode model under an uncertainty guardrail; non-c-Si candidates without validated model evidence are decision-ineligible.
- Material/device architecture is not yet the primary decision layer.
- P50/P90 uncertainty propagation is not yet implemented.

### Next scientific build after this validation PoC

Validate the technology dataset and degradation assumptions, benchmark the hourly yield chain, then add architecture/material-specific physics only where it improves a real project decision.
        """
    )
    st.json({
        "model_version": "V9.2.1",
        "coordinates": {"latitude": lat, "longitude": lon},
        "analysis_period": {"start": str(start), "end": str(end), "days": analysis_days},
        "system_size_mw": system_size,
        "site_type": site_type,
        "budget": budget,
        "decision_objective": objective,
        "candidate_scope": candidate_scope,
        "active_candidate_count": len(candidate_tech),
        "primary_climate_source": "NASA POWER hourly",
        "physics_engine": "research screening: heuristic/diagnostic only; EPC mode: module-specific IEC 61853 matrix preferred, c-Si CEC fallback, non-c-Si fails closed without validated evidence",
        "pvgis_crosscheck": bool(use_pvgis),
    })
