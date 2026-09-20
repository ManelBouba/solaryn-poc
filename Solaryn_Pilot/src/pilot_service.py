"""Deterministic local analysis orchestration. The UI only supplies inputs/renders results."""
from datetime import datetime, timezone
from pathlib import Path
import importlib.metadata
import io
import json
import numpy as np
import pandas as pd
from src.data_fetchers import nasa_hourly_to_site_summary
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.module_iv_engine import simulate_module_hourly, validate_module_candidates
from src.lifetime_engine import (
    add_lifetime_metrics, common_degradation_curve, lifetime_energy_distribution,
    degradation_parameters_for_candidate,
)
from src.degradation_stress import compute_stress_exposures
from src.economics_engine import switching_point_table
from src.input_validation import finite_number, horizon_years
from src.pilot_decision import decide, POLICY_RELEASE
from src.run_store import RunStore, json_bytes, sha, clean
from src.site_qualification import qualification_for_candidate, classify_site_exposure
from src.evidence_hierarchy import assess_candidate_evidence
from src.decision_trace import build_candidate_trace
from src.uncertainty_engine import (
    compare_candidates_correlated, compare_lifetime_candidates_correlated,
)

MODEL_RELEASE = "6.0.0-audit-hardened"
LIMITATIONS = [
    "DC module energy, not delivered AC energy or full LCOE.",
    "Common degradation is a shared project prior unless product-specific field evidence exists; warranty remains a sensitivity, not a lifetime forecast.",
    "Generic spectral response is a sensitivity; it does not choose the primary leader.",
    "The measured SUPSI case validates a reference electrical layer, not commercial-SKU ranking.",
    "Local single-user workspace; cloud authentication and multi-tenant authorization are not implemented.",
]

def validate_project(project):
    p = dict(project)
    if not str(p.get("project_name", "")).strip(): raise ValueError("Project name is required.")
    for field, low, high in [("latitude", -90, 90), ("longitude", -180, 180),
                            ("tilt_deg", 0, 90), ("azimuth_deg", 0, 360),
                            ("soiling_loss_pct", 0, 99), ("common_degradation_pct_year", 0, 20)]:
        p[field] = finite_number(p[field], field, low, high)
    p["system_size_mw"] = finite_number(p["system_size_mw"], "capacity MWp", positive=True)
    p["target_lifetime_years"] = horizon_years(p.get("target_lifetime_years", 25))
    if p.get("currency", "USD") not in {"USD", "EUR"}: raise ValueError("Use USD or EUR consistently; no currency conversion is performed.")
    if p.get("geometry_type", "fixed_tilt") != "fixed_tilt": raise ValueError("Only fixed-tilt geometry is implemented.")
    # Evidence-aware climate qualification inputs. ``auto`` never infers marine salinity
    # from coordinates without a coastline/salt-deposition dataset.
    p.setdefault("salinity_stress", "auto")
    p.setdefault("hard_qualification_gates", False)
    p.setdefault("snow_model_enabled", True)
    p.setdefault("soiling_model", "constant")
    p.setdefault("snow_albedo", None)
    if p["snow_albedo"] not in (None, ""):
        p["snow_albedo"] = finite_number(p["snow_albedo"], "snow_albedo", 0.0, 1.0)
    else:
        p["snow_albedo"] = None
    if str(p["soiling_model"]).lower() not in {"constant", "kimber"}:
        raise ValueError("soiling_model must be 'constant' or 'kimber'.")
    p["soiling_model"] = str(p["soiling_model"]).lower()
    if p["soiling_model"] == "kimber":
        p["soiling_loss_rate_per_day"] = finite_number(p.get("soiling_loss_rate_per_day"), "soiling_loss_rate_per_day", 0.0, 0.1)
        p["soiling_cleaning_threshold_mm"] = finite_number(p.get("soiling_cleaning_threshold_mm"), "soiling_cleaning_threshold_mm", 0.01, 100.0)
        p["soiling_max_fraction"] = finite_number(p.get("soiling_max_fraction", 0.30), "soiling_max_fraction", 0.0, 1.0)
        p["soiling_grace_period_days"] = int(finite_number(p.get("soiling_grace_period_days", 14), "soiling_grace_period_days", 0, 365))
    # Uncertainty defaults are common across candidates unless product-specific
    # validation evidence supplies an empirical residual. Evidence grade alone never
    # receives an invented numerical sigma.
    p.setdefault("screening_candidate_model_sigma_pct", 5.0)
    p.setdefault("shared_resource_sigma_pct", 3.0)
    p.setdefault("common_degradation_sigma_pct_year", 0.20)
    p.setdefault("annual_yield_sigma_pct", 3.0)
    p.setdefault("monte_carlo_samples", 5000)
    p.setdefault("no_clear_winner_probability_pct", 65.0)
    for key, low, high in [
        ("screening_candidate_model_sigma_pct", 0.01, 50.0),
        ("shared_resource_sigma_pct", 0.0, 50.0),
        ("common_degradation_sigma_pct_year", 0.0, 10.0),
        ("annual_yield_sigma_pct", 0.0, 50.0),
        ("no_clear_winner_probability_pct", 0.0, 100.0),
    ]:
        p[key] = finite_number(p[key], key, low, high)
    p["monte_carlo_samples"] = int(finite_number(p["monte_carlo_samples"], "monte_carlo_samples", 100, 200000))
    return clean(p)

