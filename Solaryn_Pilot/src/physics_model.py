from __future__ import annotations
import math
import pandas as pd
from src.climate_physics import simulate_site_technology
from src.system_physics import annual_system_from_specific_dc
from src.uncertainty_engine import monte_carlo_yield

K_B_OVER_Q = 8.617333262e-5  # V/K
T_REF_K = 298.15
PIN_MW_CM2 = 100.0  # STC incident power density

COST_SCORE = {"low": 90.0, "medium": 70.0, "high": 45.0}
TOXICITY_SCORE = {"low": 90.0, "medium": 65.0, "high": 35.0}
STATUS_SCORE = {
    "commercial": 95.0,
    "commercial_niche": 75.0,
    "specialty_space": 60.0,
    "pilot": 55.0,
    "pilot_research": 45.0,
    "research_niche": 35.0,
    "research": 25.0,
}

def bounded(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    if pd.isna(value):
        return lo
    return max(lo, min(hi, float(value)))

def normalize(value: float, lo: float, hi: float, inverse: bool = False) -> float:
    if hi == lo:
        score = 50.0
    else:
        score = (float(value) - lo) / (hi - lo) * 100.0
    score = bounded(score)
    return 100.0 - score if inverse else score

def optical_penetration_depth_um(absorption_coefficient_cm1: float) -> float:
    """1/alpha converted from cm to um: depth_um = 10000 / alpha_cm^-1."""
    alpha = max(float(absorption_coefficient_cm1), 1e-12)
    return 10000.0 / alpha

def diffusivity_cm2_s(mobility_cm2_vs: float, temperature_k: float = T_REF_K) -> float:
    """Einstein relation: D = mu * kT/q."""
    return float(mobility_cm2_vs) * K_B_OVER_Q * temperature_k

def diffusion_length_um(mobility_cm2_vs: float, lifetime_ns: float, temperature_k: float = T_REF_K) -> float:
    """L = sqrt(D*tau), converted from cm to um."""
    tau_s = max(float(lifetime_ns), 0.0) * 1e-9
    D = diffusivity_cm2_s(mobility_cm2_vs, temperature_k)
    return math.sqrt(max(D * tau_s, 0.0)) * 1e4

def absorption_fraction(alpha_cm1: float, thickness_um: float) -> float:
    """Beer-Lambert absorption proxy A = 1-exp(-alpha*d)."""
    thickness_cm = max(float(thickness_um), 0.0) * 1e-4
    return bounded((1.0 - math.exp(-max(float(alpha_cm1), 0.0) * thickness_cm)) * 100.0)

def collection_efficiency_score(diffusion_length_um_value: float, thickness_um: float) -> float:
    """Simplified carrier collection proxy. Thin-film direct absorbers saturate fast; thick Si needs long L."""
    thickness = max(float(thickness_um), 1e-9)
    ratio = float(diffusion_length_um_value) / thickness
    return bounded(100.0 * (1.0 - math.exp(-3.0 * ratio)))

def stc_physics_features(tech: pd.Series) -> dict:
    mu_avg = (float(tech["electron_mobility_cm2Vs"]) + float(tech["hole_mobility_cm2Vs"])) / 2.0
    tau_ns = float(tech["carrier_lifetime_ns"])
    L_um = diffusion_length_um(mu_avg, tau_ns)
    alpha = float(tech["absorption_coefficient_cm-1"])
    thickness = float(tech["absorber_thickness_um"])
    abs_score = absorption_fraction(alpha, thickness)
    coll_score = collection_efficiency_score(L_um, thickness)
    voc_loss_v = max(float(tech["bandgap_eV"]) - float(tech["voc_typical_V"]), 0.0)
    mu_tau = mu_avg * tau_ns * 1e-9
    recombination_factor = float(tech["defect_density_cm-3"]) / max(tau_ns, 1e-12)
    recombination_score = normalize(math.log10(max(recombination_factor, 1.0)), 3, 14, inverse=True)
    physics_quality_score = (
        0.25 * abs_score +
        0.25 * coll_score +
        0.20 * recombination_score +
        0.15 * normalize(mu_tau, 1e-5, 1.0) +
        0.15 * normalize(voc_loss_v, 0.05, 1.0, inverse=True)
    )
    return {
        "optical_penetration_depth_um": round(optical_penetration_depth_um(alpha), 6),
        "diffusion_length_um_model": round(L_um, 4),
        "absorption_fraction_pct": round(abs_score, 2),
        "collection_efficiency_score": round(coll_score, 2),
        "voc_loss_V": round(voc_loss_v, 3),
        "mu_tau_product_cm2_V": round(mu_tau, 8),
        "recombination_factor": round(recombination_factor, 3),
        "recombination_score": round(recombination_score, 2),
        "physics_quality_score": round(bounded(physics_quality_score), 2),
    }

def site_adjusted_performance(site: pd.Series, tech: pd.Series, weather: pd.DataFrame | None = None) -> dict:
    """Return corrected site performance plus preserved material/device diagnostics.

    Material metrics remain in Solaryn because they are part of the long-term
    material/device intelligence vision. They are diagnostic in the commercial screening application
    and do not directly force the technology ranking.
    """
    p = stc_physics_features(tech)
    climate_perf = simulate_site_technology(site, tech, weather=weather)
    annual_yield=float(climate_perf["annual_yield_kwh_kwp"])
    system_perf = annual_system_from_specific_dc(
        annual_yield,
        dc_ac_ratio=float(site.get("dc_ac_ratio", 1.25)),
        mismatch_loss_pct=float(site.get("mismatch_loss_pct", 1.5)),
        dc_wiring_loss_pct=float(site.get("dc_wiring_loss_pct", 1.5)),
        inverter_efficiency=float(site.get("inverter_efficiency", 0.975)),
        transformer_loss_pct=float(site.get("transformer_loss_pct", 1.0)),
        ac_wiring_loss_pct=float(site.get("ac_wiring_loss_pct", 0.5)),
        availability_pct=float(site.get("availability_pct", 99.0)),
        curtailment_pct=float(site.get("curtailment_pct", 0.0)),
        clipping_loss_pct=(None if pd.isna(site.get("clipping_loss_pct", pd.NA)) else float(site.get("clipping_loss_pct"))),
    )
    evidence_sigma = 3.0 if bool(climate_perf.get("electrical_model_measured", False)) else 5.0
    uq = monte_carlo_yield(
        system_perf["annual_meter_specific_energy_kwh_kwp"],
        uncertainty_pct={"module_model": evidence_sigma},
        n=int(site.get("uncertainty_samples", 5000)),
        seed=int(site.get("uncertainty_seed", 95)),
    )
    degradation=float(climate_perf["site_degradation_pct_year"])
    degradation_factor_25y=sum((1.0-degradation/100.0)**(y-1) for y in range(1,26))/25.0
    lifetime_energy_index=annual_yield*degradation_factor_25y
    ghi=max(float(site.get("ghi_kwh_m2_year",site.get("GHI_kWh_m2_year",1600.0))),1e-9)
    performance_ratio=annual_yield/ghi
    operating_efficiency_proxy=float(tech["efficiency_commercial_percent"])*performance_ratio
    return {
        **p,
        "cell_temperature_C": climate_perf["avg_cell_temperature_C"],
        "p95_cell_temperature_C": climate_perf["p95_cell_temperature_C"],
        "temperature_effect_pct": climate_perf["temperature_effect_pct"],
        "temperature_loss_pct": climate_perf["temperature_loss_pct"],
        "temperature_gain_pct": climate_perf["temperature_gain_pct"],
        "spectral_effect_pct": climate_perf["spectral_effect_pct"],
        "mean_spectral_factor": climate_perf["mean_spectral_factor"],
        "spectral_model_applied": climate_perf["spectral_model_applied"],
        "spectral_model_note": climate_perf["spectral_model_note"],
        "aoi_effect_pct": climate_perf.get("aoi_effect_pct", 0.0),
        "mean_iam_factor": climate_perf.get("mean_iam_factor", 1.0),
        "aoi_model_applied": climate_perf.get("aoi_model_applied", False),
        "aoi_model_note": climate_perf.get("aoi_model_note", ""),
        "thermal_model_basis": climate_perf.get("thermal_model_basis", "unknown"),
        "electrical_model_basis": climate_perf.get("electrical_model_basis", "unknown"),
        "electrical_model_measured": climate_perf.get("electrical_model_measured", False),
        "iec_measured_points": climate_perf.get("iec_measured_points", 0),
        "estimated_operating_efficiency_pct": round(operating_efficiency_proxy,2),
        "site_performance_factor": round(performance_ratio,3),
        "site_adjusted_efficiency_pct": round(operating_efficiency_proxy,2),
        "soiling_loss_pct": climate_perf["annual_soiling_loss_pct"],
        "adjusted_degradation_pct_year": round(degradation,3),
        "database_degradation_pct_year": climate_perf.get("database_degradation_pct_year", degradation),
        "degradation_acceleration_factor": climate_perf["degradation_acceleration_factor"],
        "degradation_stress_factor": climate_perf["degradation_stress_factor"],
        "degradation_rate_basis": climate_perf["degradation_rate_basis"],
        "performance_ratio_model": round(performance_ratio,3),
        "moisture_sensitivity_score": round(float(tech.get("moisture_sensitivity_score",2.0)),2),
        "uv_stability_score": round(float(tech.get("uv_stability_score",7.0)),2),
        "ion_migration_score": round(float(tech.get("ion_migration_score",0.0)),2),
        "phase_stability_score": round(float(tech.get("phase_stability_score",7.0)),2),
        "energy_yield_index": round(annual_yield,2),
        "annual_yield_kwh_kwp": round(annual_yield,2),
        **system_perf,
        "p50_meter_specific_energy_kwh_kwp": uq["p50_kwh_kwp"],
        "p90_meter_specific_energy_kwh_kwp": uq["p90_kwh_kwp"],
        "yield_uncertainty_std_pct": uq["std_pct"],
        "uncertainty_model_basis": uq["basis"],
        "clean_annual_yield_kwh_kwp": climate_perf["clean_annual_yield_kwh_kwp"],
        "lifetime_energy_index_25y": round(lifetime_energy_index,2),
        "uv_dose_proxy": climate_perf["uv_dose_proxy"],
        "weather_coverage_days": climate_perf["weather_coverage_days"],
        "hour_coverage_fraction": climate_perf["hour_coverage_fraction"],
        "soiling_model_basis": climate_perf["soiling_model_basis"],
    }

