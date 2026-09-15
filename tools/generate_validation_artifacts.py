from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_fetchers import (
    fetch_nasa_power_hourly_dataframe,
    fetch_pvgis_hourly_dataframe,
    pvlib_azimuth_to_pvgis_aspect,
)
from src.module_iv_engine import cec_stc_fit_residuals
from src.module_iv_engine import simulate_module_hourly
from src.module_offer_io import load_module_offer_csv
from src.pvlib_pipeline import nasa_hourly_to_pvlib_weather
from src.lifetime_engine import add_lifetime_metrics
from src.epc_decision import poc_validation_decision
from src.benchmark_regression import (
    RIYADH_THREE_CANDIDATE_IDS,
    candidate_set_sha256,
)
from src.outdoor_validation import validate_iec61853_pmax_layer


LATITUDE = 24.7136
LONGITUDE = 46.6753
YEAR = 2020
TILT_DEG = 25.0
AZIMUTH_DEG = 180.0
ALBEDO = 0.20


def resource_benchmark(nasa: pd.DataFrame, weather: pd.DataFrame, pvgis: pd.DataFrame) -> pd.DataFrame:
    nasa_month = pd.DatetimeIndex(pd.to_datetime(nasa["time_utc"], utc=True)).month
    weather_month = pd.DatetimeIndex(pd.to_datetime(weather["time_utc"], utc=True)).month
    pvgis_month = pd.DatetimeIndex(pd.to_datetime(pvgis["date"])).month
    rows = []
    for month in range(1, 13):
        nmask = nasa_month == month
        wmask = weather_month == month
        pmask = pvgis_month == month
        solaryn_poa = float(pd.to_numeric(weather.loc[wmask, "poa_w_m2"], errors="coerce").fillna(0).sum() / 1000.0)
        pvgis_poa = float(pd.to_numeric(pvgis.loc[pmask, "poa_w_m2"], errors="coerce").fillna(0).sum() / 1000.0)
        rows.append({
            "month": month,
            "nasa_ghi_kwh_m2": float(pd.to_numeric(nasa.loc[nmask, "ALLSKY_SFC_SW_DWN"], errors="coerce").fillna(0).sum() / 1000.0),
            "nasa_dni_kwh_m2": float(pd.to_numeric(nasa.loc[nmask, "ALLSKY_SFC_SW_DNI"], errors="coerce").fillna(0).sum() / 1000.0),
            "nasa_dhi_kwh_m2": float(pd.to_numeric(nasa.loc[nmask, "ALLSKY_SFC_SW_DIFF"], errors="coerce").fillna(0).sum() / 1000.0),
            "solaryn_poa_kwh_m2": solaryn_poa,
            "pvgis_poa_kwh_m2": pvgis_poa,
            "absolute_difference_kwh_m2": solaryn_poa - pvgis_poa,
            "percentage_difference_pct": 100.0 * (solaryn_poa - pvgis_poa) / max(abs(pvgis_poa), 1e-9),
            "nasa_hour_count": int(nmask.sum()),
            "pvgis_hour_count": int(pmask.sum()),
            "year": YEAR,
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "tilt_deg": TILT_DEG,
            "azimuth_deg": AZIMUTH_DEG,
            "nasa_time_standard": "UTC",
            "solaryn_transposition_model": "perez-driesse",
            "pvgis_horizon": "enabled",
        })
    out = pd.DataFrame(rows)
    annual = {
        "month": "ANNUAL",
        "nasa_ghi_kwh_m2": out["nasa_ghi_kwh_m2"].sum(),
        "nasa_dni_kwh_m2": out["nasa_dni_kwh_m2"].sum(),
        "nasa_dhi_kwh_m2": out["nasa_dhi_kwh_m2"].sum(),
        "solaryn_poa_kwh_m2": out["solaryn_poa_kwh_m2"].sum(),
        "pvgis_poa_kwh_m2": out["pvgis_poa_kwh_m2"].sum(),
        "nasa_hour_count": out["nasa_hour_count"].sum(),
        "pvgis_hour_count": out["pvgis_hour_count"].sum(),
        "year": YEAR,
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "tilt_deg": TILT_DEG,
        "azimuth_deg": AZIMUTH_DEG,
        "nasa_time_standard": "UTC",
        "solaryn_transposition_model": "perez-driesse",
        "pvgis_horizon": "enabled",
    }
    annual["absolute_difference_kwh_m2"] = annual["solaryn_poa_kwh_m2"] - annual["pvgis_poa_kwh_m2"]
    annual["percentage_difference_pct"] = 100.0 * annual["absolute_difference_kwh_m2"] / annual["pvgis_poa_kwh_m2"]
    return pd.concat([out, pd.DataFrame([annual])], ignore_index=True)


def module_fit_residuals(modules: pd.DataFrame) -> pd.DataFrame:
    selected = modules[modules["manufacturer"].isin(["JinkoSolar", "LONGi"])]
    return pd.DataFrame([cec_stc_fit_residuals(row) for _, row in selected.iterrows()])