def csv_bytes(frame):
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")

def export_csv(frame):
    f = frame.copy()
    for col in f.select_dtypes(include=["object", "string"]).columns:
        f[col] = f[col].map(lambda x: "'" + x if isinstance(x, str) and x.lstrip().startswith(("=", "+", "-", "@")) else x)
    return csv_bytes(f)

def monthly_resource(weather, pvgis=None):
    w = weather.copy()
    months = pd.to_datetime(w.time_utc, utc=True).dt.month
    weights = w.days_weight
    records = pd.DataFrame({"month": months})
    for source, target in [("ghi_w_m2", "nasa_ghi"), ("dni_w_m2", "nasa_dni"), ("dhi_w_m2", "nasa_dhi"), ("poa_w_m2", "solaryn_poa")]:
        records[target] = w[source] * weights / 1000
    table = records.groupby("month", as_index=False).sum()
    status, warning = "not_checked", "Independent resource check was not requested or is unavailable."
    if pvgis is not None:
        times = pd.to_datetime(pvgis.date, utc=True)
        vals = pd.to_numeric(pvgis.poa_w_m2, errors="coerce")
        expected = pd.DatetimeIndex(pd.to_datetime(w.time_utc, utc=True))
        # PVGIS has a provider-specific minute offset; compare hourly slots, not silently shifted values.
        slots = pd.DatetimeIndex(times).floor("h")
        if slots.duplicated().any() or set(slots) != set(expected.floor("h")) or not np.isfinite(vals).all() or (vals < 0).any():
            raise ValueError("PVGIS coverage must match the complete primary resource period.")
        ny = times.dt.year.nunique()
        pv = pd.DataFrame({"month": times.dt.month, "pvgis_poa": vals / (1000 * ny)}).groupby("month", as_index=False).sum()
        table = table.merge(pv, on="month")
        table["absolute_difference"] = table.solaryn_poa - table.pvgis_poa
        table["percentage_difference"] = 100 * table.absolute_difference / table.pvgis_poa.replace(0, np.nan)
        delta = 100 * (table.solaryn_poa.sum() / table.pvgis_poa.sum() - 1)
        status = "adequate" if abs(delta) <= 5 else "warning" if abs(delta) <= 10 else "insufficient_for_robust_claim"
        warning = f"Annual POA differs by {delta:+.2f}%. Product policy bands: 5% / 10%; not a confidence interval."
    return table, status, warning

