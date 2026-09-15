from __future__ import annotations

from datetime import date
from pathlib import Path
import io
import re
import unicodedata
import zipfile

import requests

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.data_fetchers import (
    fetch_nasa_power_hourly_dataframe,
    fetch_pvgis_hourly_dataframe,
    nasa_hourly_to_site_summary,
    pvlib_azimuth_to_pvgis_aspect,
)
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.module_iv_engine import simulate_module_hourly, validate_module_candidates
from src.module_offer_io import load_module_offer_csv, module_offer_readiness
from src.lifetime_engine import add_lifetime_metrics
from src.degradation_stress import compute_stress_exposures
from src.economics_engine import switching_point_table
from src.epc_decision import recommendation_decision
from src.evidence_policy import project_segment_compatible, DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT
from src.epc_report import build_epc_html_report


@st.cache_data(show_spinner=False)
def _load_seed_modules(root_str: str) -> pd.DataFrame:
    return pd.read_csv(Path(root_str) / "data/raw/module_candidate_master.csv")


@st.cache_data(show_spinner=True)
def _nasa_hourly(lat: float, lon: float, start: str, end: str):
    return fetch_nasa_power_hourly_dataframe(lat, lon, start, end)


@st.cache_data(show_spinner=True)
def _pvgis_hourly(lat: float, lon: float, startyear: int, endyear: int, angle: float, aspect: float):
    return fetch_pvgis_hourly_dataframe(
        lat, lon, startyear=startyear, endyear=endyear, angle=angle, aspect=aspect
    )


@st.cache_data(show_spinner=False, ttl=86400)
def _geocode_city(query: str) -> dict:
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1},
        headers={"User-Agent": "Solaryn-PV-Decision-Intelligence/1.0"},
        timeout=12,
    )
    response.raise_for_status()
    rows = response.json()
    if not rows:
        raise ValueError(f"No location found for '{query}'.")
    row = rows[0]
    address = row.get("address", {}) or {}
    city = next(
        (address.get(k) for k in ("city", "town", "village", "municipality", "county", "state") if address.get(k)),
        query,
    )
    return {
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "city": str(city),
        "display_name": str(row.get("display_name", city)),
    }


@st.cache_data(show_spinner=False, ttl=86400)
def _reverse_city(lat: float, lon: float) -> dict:
    response = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "addressdetails": 1},
        headers={"User-Agent": "Solaryn-PV-Decision-Intelligence/1.0"},
        timeout=12,
    )
    response.raise_for_status()
    row = response.json()
    address = row.get("address", {}) or {}
    city = next(
        (address.get(k) for k in ("city", "town", "village", "municipality", "county", "state") if address.get(k)),
        None,
    )
    return {
        "city": str(city or ""),
        "display_name": str(row.get("display_name", city or "")),
    }


def _safe_slug(value: str, fallback: str = "Project") -> str:
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_")
    return slug or fallback


def _template_bytes(root: Path) -> bytes:
    return (root / "data/raw/epc_module_offer_template.csv").read_bytes()