def data_provenance(modules: pd.DataFrame) -> pd.DataFrame:
    units = {
        "pmax_w": "W", "vmp_v": "V", "imp_a": "A", "voc_v": "V", "isc_a": "A",
        "alpha_isc_pct_c": "%/C", "beta_voc_pct_c": "%/C", "gamma_pmax_pct_c": "%/C",
        "cells_in_series": "count", "module_area_m2": "m2", "module_efficiency_pct": "%",
        "first_year_retention_pct": "%", "annual_warranty_degradation_pct_year": "%/year",
        "warranty_years": "years", "quote_usd_w": "USD/W",
    }
    parameters = list(units)
    rows = []
    for _, module in modules.iterrows():
        for parameter in parameters:
            value = module.get(parameter, np.nan)
            rows.append({
                "module_id": module["module_id"],
                "parameter": parameter,
                "value": "" if pd.isna(value) else value,
                "unit": units[parameter],
                "source": module.get("source_url", ""),
                "source_type": "manufacturer_datasheet_seed" if parameter != "quote_usd_w" else "supplier_quote_user_input",
                "evidence_level": module.get("evidence_status", "not_documented"),
                "date_version": "SOLARYN_V9.2.1_packaged_seed_2026-08-25",
                "used_in_commercial_decision": "yes" if parameter != "quote_usd_w" or not pd.isna(value) else "no_missing_disables_economics",
            })
    for parameter, value, unit in [
        ("latitude", LATITUDE, "degree"), ("longitude", LONGITUDE, "degree"),
        ("reference_year", YEAR, "year"), ("tilt", TILT_DEG, "degree"),
        ("azimuth", AZIMUTH_DEG, "degree"), ("albedo", ALBEDO, "ratio"),
        ("common_soiling_loss", 2.0, "%"), ("common_degradation_scenario", 0.5, "%/year"),
        ("poc_decision_guardrail", 2.0, "%"),
    ]:
        rows.append({
            "module_id": "PROJECT_RIYADH_2020", "parameter": parameter, "value": value,
            "unit": unit, "source": "user_frozen_benchmark_assumption", "source_type": "declared_project_assumption",
            "evidence_level": "scenario_or_user_input", "date_version": "benchmark_2026-08-25",
            "used_in_commercial_decision": "yes",
        })
    return pd.DataFrame(rows)


def riyadh_benchmark_results(weather: pd.DataFrame, modules: pd.DataFrame) -> pd.DataFrame:
    summaries = []
    for _, module in modules.iterrows():
        summary, _ = simulate_module_hourly(
            weather, module, common_soiling_loss_pct=2.0, root=ROOT
        )
        summaries.append(summary)
    all_results = add_lifetime_metrics(
        pd.DataFrame(summaries), modules, years=25, common_degradation_pct_year=0.5
    )
    rows = []
    for case_name, ids in [
        ("three_candidate", RIYADH_THREE_CANDIDATE_IDS),
        ("four_candidate", tuple(modules.module_id)),
    ]:
        selected_modules = modules[modules.module_id.isin(ids)].copy()
        selected_results = all_results[all_results.module_id.isin(ids)].copy()
        decision = poc_validation_decision(selected_results, uncertainty_guardrail_pct=2.0)
        for _, result in selected_results.iterrows():
            rows.append({
                "case": case_name,
                "candidate_set_sha256": candidate_set_sha256(selected_modules),
                "candidate_ids": "|".join(sorted(selected_modules.module_id.astype(str))),
                "module_id": result["module_id"],
                "manufacturer": result["manufacturer"],
                "model": result["model"],
                "annual_yield_kwh_kwp": result["annual_yield_kwh_kwp"],
                "decision_eligible": result["decision_eligible"],
                "electrical_model": result["electrical_model"],
                "nominal_leader_id": decision["winner_module_id"],
                "robust_winner_id": decision["robust_winner_module_id"] or "",
                "annual_lead_over_second_pct": decision["annual_lead_over_second_pct"],
                "robust_status": decision["robust_status"],
                "year": YEAR,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "tilt_deg": TILT_DEG,
                "azimuth_deg": AZIMUTH_DEG,
            })
    return pd.DataFrame(rows)


def main() -> None:
    modules = load_module_offer_csv(ROOT / "data/raw/module_candidate_master.csv")
    nasa = fetch_nasa_power_hourly_dataframe(
        LATITUDE, LONGITUDE, f"{YEAR}-01-01", f"{YEAR}-12-31"
    )
    weather = nasa_hourly_to_pvlib_weather(
        nasa, LATITUDE, LONGITUDE, TILT_DEG, AZIMUTH_DEG, ALBEDO
    )
    pvgis = fetch_pvgis_hourly_dataframe(
        LATITUDE, LONGITUDE, YEAR, YEAR, angle=TILT_DEG,
        aspect=pvlib_azimuth_to_pvgis_aspect(AZIMUTH_DEG),
    )
    resource_benchmark(nasa, weather, pvgis).to_csv(ROOT / "RESOURCE_BENCHMARK.csv", index=False)
    riyadh_benchmark_results(weather, modules).to_csv(
        ROOT / "outputs/RIYADH_LIVE_BENCHMARK_RESULTS.csv", index=False
    )
    module_fit_residuals(modules).to_csv(ROOT / "MODULE_FIT_RESIDUALS.csv", index=False)
    data_provenance(modules).to_csv(ROOT / "DATA_PROVENANCE.csv", index=False)
    dvp_root = ROOT / "validation/external/iea_pvps_task13_supsi_csi"
    if dvp_root.exists():
        measured_summary, measured_monthly, measured_points = validate_iec61853_pmax_layer(
            dvp_root / "data",
            dvp_root / "IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv",
        )
        pd.DataFrame([measured_summary]).to_csv(ROOT / "MEASURED_VALIDATION_RESULTS.csv", index=False)
        measured_monthly.to_csv(ROOT / "outputs/DVP_OUTDOOR_VALIDATION_MONTHLY.csv", index=False)
        measured_points.to_csv(ROOT / "outputs/DVP_OUTDOOR_VALIDATION_POINTS.csv", index=False)


if __name__ == "__main__":
    main()