def analyze(root, project, modules, nasa, pvgis=None, *, store_root=None):
    root = Path(root)
    project = validate_project(project)
    if len(modules) < 2: raise ValueError("Select at least two exact module candidates.")
    modules = modules.sort_values("module_id").reset_index(drop=True).copy()
    validate_module_candidates(modules)
    for col in ["quote_usd_w", "quote_eur_w"]:
        if col in modules:
            q = pd.to_numeric(modules[col], errors="coerce")
            supplied = modules[col].notna() & modules[col].astype(str).str.strip().ne("")
            if (supplied & (~np.isfinite(q) | (q < 0))).any():
                raise ValueError(f"{col} must be blank or finite and non-negative.")
    times = pd.to_datetime(nasa.time_utc, utc=True)
    if nasa.attrs.get("time_standard") != "UTC": raise ValueError("The pilot requires explicit UTC weather.")
    for year in sorted(times.dt.year.unique()):
        expected = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h", tz="UTC")
        actual = pd.DatetimeIndex(times[times.dt.year == year])
        if not actual.equals(expected): raise ValueError("Climate snapshot must contain unique, sorted, complete UTC calendar years.")
    for col in ["ALLSKY_SFC_SW_DWN", "T2M", "WS10M", "RH2M"]:
        if not np.isfinite(pd.to_numeric(nasa[col], errors="coerce")).all(): raise ValueError(f"Missing or non-finite core climate input: {col}")
    site = nasa_hourly_to_site_summary(nasa, project["latitude"], project["longitude"], require_full_year=True).iloc[0].to_dict()
    weather = nasa_hourly_to_pvlib_weather(
        nasa, project["latitude"], project["longitude"], project["tilt_deg"], project["azimuth_deg"],
        albedo=project.get("albedo", .2), snow_albedo=project.get("snow_albedo"),
    )
    artifacts = {"inputs/Project.json": json_bytes(project), "inputs/Modules.csv": csv_bytes(modules), "inputs/NASA-hourly.csv": csv_bytes(nasa)}
    providers = {}
    for name, frame in [("NASA", nasa), ("PVGIS", pvgis)]:
        if frame is None: continue
        metadata = dict(frame.attrs)
        raw = metadata.pop("raw_provider_json", None)
        if raw is not None: artifacts[f"inputs/{name}-raw.json"] = json_bytes(raw)
        if name == "PVGIS": artifacts["inputs/PVGIS-hourly.csv"] = csv_bytes(frame)
        providers[name] = {**metadata, "rows": len(frame), "time_standard": metadata.get("time_standard", "UTC"), "raw_snapshot_available": raw is not None,
                           "normalized_sha256": sha(csv_bytes(frame)), "missingness": frame.isna().sum().to_dict()}
        artifacts[f"inputs/{name}-metadata.json"] = json_bytes(providers[name])
    # Exact performance matrices are dependencies of the calculation and must travel with it.
    for name in modules.get("iec61853_matrix_file", pd.Series(dtype=str)).dropna():
        if str(name).strip():
            file = (root / str(name)).resolve()
            if not file.is_relative_to(root.resolve()): raise ValueError("Matrix path must stay inside the project.")
            if file.exists(): artifacts["model-inputs/" + file.relative_to(root.resolve()).as_posix()] = file.read_bytes()
    measured_reference = root / "validation/results/measured_replay.json"
    reference_validation = None
    if measured_reference.exists():
        reference_validation = json.loads(measured_reference.read_text(encoding="utf-8"))
        source_root = root / "validation/external/iea_pvps_task13_supsi_csi"
        for name, checksum in reference_validation["input_hashes"].items():
            if sha((source_root / name).read_bytes()) != checksum:
                raise ValueError("Measured validation input hash mismatch.")
        artifacts["Reference-measured-validation.json"] = measured_reference.read_bytes()
    versions = {"model_release": MODEL_RELEASE, "decision_policy": POLICY_RELEASE,
                "code_sha256": sha(b"".join(p.name.encode() + p.read_bytes() for p in sorted((root / "src").glob("*.py")))),
                "parameter_release": sha(csv_bytes(modules)),
                "runtime": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scipy", "pvlib", "NREL-PySAM"]}}
    identity = {"inputs": {n: sha(d) for n, d in artifacts.items()}, "versions": versions}
    run_id = sha(json_bytes(identity))
    store = RunStore(store_root or root / "workspace/runs")
    if (store.root / run_id).exists(): return store.read(run_id)
    summaries, hours, stress, failures = [], [], [], []
    for _, module in modules.iterrows():
        try:
            summary, hourly = simulate_module_hourly(weather, module, project["soiling_loss_pct"], root,
                bifacial_config={"enabled": project.get("row_geometry_enabled", False), "gcr": project.get("gcr", .4),
                    "height_m": project.get("row_height_m", 1.5), "pitch_m": project.get("row_pitch_m", 5.),
                    "albedo": project.get("albedo", .2), "rear_structure_loss_pct": project.get("rear_structure_loss_pct", 2.),
                    "snow_model_enabled": project.get("snow_model_enabled", True)},
                soiling_config={
                    "mode": project.get("soiling_model", "constant"),
                    "soiling_loss_rate_per_day": project.get("soiling_loss_rate_per_day"),
                    "cleaning_threshold_mm": project.get("soiling_cleaning_threshold_mm"),
                    "max_soiling_fraction": project.get("soiling_max_fraction", 0.30),
                    "grace_period_days": project.get("soiling_grace_period_days", 14),
                })
            if not np.isfinite(summary["annual_yield_kwh_kwp"]) or summary["annual_yield_kwh_kwp"] <= 0:
                raise ValueError("No positive finite annual energy.")
            if not str(module.get("source_url", "")).startswith(("https://", "http://")):
                summary["decision_eligible"] = False
                summary["model_evidence_level"] = "missing_parameter_source"
            summaries.append(summary); hours.append(hourly)
            stress.append({"module_id": module.module_id, **compute_stress_exposures(hourly)})
        except Exception as exc:
            failures.append({"module_id": str(module.module_id), "simulation_status": "failed", "reason": str(exc)})
    try:
        benchmark, resource_status, resource_reason = monthly_resource(weather, pvgis)
    except ValueError as exc:
        benchmark, _, _ = monthly_resource(weather)
        resource_status, resource_reason = "insufficient_for_robust_claim", str(exc)
    if project.get("provider_warning"):
        resource_reason += " Provider request failed: " + str(project["provider_warning"])
    artifacts["Resource-benchmark.csv"] = export_csv(benchmark)
    resource = {"status": resource_status, "reason": resource_reason, "providers": providers,
                "benchmark": benchmark.to_dict("records"), "units": "kWh/m2/year (monthly contributions)",
                "annual_poa_primary_kwh_m2": float(benchmark.solaryn_poa.sum()),
                "annual_poa_crosscheck_kwh_m2": float(benchmark.pvgis_poa.sum()) if "pvgis_poa" in benchmark else None}
    results = pd.DataFrame()
    qualification_records = {}
    evidence_records = {}
    site_exposure = classify_site_exposure(weather, project)
    if summaries:
        results = add_lifetime_metrics(pd.DataFrame(summaries), modules, years=project["target_lifetime_years"], common_degradation_pct_year=project["common_degradation_pct_year"])
        results["annual_project_dc_energy_mwh"] = results.annual_yield_kwh_kwp * project["system_size_mw"]

        # Climate qualification and evidence quality are governance layers, not hidden
        # performance bonuses. They can condition/block a claim without changing kWh.
        module_lookup = modules.set_index("module_id")
        for idx, rr in results.iterrows():
            mid = str(rr["module_id"])
            mm = module_lookup.loc[mid]
            q = qualification_for_candidate(mm, rr, weather, project).to_dict()
            ev = assess_candidate_evidence(mm, rr, q["status"]).to_dict()
            qualification_records[mid] = q
            evidence_records[mid] = ev
            results.loc[idx, "qualification_status"] = q["status"]
            results.loc[idx, "temperature_qualification_level"] = q["temperature_level"]
            results.loc[idx, "humidity_exposure"] = q["humidity_exposure"]
            results.loc[idx, "salinity_exposure"] = q["salinity_exposure"]
            results.loc[idx, "snow_exposure"] = q["snow_exposure"]
            results.loc[idx, "qualification_missing"] = " | ".join(q["missing"])
            results.loc[idx, "evidence_grade"] = ev["grade"]
            results.loc[idx, "evidence_score"] = ev["score"]
            results.loc[idx, "evidence_gaps"] = " | ".join(ev["gaps"])
            if q["status"] == "blocked":
                results.loc[idx, "decision_eligible"] = False

        # Lifetime uncertainty: do not turn evidence grades or technology labels into
        # invented degradation advantages. Product-specific degradation means are used
        # only when validated field evidence is explicitly present; otherwise candidates
        # share the same project prior.
        for idx, rr in results.iterrows():
            mid = str(rr["module_id"])
            mm = module_lookup.loc[mid]
            degr = degradation_parameters_for_candidate(
                mm,
                common_mean_pct_year=project["common_degradation_pct_year"],
                common_sigma_pct_year=project["common_degradation_sigma_pct_year"],
            )
            dist = lifetime_energy_distribution(
                rr["annual_yield_kwh_kwp"],
                mean_degradation_pct_year=degr["mean_pct_year"],
                degradation_sigma_pct_year=degr["sigma_pct_year"],
                annual_yield_sigma_pct=project["annual_yield_sigma_pct"],
                years=project["target_lifetime_years"],
                n=project["monte_carlo_samples"],
                seed=95 + idx,
            )
            results.loc[idx, "degradation_mean_pct_year"] = degr["mean_pct_year"]
            results.loc[idx, "degradation_sigma_pct_year"] = degr["sigma_pct_year"]
            results.loc[idx, "degradation_evidence_basis"] = degr["basis"]
            results.loc[idx, "lifetime_p50_kwh_kwp"] = dist["p50_lifetime_kwh_kwp"]
            results.loc[idx, "lifetime_p90_kwh_kwp"] = dist["p90_lifetime_kwh_kwp"]
            # Common fallback residual width for every candidate. Product-specific
            # empirical residual fields can still override it inside the uncertainty engine.
            results.loc[idx, "screening_model_sigma_pct"] = project["screening_candidate_model_sigma_pct"]

    uncertainty = None
    lifetime_uncertainty = None
    if len(results) >= 2:
        try:
            uncertainty = compare_candidates_correlated(
                results, value_col="annual_yield_kwh_kwp",
                shared_resource_sigma_pct=project["shared_resource_sigma_pct"],
                default_candidate_sigma_pct=project["screening_candidate_model_sigma_pct"],
                n=max(1000, project["monte_carlo_samples"]), seed=95
            )
            lifetime_uncertainty = compare_lifetime_candidates_correlated(
                results,
                years=project["target_lifetime_years"],
                shared_resource_sigma_pct=project["shared_resource_sigma_pct"],
                default_candidate_sigma_pct=project["screening_candidate_model_sigma_pct"],
                common_degradation_mean_pct_year=project["common_degradation_pct_year"],
                common_degradation_sigma_pct_year=project["common_degradation_sigma_pct_year"],
                n=max(1000, project["monte_carlo_samples"]), seed=195,
            )
        except ValueError:
            uncertainty = None
            lifetime_uncertainty = None
    if len(results) >= 2:
        decision = decide(results, resource_status=resource_status, guardrail_pct=project.get("guardrail_pct", 2), failed_candidates=failures,
                          geometry_confidence=project.get("geometry_confidence", "screening_assumptions"))
    else:
        decision = {"status": "INSUFFICIENT_EVIDENCE", "label": "Insufficient evidence", "headline": "Calculation failed: fewer than two successful candidates. No ranking available.",
                    "provisional_leader_module_id": None, "robust_winner_module_id": None, "reasons": [f["reason"] for f in failures], "failed_candidates": failures}
    if uncertainty:
        decision["uncertainty"] = uncertainty
        leader_id = decision.get("provisional_leader_module_id")
        pbest = uncertainty.get("probability_of_best_pct", {}).get(str(leader_id)) if leader_id else None
        decision["probability_of_best_pct"] = pbest
        # Probabilistic uncertainty never upgrades a weak evidence claim. It can only
        # make a close numerical recommendation more cautious.
        if pbest is not None and float(pbest) < float(project.get("no_clear_winner_probability_pct", 65.0)):
            decision["uncertainty_flag"] = "NO_CLEAR_WINNER_UNDER_UNCERTAINTY"
            decision.setdefault("reasons", []).append(
                f"The numerical leader is best in only {float(pbest):.1f}% of correlated Monte Carlo samples."
            )
        else:
            decision["uncertainty_flag"] = "SEPARATED_UNDER_SCREENING_UNCERTAINTY"
    if lifetime_uncertainty:
        decision["lifetime_uncertainty"] = lifetime_uncertainty
        life_leader = str(lifetime_uncertainty.get("leader_module_id"))
        decision["lifetime_probability_of_best_pct"] = lifetime_uncertainty.get("probability_of_best_pct", {}).get(life_leader)
        technical_leader = decision.get("provisional_leader_module_id")
        if technical_leader and life_leader != str(technical_leader):
            decision.setdefault("reasons", []).append(
                "The correlated lifetime uncertainty analysis changes the numerical leader; no strong technology claim is allowed."
            )
            decision["uncertainty_flag"] = "LIFETIME_LEADER_CHANGE"

    economics = {"status": "disabled_missing_real_quotes", "currency": project.get("currency", "USD"), "switching_threshold": None}
    if len(results) >= 2 and not failures:
        try:
            # Numeric kernel uses same-currency values. Public contract uses the declared currency; no FX conversion.
            quoted = modules.copy()
            if project.get("currency") == "EUR": quoted["quote_usd_w"] = quoted.get("quote_eur_w", np.nan)
            switch = switching_point_table(results, quoted, project["baseline_module_id"],
                energy_value_usd_kwh=project["energy_value_per_kwh"], discount_rate_pct=project["discount_rate_pct"],
                area_bos_usd_m2=project["area_bos_per_m2"], years=project["target_lifetime_years"],
                common_degradation_pct_year=project["common_degradation_pct_year"], allow_screening_sensitivity=False)
            switch.columns = [c.replace("usd", "currency") for c in switch.columns]
            economics.update(status="available_sensitivity", switching_threshold=switch.to_dict("records"))
            artifacts["Switching-threshold.csv"] = export_csv(switch)
        except KeyError:
            economics["reason"] = "Add a baseline module, a real supplier quote, and the declared financial inputs to enable procurement economics."
        except ValueError as exc: economics["reason"] = str(exc)
    # Primary procurement decision: when real quotes are available, maximize modeled
    # lifetime economic value among evidence/qualification-eligible products. Without
    # quotes, retain the technical leader and explicitly label the basis.
    decision["decision_basis"] = "technical_lifetime_performance_screening"
    decision["procurement_recommendation_module_id"] = None
    if economics.get("switching_threshold"):
        ef = pd.DataFrame(economics["switching_threshold"])
        col = "net_lifetime_value_index_currency_per_w" if "net_lifetime_value_index_currency_per_w" in ef.columns else "net_lifetime_value_index_usd_per_w"
        if col in ef.columns:
            vals = pd.to_numeric(ef[col], errors="coerce")
            ok = ef.get("economic_decision_eligible", pd.Series(False, index=ef.index)).astype(bool) & np.isfinite(vals)
            if ok.any():
                winner = ef.loc[ok].assign(_v=vals[ok]).sort_values("_v", ascending=False).iloc[0]
                decision["decision_basis"] = "maximum_site_specific_lifetime_economic_value_subject_to_evidence_gates"
                decision["procurement_recommendation_module_id"] = str(winner["module_id"])
                decision["procurement_net_value_index_currency_per_w"] = float(winner[col])

    candidate_results = []
    econ_lookup = {}
    if economics.get("switching_threshold"):
        econ_lookup = {str(x.get("module_id")): x for x in economics["switching_threshold"]}
    for _, module in modules.iterrows():
        row = results[results.module_id == module.module_id] if not results.empty else pd.DataFrame()
        fail = next((f for f in failures if f["module_id"] == module.module_id), None)
        mid = str(module.module_id)
        metrics = row.iloc[0].to_dict() if len(row) else {}
        q = qualification_records.get(mid, {})
        ev = evidence_records.get(mid, {})
        trace = build_candidate_trace(project, metrics, q, ev, econ_lookup.get(mid, {})) if len(row) else {}
        warning_list = [fail["reason"]] if fail else list(q.get("reasons", [])) + list(ev.get("gaps", []))
        candidate_results.append({"module_id": module.module_id, "manufacturer": module.manufacturer, "model": module.model, "technology": module.technology_label,
            "simulation_status": "failed" if fail else "completed", "metrics": metrics,
            "decision_eligible": bool(row.iloc[0].get("decision_eligible", False)) if len(row) else False,
            "qualification": q, "evidence": ev, "decision_trace": trace,
            "model_path": str(row.iloc[0].get("electrical_model", "unavailable")) if len(row) else "unavailable",
            "eligibility_reasons": [fail["reason"]] if fail else [str(row.iloc[0].get("model_evidence_level", "missing"))] + list(q.get("reasons", [])),
            "resource_status": resource_status, "economics_status": economics["status"],
            "warnings": warning_list, "inputs": module.to_dict(), "parameter_provenance": [
                {"parameter": k, "value": module.get(k), "unit": unit, "source": module.get("source_url"),
                 "evidence_level": "B_manufacturer_product_specific", "reviewer_state": "not_independently_reverified_in_this_release",
                 "parameter_release": versions["parameter_release"], "decision_relevant": True}
                for k, unit in {"pmax_w":"W", "vmp_v":"V", "imp_a":"A", "voc_v":"V", "isc_a":"A",
                   "module_area_m2":"m2", "gamma_pmax_pct_c":"%/C", "cells_in_series":"count"}.items()]})
    monthly, lifetime = [], []
    if hours:
        hourly = pd.concat(hours, ignore_index=True)
        artifacts["Hourly-physics.csv"] = export_csv(hourly)
        h = hourly.assign(month=pd.to_datetime(hourly.timestamp, utc=True).dt.month)
        h["energy_kwh_kwp"] = h.specific_power_kw_per_kwp * h.days_weight
        monthly = h.groupby(["module_id", "month"], as_index=False).energy_kwh_kwp.sum().to_dict("records")
    curve = common_degradation_curve(project["common_degradation_pct_year"], project["target_lifetime_years"])
    for summary in summaries:
        for _, year in curve.iterrows(): lifetime.append({"module_id": summary["module_id"], "year": int(year.year), "energy_kwh_kwp": summary["annual_yield_kwh_kwp"] * year.annual_energy_retention_scenario_pct / 100})
    gates = {"software_runtime": "PASS" if not failures else "FAIL", "numerical_implementation": "PASS" if not failures else "FAIL",
             "climate_resource_validation": "PASS" if resource_status == "adequate" else "PENDING",
             "c_si_module_model_validation": "PENDING", "cross_technology_validation": "PENDING",
             "iec_measured_data_validation": "PENDING", "decision_logic": "PASS", "economics": "PASS" if economics["switching_threshold"] else "PENDING",
             "historical_epc_replay": "PENDING", "bankability": "NOT_CLAIMED",
             "reference_iec_electrical_layer": "PASS" if reference_validation else "PENDING"}
    result = clean({"schema_version": "3.0", "run_id": run_id, "status": "completed" if len(results) >= 2 else "failed",
                   "workspace_id": "local", "project": project, "site": {**site, "latitude": project["latitude"], "longitude": project["longitude"], "timezone": "UTC", "timezone_basis": "calculation time standard", "exposure": site_exposure},
                   "versions": versions, "resource": resource, "candidates": candidate_results, "decision": decision,
                   "uncertainty": uncertainty, "lifetime_uncertainty": lifetime_uncertainty,
                   "economics": economics, "validation_gates": gates, "reference_validation": reference_validation, "monthly": monthly, "lifetime": lifetime, "stress": stress,
                   "limitations": LIMITATIONS, "created_at": datetime.now(timezone.utc).isoformat()})
    result = json.loads(json_bytes(result))
    artifacts["Comparison.csv"] = export_csv(results)
    from src.pilot_report import render_report
    artifacts["Decision.html"] = render_report(result).encode("utf-8")
    artifacts["START-HERE.md"] = f"# Solaryn\n\nOpen Decision.html. Result.json is the authoritative result.\n\n{decision['headline']}\n\nRun: {run_id}\nInputs and hashes are included. No bankability claim.\n".encode()
    store.publish(result, artifacts)
    return store.read(run_id)