def render_epc_module_mode(root: Path) -> None:
    st.caption("SOLAR PROCUREMENT / MODULE COMPARISON")
    st.title("Compare modules. Understand the trade-offs.")
    st.write("Evaluate real module offers against the same site, climate, and project assumptions.")
    highlights = st.columns(3, gap="medium")
    with highlights[0].container(border=True):
        st.badge("PROJECT SPECIFIC", color="blue", icon=":material/location_on:")
        st.subheader("Model the real site")
        st.caption("One climate, geometry, and loss basis for every offer.")
    with highlights[1].container(border=True):
        st.badge("EVIDENCE LED", color="green", icon=":material/fact_check:")
        st.subheader("Compare like for like")
        st.caption("Module-level evidence, transparent fallbacks, explicit flags.")
    with highlights[2].container(border=True):
        st.badge("DECISION READY", color="yellow", icon=":material/insights:")
        st.subheader("See the trade-off")
        st.caption("Energy lead, lifetime scenario, and price switching point.")
    st.caption("PROJECT WORKFLOW")
    st.markdown(
        ":green-badge[1 Overview] :green-badge[2 Site & climate] :blue-badge[3 Objectives] "
        ":blue-badge[4 Candidates] :orange-badge[5 Supplier offers] :gray-badge[6 Analysis] "
        ":gray-badge[7 Comparison] :gray-badge[8 Decision] :gray-badge[9 Report]"
    )
    st.caption("Decision confidence is evidence-aware: Solaryn can return Robust, Probable, Conditional, or No decision.")
    with st.expander("How to use this workspace", icon=":material/help:"):
        st.write("1. Configure your project and select its location.\n2. Choose comparable module offers and add actual quotes if available.\n3. Run the physics comparison, review evidence flags, and export the report.")
        st.write("At least two successfully simulated candidates are required. Solaryn separates the technical leader from the final recommendation and shows the next evidence request when the decision remains conditional.")

    st.session_state.setdefault("selected_lat", 20.0)
    st.session_state.setdefault("selected_lon", 0.0)
    st.session_state.setdefault("location_configured", False)
    st.session_state.setdefault("resolved_city", "")
    st.session_state.setdefault("resolved_location_name", "")

    st.subheader("01  Project setup")
    st.caption("Shared assumptions apply to every selected candidate.")
    with st.container(border=True):
        geometry_tab, economics_tab, policy_tab = st.tabs(["Project & geometry", "Economics", "Validation & sensitivities"])
        with geometry_tab:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                reference_year = int(st.number_input("Latest resource year", min_value=2005, max_value=2023, value=2020, step=1))
            with c2:
                resource_years = int(st.selectbox("Resource history", [1, 3, 5], index=1, format_func=lambda x: f"{x} year" if x == 1 else f"{x} years", help="Multi-year resource is preferred because interannual variability belongs in the uncertainty model."))
            with c3:
                system_size_mw = st.number_input("Project DC size (MWp)", min_value=0.1, max_value=5000.0, value=100.0, step=1.0)
            with c4:
                tilt_deg = st.number_input("Fixed tilt (°)", min_value=0.0, max_value=60.0, value=25.0, step=1.0)

            g0, g1, g2, g3, g4 = st.columns(5)
            with g0:
                model_row_geometry = st.toggle("Row + rear irradiance", value=True, help="Uses pvlib infinite-sheds geometry for common row shading and rear irradiance. Disable only when this geometry is not applicable.")
            with g1:
                albedo = st.number_input("Albedo", min_value=0.0, max_value=1.0, value=0.20, step=0.05)
            with g2:
                gcr = st.number_input("GCR", min_value=0.05, max_value=0.95, value=0.40, step=0.05, help="Ground coverage ratio = row slant length / row pitch.")
            with g3:
                row_height_m = st.number_input("Row center height (m)", min_value=0.1, max_value=20.0, value=1.5, step=0.1)
            with g4:
                row_pitch_m = st.number_input("Row pitch (m)", min_value=0.2, max_value=50.0, value=5.0, step=0.2)
            rear_structure_loss_pct = st.number_input(
                "Rear structural / non-uniformity screening loss (%)", min_value=0.0, max_value=20.0, value=2.0, step=0.5,
                help="Declared project assumption applied only to rear irradiance after geometry. Replace with measured/rear-mismatch evidence for procurement-grade work."
            )
            geometry_evidence_label = st.selectbox(
                "Geometry evidence",
                ["Screening assumptions", "Project design inputs", "Measured / as-built geometry & albedo"],
                help=(
                    "This controls recommendation claim strength, never modeled mean energy. "
                    "Project-design inputs can support a strong monofacial comparison; decision-material bifacial rear gain "
                    "requires measured/as-built geometry and albedo before Robust wording is allowed."
                ),
            )
            if geometry_evidence_label.startswith("Measured"):
                geometry_confidence = "measured"
            elif geometry_evidence_label.startswith("Project"):
                geometry_confidence = "project_design"
            else:
                geometry_confidence = "screening_assumptions"
            soiling_loss_pct = st.number_input(
                "Common soiling loss (%)", min_value=0.0, max_value=30.0, value=2.0, step=0.25,
                help="Shared project assumption. Technology-specific soiling resilience scores from the research database do not enter EPC ranking."
            )

        with economics_tab:
            e1, e2, e3, e4 = st.columns(4)
            with e1:
                energy_value = st.number_input("Energy value / PPA ($/kWh)", min_value=0.0, max_value=1.0, value=0.05, step=0.005, format="%.3f")
            with e2:
                discount_rate = st.number_input("Discount rate (%)", min_value=0.0, max_value=30.0, value=7.0, step=0.5)
            with e3:
                area_bos_cost = st.number_input(
                    "Area-sensitive BOS ($/m²)", min_value=0.0, max_value=500.0, value=0.0, step=1.0,
                    help="Only land/racking/area-sensitive cost. This is not total BOS or LCOE."
                )
            with e4:
                use_pvgis = st.toggle("PVGIS POA cross-check", value=True)
            st.selectbox(
                "Quote currency", ["USD"], disabled=True,
                help="This workspace uses USD/W for supplier quotes so every offer is compared on one currency basis.",
            )

        with policy_tab:
            min_sep = st.number_input(
                "Decision separation policy (%)", min_value=0.0, max_value=10.0, value=1.0, step=0.25,
                help="Configurable decision-policy threshold. It is a governance setting, not a scientific confidence interval."
            )

        with policy_tab:
            g1, g2, g3 = st.columns(3)
            with g1:
                common_degradation = st.number_input(
                    "Common degradation sensitivity (%/year)", min_value=0.0, max_value=3.0, value=0.50, step=0.05,
                    help="Applied identically to all candidates. Manufacturer warranty slopes are shown separately as sensitivity only."
                )
            with g2:
                uncertainty_guardrail = st.number_input(
                    "Energy-rating uncertainty guardrail (%)", min_value=0.0, max_value=10.0,
                    value=float(DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT), step=0.25,
                    help="Secondary deterministic policy threshold; uncertainty is also reported through P(best) and expected regret."
                )
            with g3:
                project_segment = st.selectbox(
                    "Project segment", ["utility", "commercial", "residential", "research"], index=0,
                    help="Prevents apples-to-oranges comparisons. Research mode disables segment filtering but also weakens commercial claims."
                )

    st.subheader("02  Project location")
    st.caption("Search a city, click the map, or enter coordinates. Solaryn uses the resolved city/project label in every exported project file.")

    city_col, search_col = st.columns([4, 1], vertical_alignment="bottom")
    city_query = city_col.text_input(
        "City / project location",
        placeholder="e.g. Brussels, Algiers, Dubai, Singapore",
        key="city_search_query",
        help="Use a city name for the fastest demo flow. You can still select an exact coordinate afterward.",
    )
    if search_col.button("Find city", icon=":material/search:", width="stretch"):
        if not city_query.strip():
            st.warning("Enter a city or project location first.")
        else:
            try:
                geo = _geocode_city(city_query.strip())
                st.session_state.selected_lat = geo["lat"]
                st.session_state.selected_lon = geo["lon"]
                st.session_state.location_configured = True
                st.session_state.resolved_city = geo["city"]
                st.session_state.resolved_location_name = geo["display_name"]
                st.rerun()
            except Exception as exc:
                st.error(f"City search could not be completed: {exc}")

    def _apply_manual_location() -> None:
        st.session_state.selected_lat = float(st.session_state.manual_latitude)
        st.session_state.selected_lon = float(st.session_state.manual_longitude)
        st.session_state.location_configured = True

    coordinate_inputs = st.columns(2)
    coordinate_inputs[0].number_input(
        "Enter latitude", min_value=-90.0, max_value=90.0, step=0.0001,
        value=float(st.session_state.selected_lat), format="%.5f", key="manual_latitude",
    )
    coordinate_inputs[1].number_input(
        "Enter longitude", min_value=-180.0, max_value=180.0, step=0.0001,
        value=float(st.session_state.selected_lon), format="%.5f", key="manual_longitude",
    )
    st.button("Apply coordinates", icon=":material/my_location:", on_click=_apply_manual_location)
    lat = float(st.session_state.selected_lat)
    lon = float(st.session_state.selected_lon)
    azimuth_deg = 180.0 if lat >= 0 else 0.0

    map_col, info_col = st.columns([2.1, 1])
    with map_col:
        zoom = 5 if st.session_state.location_configured else 2
        m = folium.Map([lat, lon], zoom_start=zoom, tiles="OpenStreetMap", control_scale=True)
        if st.session_state.location_configured:
            folium.Marker([lat, lon], tooltip="Selected project location").add_to(m)
        folium.LatLngPopup().add_to(m)
        res = st_folium(m, height=320, returned_objects=["last_clicked"], width=None)
        if res and res.get("last_clicked"):
            new_lat = float(res["last_clicked"]["lat"])
            new_lon = float(res["last_clicked"]["lng"])
            if (not st.session_state.location_configured) or abs(new_lat-lat)>1e-7 or abs(new_lon-lon)>1e-7:
                st.session_state.selected_lat = new_lat
                st.session_state.selected_lon = new_lon
                st.session_state.location_configured = True
                lat, lon = new_lat, new_lon
                azimuth_deg = 180.0 if lat >= 0 else 0.0

    if st.session_state.location_configured:
        try:
            reverse = _reverse_city(lat, lon)
            if reverse.get("city"):
                st.session_state.resolved_city = reverse["city"]
            if reverse.get("display_name"):
                st.session_state.resolved_location_name = reverse["display_name"]
        except Exception:
            pass

    project_label = (city_query.strip() or st.session_state.resolved_city.strip()) if st.session_state.location_configured else ""
    if not project_label and st.session_state.location_configured:
        project_label = f"Site {lat:.2f}, {lon:.2f}"

    with info_col:
        if st.session_state.location_configured:
            st.badge(project_label, icon=":material/location_on:", color="blue")
            st.caption(st.session_state.resolved_location_name or f"{lat:.5f}, {lon:.5f}")
        else:
            st.badge("Select a project location", icon=":material/location_on:", color="gray")
        st.subheader("Site configuration")
        st.write(f"• Project segment: {project_segment}")
        st.write("• Fixed tilt")
        st.write("• Monofacial")
        if st.session_state.location_configured:
            st.write(f"• Equator-facing azimuth: {azimuth_deg:.0f}°")
        st.caption("This comparison uses fixed-tilt front-side DC physics. Add tracker, rear-irradiance, terrain/shading and inverter design inputs when they are decision-critical.")

    st.subheader("03  Module shortlist")
    st.caption("Compare like-for-like offers. Only quote cells are editable; technical evidence stays unchanged.")
    seed = _load_seed_modules(str(root))

    # Keep recovery tools visible even when an uploaded CSV is invalid. The blank
    # template is intentionally headers-only; the populated example is immediately
    # runnable and demonstrates the expected row structure without inventing prices.
    with st.expander("Import offers & download templates", icon=":material/upload_file:"):
        templates = st.container()
    d1, d2 = templates.columns(2)
    with d1:
        st.download_button(
            "Download blank EPC template",
            data=_template_bytes(root),
            file_name="solaryn_epc_module_offer_template.csv",
            mime="text/csv",
            width="stretch",
        )
    with d2:
        example = seed[seed.apply(lambda r: project_segment_compatible(r, "utility"), axis=1)].copy()
        st.download_button(
            "Download populated 3-module example",
            data=example.to_csv(index=False).encode("utf-8"),
            file_name="solaryn_epc_module_offer_example_3modules.csv",
            mime="text/csv",
            width="stretch",
        )
    templates.caption(
        "The blank template contains headers only and will not run until module rows are added. "
        "The populated example uses the packaged manufacturer-datasheet seed records; supplier quotes remain blank."
    )

    uploaded = templates.file_uploader("Upload EPC module-offer CSV (optional)", type=["csv"])
    if uploaded is not None:
        try:
            candidates = load_module_offer_csv(uploaded)
            st.success(f"Loaded {len(candidates)} EPC module candidates.")
        except Exception as exc:
            st.error(f"Module-offer CSV is not usable: {exc}")
            st.stop()
    else:
        candidates = load_module_offer_csv(root / "data/raw/module_candidate_master.csv")
        st.caption("Using manufacturer-datasheet seed records. Their prices are intentionally blank and their model-evidence limitations are explicit.")

    if project_segment != "research":
        mask = candidates.apply(lambda r: project_segment_compatible(r, project_segment), axis=1)
        excluded = candidates.loc[~mask, ["manufacturer", "model"]]
        candidates = candidates.loc[mask].reset_index(drop=True)
        if not excluded.empty:
            st.caption("Excluded as incompatible with the selected project segment: " + "; ".join(excluded["manufacturer"].astype(str)+" "+excluded["model"].astype(str)))
    if len(candidates) < 2:
        st.error("Fewer than two segment-compatible candidates remain. Upload comparable offers or use research mode explicitly.")
        st.stop()

    labels = dict(zip(candidates["module_id"], candidates["manufacturer"].astype(str) + " · " + candidates["model"].astype(str)))
    selected_ids = st.multiselect(
        "Modules to compare",
        options=list(labels.keys()),
        default=list(labels.keys()),
        format_func=lambda x: labels[x],
    )
    if len(selected_ids) < 2:
        st.warning("Select at least two module candidates for an EPC comparison.")
        st.stop()

    selected = candidates[candidates["module_id"].isin(selected_ids)].copy().reset_index(drop=True)
    quote_view = selected.reindex(columns=["module_id", "manufacturer", "model", "technology_label", "quote_usd_w"]).copy()
    quote_view["quote_usd_w"] = pd.to_numeric(quote_view["quote_usd_w"], errors="coerce")
    quote_view = st.data_editor(
        quote_view,
        hide_index=True,
        disabled=["module_id", "manufacturer", "model", "technology_label"],
        column_config={
            "module_id": st.column_config.TextColumn("Candidate ID", width="small"),
            "manufacturer": "Manufacturer",
            "model": st.column_config.TextColumn("Module", width="medium"),
            "technology_label": "Technology",
            "quote_usd_w": st.column_config.NumberColumn(
                "Actual quote ($/W)", min_value=0.0, max_value=5.0, step=0.001, format="$%.3f"
            )
        },
        width="stretch",
        key="epc_quotes_editor_" + "__".join(map(str, selected_ids)),
    )
    quote_map = quote_view.set_index("module_id")["quote_usd_w"].to_dict()
    selected["quote_usd_w"] = selected["module_id"].map(quote_map)

    show_cols = [
        "manufacturer", "model", "technology_label", "pmax_w", "vmp_v", "imp_a",
        "voc_v", "isc_a", "gamma_pmax_pct_c", "module_efficiency_pct",
        "first_year_retention_pct", "annual_warranty_degradation_pct_year",
        "bifaciality_factor", "bifaciality_tolerance_pct_points",
        "evidence_status", "project_segment", "spectral_evidence_level", "iec61853_matrix_file",
    ]
    with st.expander("Technical specifications", icon=":material/table_chart:"):
        st.dataframe(selected.reindex(columns=show_cols), hide_index=True, width="stretch")

    readiness = module_offer_readiness(selected, root)
    with st.expander("Candidate evidence & readiness", expanded=True, icon=":material/fact_check:"):
        st.dataframe(readiness, hide_index=True, width="stretch")
    quote_count = int(readiness["supplier_quote_ready"].sum())
    if quote_count == 0:
        st.warning(
            "Energy comparison is ready. Add a real baseline supplier quote to calculate the maximum justified price premium.",
            icon=":material/request_quote:",
        )
        st.caption("You can continue without prices; switching economics will remain unavailable.")

    baseline_id = st.selectbox(
        "Economic switching baseline",
        options=list(selected["module_id"]),
        format_func=lambda x: labels.get(x, x),
        help="A switching threshold can only be calculated after the baseline has a real $/W quote.",
    )

    if st.session_state.location_configured:
        st.caption(f"Ready to compare {len(selected)} candidates · {project_label} · {reference_year-resource_years+1}–{reference_year} resource · {system_size_mw:g} MWp · {quote_count} supplier quotes")
    else:
        st.caption("Select a city, map point, or coordinate before running the comparison.")
    run = st.button(
        "Run EPC physics comparison",
        type="primary",
        width="stretch",
        icon=":material/play_arrow:",
        disabled=not st.session_state.location_configured,
    )
    if not run:
        st.stop()

    resource_start_year = int(reference_year - resource_years + 1)
    if resource_start_year < 2001:
        st.error("Selected resource history starts before NASA POWER hourly coverage used by this workflow. Choose a later latest year or fewer resource years.")
        st.stop()
    start = f"{resource_start_year}-01-01"
    end = f"{reference_year}-12-31"
    try:
        with st.status("Preparing site climate", expanded=True) as climate_status:
            climate_status.write(f"Requesting {resource_years}-year NASA POWER hourly resource ({resource_start_year}–{reference_year})…")
            nasa = _nasa_hourly(lat, lon, start, end)
            climate_status.write("Calculating solar position, plane-of-array irradiance, and cell temperature…")
            site = nasa_hourly_to_site_summary(
                nasa, lat, lon, project_name=project_label,
                system_size_mw=system_size_mw, site_type=project_segment,
                require_full_year=True,
            ).iloc[0]
            weather = nasa_hourly_to_pvlib_weather(
                nasa, lat, lon, tilt_deg=tilt_deg, azimuth_deg=azimuth_deg, albedo=albedo
            )
            climate_status.update(label="Site climate ready", state="complete", expanded=False)
    except Exception as exc:
        error_text = str(exc)
        is_connection_error = any(
            marker in error_text
            for marker in ("ConnectionError", "NewConnectionError", "Max retries exceeded", "WinError 10013")
        )
        if is_connection_error:
            st.error(
                "Climate data could not be reached. Check the internet connection or network permissions, then run the comparison again.",
                icon=":material/cloud_off:",
            )
            st.caption("No calculation was completed and no fallback climate data was substituted.")
        else:
            st.error(
                "The climate and plane-of-array calculation could not be completed. Review the technical details below before retrying.",
                icon=":material/error:",
            )
        with st.expander("Technical details", icon=":material/code:"):
            st.code(error_text, language=None, wrap_lines=True)
        st.stop()

    summaries = []
    hourly_frames = []
    stress_rows = []
    failed = []
    progress = st.progress(0.0, text="Fitting module IV models...")
    for i, (_, row) in enumerate(selected.iterrows(), start=1):
        try:
            summary, hourly = simulate_module_hourly(
                weather, row, common_soiling_loss_pct=soiling_loss_pct, root=root,
                bifacial_config={
                    "enabled": model_row_geometry, "albedo": albedo, "gcr": gcr,
                    "height_m": row_height_m, "pitch_m": row_pitch_m,
                    "rear_structure_loss_pct": rear_structure_loss_pct,
            "geometry_confidence": geometry_confidence,
                },
            )
            summaries.append(summary)
            hourly_frames.append(hourly)
            stress = compute_stress_exposures(hourly)
            stress_rows.append({
                "module_id": row["module_id"],
                "manufacturer": row["manufacturer"],
                "model": row["model"],
                **stress,
            })
        except Exception as exc:
            failed.append(f"{row['manufacturer']} {row['model']}: {exc}")
        progress.progress(i/len(selected), text=f"Processed {i}/{len(selected)} candidates")
    progress.empty()

    if failed:
        if len(summaries) < 2:
            st.error(
                "Solaryn cannot compare modules because fewer than two candidates simulated successfully:\n\n- "
                + "\n- ".join(failed)
            )
            st.stop()
        st.info(
            "Non-blocking model diagnostic: these candidates were skipped because their IV simulation failed. "
            "The analysis continues with the successfully simulated candidates:\n\n- " + "\n- ".join(failed)
        )

    spectral_warnings = []
    for summary in summaries:
        invalid_pct = float(summary.get("spectral_proxy_invalid_daylight_fraction_pct", 0.0) or 0.0)
        if invalid_pct > 0:
            spectral_warnings.append(
                f"{summary['manufacturer']} {summary['model']}: {invalid_pct:.1f}% of daylight hours "
                "were outside the executable technology-class spectral proxy domain and were assigned "
                "a neutral factor of 1.0 for the spectral sensitivity only."
            )
    if spectral_warnings:
        with st.expander("Model diagnostics — spectral proxy coverage", expanded=False):
            st.write(
                "Broadband physics continued normally. The spectral proxy is sensitivity-only; unsupported hours "
                "were neutralized only inside that diagnostic sensitivity."
            )
            for item in spectral_warnings:
                st.write("• " + item)

    if len(summaries) < 2:
        st.error(
            "Module comparison requires at least two candidates with finite successful simulations. "
            "Review the candidate diagnostics above."
        )
        st.stop()

    results = add_lifetime_metrics(
        pd.DataFrame(summaries), selected, years=25, common_degradation_pct_year=common_degradation
    )
    # Project-scale DC energy is derived transparently from specific energy.
    # kWh/kWp × MWp is numerically MWh. No AC/inverter losses are implied.
    results["annual_project_dc_energy_mwh"] = (
        results["annual_dc_specific_energy_kwh_kwp"] * float(system_size_mw)
    )
    results["lifetime_project_dc_energy_mwh"] = (
        results["lifetime_energy_common_degradation_scenario_kwh_kwp"] * float(system_size_mw)
    )
    stress_df = pd.DataFrame(stress_rows)
    hourly_all = pd.concat(hourly_frames, ignore_index=True) if hourly_frames else pd.DataFrame()

    # Build empirical shared-resource years for the ranking uncertainty engine.
    # Each candidate sees the same sampled calendar year in each Monte Carlo draw.
    annual_scenarios = None
    if not hourly_all.empty and {"timestamp", "module_id", "specific_power_kw_per_kwp"}.issubset(hourly_all.columns):
        hs = hourly_all.copy()
        hs["timestamp"] = pd.to_datetime(hs["timestamp"], utc=True, errors="coerce")
        hs["year"] = hs["timestamp"].dt.year
        annual_scenarios = (
            hs.dropna(subset=["year", "specific_power_kw_per_kwp"])
              .groupby(["year", "module_id"], as_index=False)["specific_power_kw_per_kwp"].sum()
              .pivot(index="year", columns="module_id", values="specific_power_kw_per_kwp")
              .sort_index()
        )

    pvgis_note = "PVGIS cross-check disabled."
    pvgis_delta = np.nan
    resource_crosscheck_status = "not_checked"
    if use_pvgis:
        try:
            pvgis_aspect = pvlib_azimuth_to_pvgis_aspect(azimuth_deg)
            pv = _pvgis_hourly(lat, lon, resource_start_year, reference_year, tilt_deg, pvgis_aspect)
            nasa_weights = pd.to_numeric(weather.get("days_weight", 1.0), errors="coerce").fillna(1.0)
            nasa_poa = float((pd.to_numeric(weather["poa_w_m2"], errors="coerce").fillna(0) * nasa_weights).sum()/1000.0)
            pv_times = pd.to_datetime(pv["date"], errors="coerce")
            pv_annual = (pd.DataFrame({"year": pv_times.dt.year, "poa": pd.to_numeric(pv["poa_w_m2"], errors="coerce").fillna(0)})
                         .groupby("year")["poa"].sum()/1000.0)
            pvgis_poa = float(pv_annual.mean())
            pvgis_delta = 100.0 * (nasa_poa - pvgis_poa) / max(abs(pvgis_poa), 1e-9)
            pvgis_note = (
                f"Mean annual NASA→pvlib POA {nasa_poa:,.0f} kWh/m² vs PVGIS "
                f"{pvgis_poa:,.0f} kWh/m² over {resource_start_year}–{reference_year}; difference {pvgis_delta:+.1f}%."
            )
            resource_crosscheck_status = "ok"
        except Exception as exc:
            pvgis_note = f"PVGIS cross-check failed: {exc}"
            resource_crosscheck_status = "failed"

    decision = recommendation_decision(
        results,
        minimum_separation_pct=min_sep,
        uncertainty_guardrail_pct=uncertainty_guardrail,
        annual_scenarios=annual_scenarios,
        resource_disagreement_pct=(pvgis_delta if np.isfinite(pvgis_delta) else None),
        resource_crosscheck_status=resource_crosscheck_status,
        geometry_confidence=geometry_confidence,
    )

    switching = None
    try:
        switching = switching_point_table(
            results, selected, baseline_id,
            energy_value_usd_kwh=energy_value,
            discount_rate_pct=discount_rate,
            area_bos_usd_m2=area_bos_cost,
            years=25, common_degradation_pct_year=common_degradation,
            allow_screening_sensitivity=True,
        )
    except Exception as exc:
        switching_error = str(exc)
    else:
        switching_error = None

    st.subheader("04  Recommendation")
    status = str(decision.get("decision_status", "Conditional"))
    status_icon = {"Robust": ":material/verified:", "Probable": ":material/check_circle:", "Conditional": ":material/info:", "No decision": ":material/block:"}.get(status, ":material/info:")
    if status == "Robust":
        st.success("**" + decision["headline"] + "**", icon=status_icon)
    elif status == "Probable":
        st.info("**" + decision["headline"] + "**", icon=status_icon)
    else:
        st.warning("**" + decision["headline"] + "**", icon=status_icon)

    technical = results.set_index("module_id").loc[decision["technical_leader_module_id"]]
    lifetime_leader = results.sort_values("lifetime_energy_common_degradation_scenario_kwh_kwp", ascending=False).iloc[0]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Technical leader", str(technical.get("technology_label", "—")), border=True)
    k1.caption(f"{technical['manufacturer']} {technical['model']}")
    k2.metric("Annual yield", f"{technical['annual_yield_kwh_kwp']:,.1f} kWh/kWp", border=True)
    k2.caption(f"+{decision.get('decision_frontier_lead_over_second_pct', decision['annual_lead_over_second_pct']):.2f}% vs #2 decision-eligible")
    k3.metric("P(best)", f"{decision['probability_of_best_pct']:.1f}%", border=True)
    k3.caption("Shared-resource correlated uncertainty")
    k4.metric("Expected regret", f"{decision['expected_regret_pct']:.2f}%", border=True)
    k4.caption("Decision-frontier expected opportunity loss")
    k5.metric("Resource confidence", str(decision.get("resource_confidence", "Not checked")), border=True)
    k5.caption(str(decision.get("resource_confidence_reason", "")))

    st.caption(
        f"25-year neutral scenario leader: {lifetime_leader['manufacturer']} {lifetime_leader['model']} · "
        f"{lifetime_leader['lifetime_energy_common_degradation_scenario_kwh_kwp']:,.0f} kWh/kWp. "
        f"Lifetime status: {decision.get('lifetime_status','not differentiated')}."
    )
    if decision.get("next_evidence_request"):
        st.info("**Next best evidence:** " + str(decision["next_evidence_request"]), icon=":material/science:")

    with st.expander("Decision robustness gates", expanded=False):
        gate_rows = [
            {"Gate": "Independent resource agreement", "Ready for Robust": decision.get("resource_confidence") == "High", "Why": decision.get("resource_confidence_reason", "")},
            {"Gate": "Multi-year resource history", "Ready for Robust": bool(decision.get("resource_history_ready_for_robust", False)), "Why": "Requires shared empirical interannual scenarios from at least two complete years."},
            {"Gate": "Off-STC electrical evidence", "Ready for Robust": bool(decision.get("robust_evidence_ready", False)), "Why": decision.get("robust_evidence_reason", "")},
            {"Gate": "Thermal evidence", "Ready for Robust": bool(decision.get("robust_thermal_ready", False)), "Why": decision.get("robust_thermal_reason", "")},
            {"Gate": "Project geometry", "Ready for Robust": bool(decision.get("geometry_ready_for_robust", False)), "Why": f"Geometry evidence: {decision.get('geometry_confidence','screening_assumptions').replace('_',' ')}."},
            {"Gate": "Decision-material rear side", "Ready for Robust": bool(decision.get("robust_rear_ready", False)), "Why": decision.get("robust_rear_reason", "")},
        ]
        st.dataframe(pd.DataFrame(gate_rows), width="stretch", hide_index=True)
        st.caption("Robust is a claim-strength label. Failing a gate does not alter the modeled mean energy; it limits how strongly Solaryn may recommend the result.")

    if switching_error:
        st.warning(
            "**Commercial switching value unavailable**\n\nAdd a real supplier quote for the selected baseline to enable the maximum justifiable price premium.",
            icon=":material/request_quote:",
        )
    else:
        eligible_switching = switching[switching["allowable_module_price_premium_vs_baseline_usd_w"].notna()].copy()
        if not eligible_switching.empty:
            leader_switch = eligible_switching[eligible_switching["module_id"] == decision["technical_leader_module_id"]]
            threshold_row = (leader_switch.iloc[0] if not leader_switch.empty else eligible_switching.sort_values("allowable_module_price_premium_vs_baseline_usd_w", ascending=False).iloc[0])
            st.metric(
                "Maximum justified module-price premium",
                f"${threshold_row['allowable_module_price_premium_vs_baseline_usd_w']:.3f}/W",
                border=True,
            )
            st.caption("Relative to the quoted baseline using discounted energy value plus area-sensitive BOS. Evidence-limited values remain sensitivities.")
    comparison = results[[
        "manufacturer", "model", "technology_label",
        "annual_dc_specific_energy_kwh_kwp", "annual_dc_specific_energy_no_spectral_kwh_kwp",
        "annual_project_dc_energy_mwh", "iam_effect_pct", "spectral_effect_pct",
        "off_stc_irradiance_response_pct", "temperature_response_effect_pct",
        "bifaciality_factor", "bifacial_rear_gain_pct", "annual_rear_optical_poa_kwh_m2",
        "avg_cell_temperature_c_daylight", "p95_cell_temperature_c_daylight",
        "lifetime_energy_common_degradation_scenario_kwh_kwp", "lifetime_energy_warranty_scenario_kwh_kwp",
        "lifetime_project_dc_energy_mwh", "year_25_common_scenario_end_retention_pct", "year_25_warranty_end_retention_pct",
        "electrical_model", "decision_eligible", "model_evidence_level",
        "spectral_policy", "spectral_proxy_status", "spectral_proxy_valid_daylight_fraction_pct",
        "spectral_proxy_fallback_policy", "exploratory_electrical_model_failure",
        "thermal_model", "thermal_evidence_level",
    ]].sort_values("lifetime_energy_common_degradation_scenario_kwh_kwp", ascending=False)
    visual_tab, physics_tab, switching_tab, resource_tab, evidence_tab = st.tabs(
        ["Visual analytics", "Energy comparison", "Switching economics", "Climate & exposure", "Evidence"]
    )

    # Build presentation-grade chart datasets from the same calculation objects used by
    # the tables/report. No separate scoring path is introduced for visualization.
    monthly_profile = pd.DataFrame()
    if not hourly_all.empty and {"timestamp", "module_id", "specific_power_kw_per_kwp"}.issubset(hourly_all.columns):
        hp = hourly_all.copy()
        hp["timestamp"] = pd.to_datetime(hp["timestamp"], errors="coerce")
        hp["month"] = hp["timestamp"].dt.month
        hp["annual_weight"] = pd.to_numeric(hp.get("days_weight", 1.0), errors="coerce").fillna(1.0)
        hp["weighted_specific_energy"] = pd.to_numeric(hp["specific_power_kw_per_kwp"], errors="coerce") * hp["annual_weight"]
        monthly_profile = (
            hp.dropna(subset=["month", "weighted_specific_energy"])
              .groupby(["month", "module_id"], as_index=False)["weighted_specific_energy"].sum()
              .rename(columns={"weighted_specific_energy": "specific_power_kw_per_kwp"})
        )
        display_map = dict(zip(selected["module_id"], selected["manufacturer"].astype(str) + " " + selected["model"].astype(str)))
        monthly_profile["candidate"] = monthly_profile["module_id"].map(display_map)

    with visual_tab:
        st.caption("Board-ready visuals generated from the same hourly physics, uncertainty, lifetime and economics outputs shown elsewhere in this analysis.")
        st.markdown("### Annual specific energy")
        energy_chart = results[["manufacturer", "model", "annual_yield_kwh_kwp"]].copy()
        energy_chart["candidate"] = energy_chart["manufacturer"].astype(str) + " " + energy_chart["model"].astype(str)
        st.bar_chart(energy_chart.set_index("candidate")[["annual_yield_kwh_kwp"]], horizontal=True)

        cprob, cstress = st.columns(2, gap="large")
        with cprob:
            st.markdown("### Decision-frontier probability of best")
            prob = pd.DataFrame([
                {"module_id": mid, "probability_pct": val}
                for mid, val in (decision.get("probability_by_candidate_pct", {}) or {}).items()
            ])
            if not prob.empty:
                prob["candidate"] = prob["module_id"].map(dict(zip(selected["module_id"], selected["manufacturer"].astype(str)+" "+selected["model"].astype(str))))
                st.bar_chart(prob.set_index("candidate")[["probability_pct"]], horizontal=True)
        with cstress:
            st.markdown("### High-temperature exposure")
            stress_chart = stress_df.copy()
            stress_chart["candidate"] = stress_chart["manufacturer"].astype(str)+" "+stress_chart["model"].astype(str)
            st.bar_chart(stress_chart.set_index("candidate")[["hot_cell_hours_gt_65c"]], horizontal=True)

        st.markdown("### Monthly production profile")
        if not monthly_profile.empty:
            month_pivot = monthly_profile.pivot(index="month", columns="candidate", values="specific_power_kw_per_kwp").sort_index()
            month_pivot.index = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][:len(month_pivot)]
            st.line_chart(month_pivot)
        else:
            st.info("Monthly profile is unavailable because hourly timestamps were not retained in this run.")

        st.markdown("### 25-year neutral degradation sensitivity")
        d = max(0.0, min(99.0, float(common_degradation))) / 100.0
        life_rows=[]
        for _, rr in results.iterrows():
            start_ret=1.0
            label=f"{rr['manufacturer']} {rr['model']}"
            for year in range(1,26):
                end_ret=start_ret*(1.0-d)
                life_rows.append({"year":year,"candidate":label,"annual_kwh_kwp":float(rr['annual_yield_kwh_kwp'])*0.5*(start_ret+end_ret)})
                start_ret=end_ret
        life_df=pd.DataFrame(life_rows).pivot(index="year",columns="candidate",values="annual_kwh_kwp")
        st.line_chart(life_df)
        st.caption("All candidates use the same declared degradation sensitivity here; this graph does not imply product-specific field degradation validation.")

        st.markdown("### Procurement switching value")
        if switching_error or switching is None or switching.empty:
            st.info("Enter a real baseline supplier quote to activate the switching-value chart.")
        else:
            econ = switching.dropna(subset=["allowable_module_price_premium_vs_baseline_usd_w"]).copy()
            if econ.empty:
                st.info("No decision-eligible switching values are available for the selected baseline.")
            else:
                econ["candidate"] = econ["manufacturer"].astype(str)+" "+econ["model"].astype(str)
                st.bar_chart(econ.set_index("candidate")[["allowable_module_price_premium_vs_baseline_usd_w"]], horizontal=True)
    with physics_tab:
        st.caption("Ranked by the common multiplicative degradation sensitivity. Values are modeled DC outputs; field lifetime differentiation is only enabled when product/BOM evidence supports it.")
        st.dataframe(
            comparison[["manufacturer", "model", "annual_dc_specific_energy_no_spectral_kwh_kwp",
                        "lifetime_energy_common_degradation_scenario_kwh_kwp", "decision_eligible"]],
            column_config={
                "manufacturer": "Manufacturer", "model": "Module",
                "annual_dc_specific_energy_no_spectral_kwh_kwp": st.column_config.NumberColumn("Annual broadband DC (kWh/kWp)", format="%.1f"),
                "lifetime_energy_common_degradation_scenario_kwh_kwp": st.column_config.NumberColumn("25-year scenario (kWh/kWp)", format="%.0f"),
                "decision_eligible": "Decision evidence eligible",
            }, hide_index=True, width="stretch",
        )
        st.markdown("### Why the ranking changes")
        driver_cols = ["manufacturer", "model", "off_stc_irradiance_response_pct", "temperature_response_effect_pct", "bifacial_rear_gain_pct", "iam_effect_pct"]
        st.dataframe(
            comparison.reindex(columns=driver_cols), hide_index=True, width="stretch",
            column_config={
                "off_stc_irradiance_response_pct": st.column_config.NumberColumn("Off-STC irradiance response", format="%.2f%%"),
                "temperature_response_effect_pct": st.column_config.NumberColumn("Temperature response effect", format="%.2f%%"),
                "bifacial_rear_gain_pct": st.column_config.NumberColumn("Rear-side energy gain", format="%.2f%%"),
                "iam_effect_pct": st.column_config.NumberColumn("Front geometry/IAM effect", format="%.2f%%"),
            },
        )
        st.caption("These are transparent model ablations/sensitivities, not additive technology scores. Candidate-specific measured P(G,T), IAM, spectral response and rear-field validation remain stronger evidence when available.")
        with st.expander("Full physics outputs", icon=":material/table_chart:"):
            st.dataframe(comparison, hide_index=True, width="stretch")

    with resource_tab:
        st.markdown("### Environmental exposure — not degradation prediction")
        st.dataframe(
            stress_df[[
                "manufacturer", "model", "hot_cell_hours_gt_55c", "hot_cell_hours_gt_65c",
                "hot_humid_hours_rh85_t40", "mean_daily_cell_temp_range_c",
                "days_cell_temp_range_gt_30c", "damp_heat_exposure_proxy", "calibration_status",
            ]],
            hide_index=True, width="stretch"
        )
        st.caption(
            "These stress metrics are transparent exposure counts/proxies. They do not add an invented "
            "technology penalty or produce a %/year degradation rate."
        )

    with switching_tab:
        st.markdown("### Procurement switching point")
        if switching_error:
            st.info(switching_error + " Economic outputs remain disabled until a real baseline quote is entered.")
        else:
            st.dataframe(
                switching[[
                    "manufacturer", "model", "actual_quote_usd_w",
                    "npv_energy_value_usd_per_w", "area_bos_proxy_usd_per_w",
                    "allowable_module_price_premium_vs_baseline_usd_w",
                    "indifference_module_price_usd_w",
                    "indifference_module_price_warranty_sensitivity_usd_w",
                    "economically_preferred_vs_baseline_at_quote",
                    "economic_decision_eligible", "economic_evidence_note",
                ]],
                hide_index=True, width="stretch"
            )
            st.caption("Switching value is a procurement sensitivity based on discounted energy value and area-sensitive BOS. Evidence-limited rows are explicitly flagged; this is not a complete project LCOE.")

    with resource_tab:
        st.markdown("### Independent resource check")
        st.metric("Resource confidence", str(decision.get("resource_confidence", "Not checked")), border=True)
        if decision.get("resource_confidence") == "Low":
            st.warning(pvgis_note + " This disagreement caps the recommendation at Conditional until the resource basis is reconciled.")
        elif decision.get("resource_confidence") == "Not checked":
            st.info(pvgis_note + " A robust recommendation requires an independent resource check.")
        else:
            st.write(pvgis_note)

    with evidence_tab:
        st.markdown("### Evidence / model boundary")
        st.dataframe(
            selected.reindex(columns=[
                "manufacturer", "model", "technology_id", "cells_in_series_basis",
                "evidence_status", "source_url", "source_note",
            ]),
            hide_index=True, width="stretch"
        )
        st.caption(
            "The full Solaryn material/device database remains available in Technology Library mode. "
            "It does not override this EPC module-level IV result."
        )

    leader_technology = str(decision.get("technical_leader_technology") or "Technical_Leader")
    leader_slug = _safe_slug(leader_technology, "Technical_Leader")
    project_slug = _safe_slug(project_label, f"Site_{lat:.2f}_{lon:.2f}".replace("-", "M"))

    report = build_epc_html_report(
        site=site.to_dict(),
        project={
            "project_name": project_label,
            "reference_year": reference_year,
            "resource_start_year": resource_start_year,
            "resource_years": resource_years,
            "system_size_mw": system_size_mw,
            "tilt_deg": tilt_deg,
            "azimuth_deg": azimuth_deg,
            "row_geometry_enabled": model_row_geometry,
            "albedo": albedo, "gcr": gcr, "row_height_m": row_height_m, "row_pitch_m": row_pitch_m,
            "rear_structure_loss_pct": rear_structure_loss_pct,
            "geometry_confidence": geometry_confidence,
            "soiling_loss_pct": soiling_loss_pct,
            "common_degradation_pct_year": common_degradation,
            "uncertainty_guardrail_pct": uncertainty_guardrail,
            "project_segment": project_segment,
            "mode": "module recommendation",
        },
        results=results,
        decision=decision,
        modules=selected,
        stress=stress_df,
        switching=switching,
        pvgis_note=pvgis_note,
        hourly=hourly_all,
    )
    st.subheader("Export analysis")
    st.caption("The complete project package is named from the selected city/project and the technical-leading technology.")

    csv = results.merge(stress_df, on=["module_id", "manufacturer", "model"], how="left")
    csv_bytes = csv.to_csv(index=False).encode("utf-8")
    hourly_bytes = hourly_all.to_csv(index=False).encode("utf-8") if not hourly_all.empty else b""

    report_name = f"Solaryn_{project_slug}_{leader_slug}_Executive_Report.html"
    comparison_name = f"Solaryn_{project_slug}_{leader_slug}_Comparison.csv"
    hourly_name = f"Solaryn_{project_slug}_{leader_slug}_Hourly_Physics.csv"
    package_name = f"Solaryn_{project_slug}_{leader_slug}.zip"

    package_readme = (
        f"Solaryn project: {project_label}\n"
        f"Coordinates: {lat:.5f}, {lon:.5f}\n"
        f"Technical-leading technology: {leader_technology}\n"
        f"Decision status: {decision.get('decision_status', 'Conditional')}\n"
        f"Resource years: {resource_start_year}–{reference_year}\n"
        f"Project DC size: {system_size_mw:g} MWp\n\n"
        "This package preserves the recommendation report, comparison data, and the evidence-aware decision status. "
        "A technical leader is not automatically a validated commercial winner.\n"
    ).encode("utf-8")
    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", package_readme)
        zf.writestr(report_name, report.encode("utf-8"))
        zf.writestr(comparison_name, csv_bytes)
        if hourly_bytes:
            zf.writestr(hourly_name, hourly_bytes)
        validation_report_path = root / "validation/results/Solaryn_Real_World_Validation_Report.html"
        if validation_report_path.exists():
            zf.writestr("Solaryn_Real_World_Validation_Report.html", validation_report_path.read_bytes())

    st.download_button(
        "Download complete Solaryn project (ZIP)",
        data=package_buffer.getvalue(),
        file_name=package_name,
        mime="application/zip",
        type="primary",
        width="stretch",
    )
    st.download_button(
        "Download recommendation report (HTML)",
        data=report.encode("utf-8"),
        file_name=report_name,
        mime="text/html",
        width="stretch",
    )
    st.download_button(
        "Download comparison data (CSV)",
        data=csv_bytes,
        file_name=comparison_name,
        mime="text/csv",
        width="stretch",
    )

    if hourly_bytes:
        st.download_button(
            "Download hourly module physics (CSV)",
            data=hourly_bytes,
            file_name=hourly_name,
            mime="text/csv",
            width="stretch",
        )
