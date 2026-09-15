from __future__ import annotations

from datetime import date
from pathlib import Path

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
from src.epc_decision import epc_energy_decision, poc_validation_decision
from src.evidence_policy import project_segment_compatible, DEFAULT_ENERGY_RATING_UNCERTAINTY_GUARDRAIL_PCT
from src.epc_report import build_epc_html_report


@st.cache_data(show_spinner=False)
def _load_seed_modules(root_str: str) -> pd.DataFrame:
    return pd.read_csv(Path(root_str) / "data/raw/module_candidate_master.csv")


@st.cache_data(show_spinner=True)
def _nasa_hourly(lat: float, lon: float, start: str, end: str):
    return fetch_nasa_power_hourly_dataframe(lat, lon, start, end)


@st.cache_data(show_spinner=True)
def _pvgis_hourly(lat: float, lon: float, year: int, angle: float, aspect: float):
    return fetch_pvgis_hourly_dataframe(
        lat, lon, startyear=year, endyear=year, angle=angle, aspect=aspect
    )


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
    st.caption("Not a bankability opinion. External scientific and procurement validation remain pending.")
    with st.expander("How to use this workspace", icon=":material/help:"):
        st.write("1. Configure your project and select its location.\n2. Choose comparable module offers and add actual quotes if available.\n3. Run the physics comparison, review evidence flags, and export the report.")
        st.write("At least two successfully simulated candidates are required. The PoC returns a provisional leader and, with a real baseline quote, a switching threshold. Evidence gaps remain visible; they do not become a validation PASS.")

    st.session_state.setdefault("selected_lat", 24.7136)
    st.session_state.setdefault("selected_lon", 46.6753)

    st.subheader("01  Project setup")
    st.caption("Shared assumptions apply to every selected candidate.")
    with st.container(border=True):
        geometry_tab, economics_tab, policy_tab = st.tabs(["Project & geometry", "Economics", "Validation & sensitivities"])
        with geometry_tab:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                reference_year = int(st.number_input("Reference year", min_value=2005, max_value=2023, value=2020, step=1))
            with c2:
                system_size_mw = st.number_input("Project DC size (MWp)", min_value=0.1, max_value=5000.0, value=100.0, step=1.0)
            with c3:
                tilt_deg = st.number_input("Fixed tilt (°)", min_value=0.0, max_value=60.0, value=25.0, step=1.0)
            with c4:
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
                help="The current PoC economics engine and report schema use USD/W. EUR/W and currency conversion remain a production requirement.",
            )

        with policy_tab:
            min_sep = st.number_input(
                "Decision separation policy (%)", min_value=0.0, max_value=10.0, value=1.0, step=0.25,
                help="Validation threshold only. In POC mode it changes the confidence label but does not suppress the provisional result."
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
                    help="Validation-confidence threshold, not a confidence interval. It does not block the POC result."
                )
            with g3:
                project_segment = st.selectbox(
                    "Project segment", ["utility", "commercial", "residential", "research"], index=0,
                    help="Prevents apples-to-oranges comparisons. Research mode disables segment filtering but also weakens commercial claims."
                )

    st.subheader("02  Project location")
    st.caption("Select the map or enter coordinates. Manual entry provides a keyboard-accessible alternative to the map.")
    def _apply_manual_location() -> None:
        st.session_state.selected_lat = float(st.session_state.manual_latitude)
        st.session_state.selected_lon = float(st.session_state.manual_longitude)

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
        m = folium.Map([lat, lon], zoom_start=4, tiles="OpenStreetMap", control_scale=True)
        folium.Marker([lat, lon], tooltip="Selected project location").add_to(m)
        folium.LatLngPopup().add_to(m)
        res = st_folium(m, height=320, returned_objects=["last_clicked"], width=None)
        if res and res.get("last_clicked"):
            new_lat = float(res["last_clicked"]["lat"])
            new_lon = float(res["last_clicked"]["lng"])
            if abs(new_lat-lat)>1e-7 or abs(new_lon-lon)>1e-7:
                st.session_state.selected_lat = new_lat
                st.session_state.selected_lon = new_lon
                lat, lon = new_lat, new_lon
                azimuth_deg = 180.0 if lat >= 0 else 0.0
    with info_col:
        st.badge(f"{lat:.5f}, {lon:.5f}", icon=":material/location_on:", color="blue")
        st.subheader("Site configuration")
        st.write(f"• Project segment: {project_segment}")
        st.write("• Fixed tilt")
        st.write("• Monofacial")
        st.write(f"• Equator-facing azimuth: {azimuth_deg:.0f}°")
        st.caption("Trackers, rear-side bifacial gain, terrain/shading and inverter AC design are deliberately outside this PoC.")

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

    st.caption(f"Ready to compare {len(selected)} candidates · {reference_year} · {system_size_mw:g} MWp · {quote_count} supplier quotes")
    run = st.button("Run EPC physics comparison", type="primary", width="stretch", icon=":material/play_arrow:")
    if not run:
        st.stop()

    start = f"{reference_year}-01-01"
    end = f"{reference_year}-12-31"
    try:
        with st.status("Preparing site climate", expanded=True) as climate_status:
            climate_status.write("Requesting full-year NASA POWER hourly data…")
            nasa = _nasa_hourly(lat, lon, start, end)
            climate_status.write("Calculating solar position, plane-of-array irradiance, and cell temperature…")
            site = nasa_hourly_to_site_summary(
                nasa, lat, lon, project_name="EPC pilot project",
                system_size_mw=system_size_mw, site_type=project_segment,
                require_full_year=True,
            ).iloc[0]
            weather = nasa_hourly_to_pvlib_weather(
                nasa, lat, lon, tilt_deg=tilt_deg, azimuth_deg=azimuth_deg
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
                weather, row, common_soiling_loss_pct=soiling_loss_pct, root=root
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
                "POC cannot compare modules because fewer than two candidates simulated successfully:\n\n- "
                + "\n- ".join(failed)
            )
            st.stop()
        st.info(
            "Non-blocking model diagnostic: these candidates were skipped because their IV simulation failed. "
            "The POC continues with the successfully simulated candidates:\n\n- " + "\n- ".join(failed)
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
            "POC comparison requires at least two candidates with finite successful simulations. "
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
    robust_decision = epc_energy_decision(
        results, minimum_separation_pct=min_sep, uncertainty_guardrail_pct=uncertainty_guardrail
    )
    decision = poc_validation_decision(
        results, minimum_separation_pct=min_sep, uncertainty_guardrail_pct=uncertainty_guardrail
    )

    pvgis_note = "PVGIS cross-check disabled."
    pvgis_delta = np.nan
    if use_pvgis:
        try:
            pvgis_aspect = pvlib_azimuth_to_pvgis_aspect(azimuth_deg)
            pv = _pvgis_hourly(lat, lon, reference_year, tilt_deg, pvgis_aspect)
            nasa_poa = float(pd.to_numeric(weather["poa_w_m2"], errors="coerce").fillna(0).sum()/1000.0)
            pvgis_poa = float(pd.to_numeric(pv["poa_w_m2"], errors="coerce").fillna(0).sum()/1000.0)
            pvgis_delta = 100.0 * (nasa_poa - pvgis_poa) / max(abs(pvgis_poa), 1e-9)
            pvgis_note = (
                f"NASA→pvlib annual POA {nasa_poa:,.0f} kWh/m² vs PVGIS "
                f"{pvgis_poa:,.0f} kWh/m²; difference {pvgis_delta:+.1f}%."
            )
        except Exception as exc:
            pvgis_note = f"PVGIS cross-check failed: {exc}"

    switching = None
    try:
        switching = switching_point_table(
            results, selected, baseline_id,
            energy_value_usd_kwh=energy_value,
            discount_rate_pct=discount_rate,
            area_bos_usd_m2=area_bos_cost,
            years=25, common_degradation_pct_year=common_degradation,
            allow_exploratory=True,
        )
    except Exception as exc:
        switching_error = str(exc)
    else:
        switching_error = None

    st.subheader("04  Commercial decision")
    if switching_error:
        st.warning(
            "**Maximum justified price premium unavailable**\n\nAdd a real quote for the selected baseline to enable the commercial switching threshold.",
            icon=":material/request_quote:",
        )
    else:
        eligible_switching = switching[
            switching["allowable_module_price_premium_vs_baseline_usd_w"].notna()
        ].copy()
        if not eligible_switching.empty:
            threshold_row = eligible_switching.sort_values(
                "allowable_module_price_premium_vs_baseline_usd_w", ascending=False
            ).iloc[0]
            st.metric(
                "Maximum justified price premium",
                f"${threshold_row['allowable_module_price_premium_vs_baseline_usd_w']:.3f}/W",
                border=True,
            )
            st.caption("Current PoC currency: USD. This threshold is exploratory when model evidence is incomplete.")
    st.info("**Modeled decision**\n\n" + decision["headline"], icon=":material/analytics:")
    if not decision["evidence_complete_for_all_selected_candidates"]:
        st.info(
            "Evidence to strengthen before commercial/bankability claims: "
            + ", ".join(decision["decision_ineligible_module_ids"])
            + ". Their current outputs are kept as transparent exploratory POC simulations."
        )
    if decision.get("robust_winner_module_id") is None:
        st.caption("Bankability-style secondary check: " + str(decision.get("robust_headline", "")))

    k1, k2, k3, k4 = st.columns(4)
    lifetime_leader = results.sort_values("lifetime_energy_common_degradation_scenario_kwh_kwp", ascending=False).iloc[0]
    annual_leader = results.sort_values("annual_yield_kwh_kwp", ascending=False).iloc[0]
    k1.metric("Annual leader · kWh/kWp", f"{annual_leader['annual_yield_kwh_kwp']:,.1f}", border=True)
    k1.caption(f"{annual_leader['manufacturer']} {annual_leader['model']}")
    k2.metric("25-year leader · kWh/kWp", f"{lifetime_leader['lifetime_energy_common_degradation_scenario_kwh_kwp']:,.0f}", border=True)
    k2.caption(f"{lifetime_leader['manufacturer']} {lifetime_leader['model']}")
    k3.metric("Lead / validation threshold", f"{decision['annual_lead_over_second_pct']:.2f}% / {decision['required_decision_gap_pct']:.2f}%", border=True)
    k4.metric("Validation confidence", str(decision.get("validation_confidence", "exploratory")).title(), border=True)

    comparison = results[[
        "manufacturer", "model", "technology_label",
        "annual_dc_specific_energy_kwh_kwp", "annual_dc_specific_energy_no_spectral_kwh_kwp",
        "annual_project_dc_energy_mwh", "iam_effect_pct", "spectral_effect_pct",
        "avg_cell_temperature_c_daylight", "p95_cell_temperature_c_daylight",
        "lifetime_energy_common_degradation_scenario_kwh_kwp", "lifetime_energy_warranty_scenario_kwh_kwp",
        "lifetime_project_dc_energy_mwh", "year_25_common_scenario_end_retention_pct", "year_25_warranty_end_retention_pct",
        "electrical_model", "decision_eligible", "model_evidence_level",
        "spectral_policy", "spectral_proxy_status", "spectral_proxy_valid_daylight_fraction_pct",
        "spectral_proxy_fallback_policy", "exploratory_electrical_model_failure",
        "thermal_model", "thermal_evidence_level",
    ]].sort_values("lifetime_energy_common_degradation_scenario_kwh_kwp", ascending=False)
    physics_tab, switching_tab, resource_tab, evidence_tab = st.tabs(
        ["Energy comparison", "Switching economics", "Climate & exposure", "Evidence"]
    )
    with physics_tab:
        st.caption("Ranked by the unchanged common-degradation lifetime scenario. Values are modeled DC outputs, not measured performance.")
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
            st.caption("POC switching threshold: useful for validation and offer sensitivity. Exploratory rows are explicitly flagged; this is not LCOE or a bankability opinion.")

    with resource_tab:
        st.markdown("### Independent resource check")
        if np.isfinite(pvgis_delta) and abs(pvgis_delta) > 10:
            st.warning(pvgis_note + " Investigate the resource/geometry mismatch before using the decision.")
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
            "The full Solaryn material/device database remains available in Technology Screening mode. "
            "It does not override this EPC module-level IV result."
        )

    report = build_epc_html_report(
        site=site.to_dict(),
        project={
            "reference_year": reference_year,
            "system_size_mw": system_size_mw,
            "tilt_deg": tilt_deg,
            "azimuth_deg": azimuth_deg,
            "soiling_loss_pct": soiling_loss_pct,
            "common_degradation_pct_year": common_degradation,
            "uncertainty_guardrail_pct": uncertainty_guardrail,
            "project_segment": project_segment,
            "mode": "POC validation — provisional ranking",
        },
        results=results,
        decision=decision,
        modules=selected,
        stress=stress_df,
        switching=switching,
        pvgis_note=pvgis_note,
    )
    st.subheader("Export analysis")
    st.caption("Keep the evidence flags and assumptions with every shared result.")
    st.download_button(
        "Download EPC validation report (HTML)",
        data=report.encode("utf-8"),
        file_name="solaryn_epc_validation_report.html",
        mime="text/html",
        width="stretch",
    )

    csv = results.merge(stress_df, on=["module_id", "manufacturer", "model"], how="left")
    st.download_button(
        "Download comparison data (CSV)",
        data=csv.to_csv(index=False).encode("utf-8"),
        file_name="solaryn_epc_comparison.csv",
        mime="text/csv",
        width="stretch",
    )

    if hourly_frames:
        hourly_all = pd.concat(hourly_frames, ignore_index=True)
        st.download_button(
            "Download hourly module physics (CSV)",
            data=hourly_all.to_csv(index=False).encode("utf-8"),
            file_name="solaryn_epc_hourly_physics.csv",
            mime="text/csv",
            width="stretch",
        )
