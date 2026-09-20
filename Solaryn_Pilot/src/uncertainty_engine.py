from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


DEFAULT_SIGMA_PCT = {
    "resource": 3.0,
    "transposition": 1.5,
    "temperature": 1.0,
    "module_model": 5.0,
    "soiling": 2.0,
    "system_losses": 1.5,
    "degradation": 0.20,
    "availability": 1.0,
}


@dataclass(frozen=True)
class DecisionUncertaintyPolicy:
    """Governance thresholds only; these values do not modify modeled means."""

    robust_probability_pct: float = 80.0
    probable_probability_pct: float = 65.0
    robust_max_expected_regret_pct: float = 0.50


def _positive_lognormal_multiplier(
    rng: np.random.Generator, sigma_pct: float, n: int
) -> np.ndarray:
    """Return a positive mean-one multiplier with approximately ``sigma_pct`` CV."""
    if not np.isfinite(float(sigma_pct)) or float(sigma_pct) < 0:
        raise ValueError("Uncertainty width must be finite and non-negative.")
    cv = float(sigma_pct) / 100.0
    if cv == 0:
        return np.ones(int(n), dtype=float)
    sigma_log = np.sqrt(np.log1p(cv * cv))
    mu_log = -0.5 * sigma_log * sigma_log
    return rng.lognormal(mean=mu_log, sigma=sigma_log, size=int(n))


def monte_carlo_yield(
    base_energy_kwh_kwp: float,
    uncertainty_pct: Mapping[str, float] | None = None,
    n: int = 10_000,
    seed: int = 95,
    downside_skew_pct: float = 0.8,
) -> dict:
    """Propagate single-candidate annual-yield uncertainty with nonnegative draws."""
    if int(n) < 100:
        raise ValueError("n must be at least 100 samples.")
    base = float(base_energy_kwh_kwp)
    if not np.isfinite(base) or base < 0:
        raise ValueError("base_energy_kwh_kwp must be finite and non-negative.")

    u = dict(DEFAULT_SIGMA_PCT)
    u.update(dict(uncertainty_pct or {}))
    rng = np.random.default_rng(seed)
    mult = np.ones(int(n), dtype=float)
    for name, sigma in u.items():
        if name == "degradation":
            # degradation has different units (%/year) and is not an annual-yield multiplier
            continue
        mult *= _positive_lognormal_multiplier(rng, float(sigma), int(n))

    downside = rng.exponential(max(float(downside_skew_pct), 0.0) / 100.0, int(n))
    samples = np.maximum(base * mult * np.maximum(1.0 - downside, 0.0), 0.0)
    p10, p25, p50, p75, p90 = np.percentile(samples, [10, 25, 50, 75, 90])
    return {
        "p50_kwh_kwp": round(float(p50), 2),
        "p90_kwh_kwp": round(float(p10), 2),
        "p75_exceedance_kwh_kwp": round(float(p25), 2),
        "p25_exceedance_kwh_kwp": round(float(p75), 2),
        "p10_exceedance_kwh_kwp": round(float(p90), 2),
        "mean_kwh_kwp": round(float(samples.mean()), 2),
        "std_pct": round(float(samples.std() / max(samples.mean(), 1e-9) * 100), 2),
        "n_samples": int(n),
        "uncertainty_components_pct": u,
        "basis": "Monte Carlo propagation; P90 is the 10th percentile (90% exceedance)",
    }


def _finite_positive(row: Mapping, *keys: str) -> float | None:
    for key in keys:
        try:
            value = float(row.get(key, np.nan))
        except (TypeError, ValueError):
            continue
        if np.isfinite(value) and value > 0:
            return value
    return None


def candidate_model_sigma_pct(row: Mapping, default_screening_sigma_pct: float = 5.0) -> float:
    """Return candidate-model uncertainty without evidence-grade winner bias.

    Product-specific empirical validation uncertainty is used when present. Otherwise
    every candidate receives the same declared screening width. Evidence grade is still
    reported and can block a strong claim, but it does not receive an invented numerical
    uncertainty merely because it is grade A/B/C/D.
    """
    empirical = _finite_positive(
        row,
        "validated_model_sigma_pct",
        "model_validation_rmse_pct",
        "electrical_model_residual_sigma_pct",
        "measurement_uncertainty_pct",
    )

    explicit_common = _finite_positive(row, "screening_model_sigma_pct")
    if empirical is not None:
        electrical = float(empirical)
    elif explicit_common is not None:
        electrical = float(explicit_common)
    else:
        electrical = float(default_screening_sigma_pct)

    if not np.isfinite(electrical) or electrical <= 0:
        raise ValueError("default_screening_sigma_pct must be finite and positive.")

    # Only independently quantified residual components are added. We deliberately do
    # not invent technology- or evidence-grade-specific thermal/rear uncertainty widths.
    thermal_empirical = _finite_positive(row, "thermal_validation_rmse_pct", "thermal_model_sigma_pct")
    rear_empirical = _finite_positive(row, "rear_irradiance_validation_sigma_pct", "bifacial_model_sigma_pct")
    components = [electrical]
    if thermal_empirical is not None:
        components.append(float(thermal_empirical))
    if rear_empirical is not None:
        components.append(float(rear_empirical))
    return float(np.sqrt(np.sum(np.square(components))))


def _prepare_empirical_scenarios(
    shared_scenarios: pd.DataFrame | None,
    candidate_ids: list[str],
) -> pd.DataFrame | None:
    """Return finite year/site scenarios aligned to every compared candidate."""
    if shared_scenarios is None or shared_scenarios.empty:
        return None
    missing = [mid for mid in candidate_ids if mid not in shared_scenarios.columns]
    if missing:
        raise ValueError(f"shared_scenarios is missing candidate columns: {missing}")
    scen = shared_scenarios[candidate_ids].apply(pd.to_numeric, errors="coerce")
    scen = scen.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how="any")
    if len(scen) < 2:
        return None
    if (scen < 0).any().any():
        raise ValueError("shared_scenarios cannot contain negative energy values.")
    return scen


def compare_candidates_correlated(
    results: pd.DataFrame,
    value_col: str = "annual_yield_kwh_kwp",
    *,
    shared_resource_sigma_pct: float = 3.0,
    candidate_sigma_pct: Mapping[str, float] | None = None,
    shared_scenarios: pd.DataFrame | None = None,
    default_candidate_sigma_pct: float = 5.0,
    n: int = 20_000,
    seed: int = 95,
) -> dict:
    """Compare co-located candidates using shared resource uncertainty.

    The same resource draw is applied to all candidates in every Monte Carlo sample.
    This is essential for procurement comparisons because weather uncertainty is common
    to every module at one site. Candidate-specific residuals are independent only when
    product-specific model validation supports them; otherwise all candidates use the
    same declared screening residual width.
    """
    if value_col not in results.columns:
        raise ValueError(f"Missing comparison column: {value_col}")
    if "module_id" not in results.columns:
        raise ValueError("results must contain module_id.")
    if int(n) < 100:
        raise ValueError("n must be at least 100 samples.")

    frame = results.sort_values("module_id").reset_index(drop=True).copy()
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    frame = frame[np.isfinite(frame[value_col]) & (frame[value_col] >= 0)].reset_index(drop=True)
    if len(frame) < 2:
        raise ValueError("At least two finite candidates are required for ranking uncertainty.")

    ids = frame["module_id"].astype(str).tolist()
    base = frame[value_col].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    empirical = _prepare_empirical_scenarios(shared_scenarios, ids)

    if empirical is not None:
        year_idx = rng.integers(0, len(empirical), size=int(n))
        shared_base = empirical.to_numpy(dtype=float)[year_idx, :].T
        annual_mean = empirical.mean(axis=0).to_numpy(dtype=float)
        scale = np.divide(base, annual_mean, out=np.ones_like(base), where=annual_mean > 0)
        shared_base = shared_base * scale[:, None]
        avg_year_energy = empirical.mean(axis=1).to_numpy(dtype=float)
        resource_cv_pct = float(
            np.std(avg_year_energy, ddof=1) / max(abs(np.mean(avg_year_energy)), 1e-12) * 100.0
        )
        method = "empirical shared interannual resource scenarios + candidate validation residuals"
    else:
        shared = _positive_lognormal_multiplier(rng, shared_resource_sigma_pct, int(n))
        shared_base = base[:, None] * shared[None, :]
        resource_cv_pct = float(shared_resource_sigma_pct)
        method = "shared-resource correlated Monte Carlo + common screening residual unless validated"

    draws = []
    sigma_used: dict[str, float] = {}
    candidate_sigma_pct = dict(candidate_sigma_pct or {})
    for i, row in frame.iterrows():
        mid = str(row["module_id"])
        sigma = float(candidate_sigma_pct.get(
            mid, candidate_model_sigma_pct(row, default_screening_sigma_pct=default_candidate_sigma_pct)
        ))
        sigma_used[mid] = sigma
        own = _positive_lognormal_multiplier(rng, sigma, int(n))
        draws.append(shared_base[i] * own)
    mat = np.vstack(draws)

    tied = np.isclose(mat, mat.max(axis=0), rtol=1e-12, atol=1e-12)
    shares = tied / tied.sum(axis=0)
    sample_best = np.max(mat, axis=0)
    probabilities = {mid: float(shares[i].mean() * 100.0) for i, mid in enumerate(ids)}

    mean_values = mat.mean(axis=1)
    regret_abs = (sample_best[None, :] - mat).mean(axis=1)
    reference = max(float(sample_best.mean()), 1e-12)
    regrets_pct = {mid: float(regret_abs[i] / reference * 100.0) for i, mid in enumerate(ids)}

    p50 = {mid: float(np.percentile(mat[i], 50)) for i, mid in enumerate(ids)}
    p90 = {mid: float(np.percentile(mat[i], 10)) for i, mid in enumerate(ids)}
    leader_idx = int(np.argmax(mean_values))

    return {
        "probability_of_best_pct": probabilities,
        "expected_regret_pct": regrets_pct,
        "p50": p50,
        "p90": p90,
        "expected_value": {mid: float(mean_values[i]) for i, mid in enumerate(ids)},
        "leader_module_id": ids[leader_idx],
        "shared_resource_sigma_pct": resource_cv_pct,
        "resource_uncertainty_basis": "empirical_interannual" if empirical is not None else "declared_screening_prior",
        "candidate_model_sigma_pct": sigma_used,
        "n_samples": int(n),
        "method": method,
    }


def compare_lifetime_candidates_correlated(
    results: pd.DataFrame,
    *,
    annual_value_col: str = "annual_yield_kwh_kwp",
    years: int = 25,
    shared_resource_sigma_pct: float = 3.0,
    default_candidate_sigma_pct: float = 5.0,
    common_degradation_mean_pct_year: float = 0.50,
    common_degradation_sigma_pct_year: float = 0.20,
    n: int = 20_000,
    seed: int = 195,
) -> dict:
    """Correlated lifetime-energy comparison for co-located candidates.

    Shared weather/resource and the default degradation prior are sampled once per
    scenario and applied to every candidate. Candidate-specific degradation means or
    sigmas are honored only when upstream code explicitly supplies product-specific
    validated evidence columns. This prevents random independent weather or invented
    family degradation assumptions from manufacturing a winner.
    """
    if annual_value_col not in results.columns or "module_id" not in results.columns:
        raise ValueError("results must contain module_id and annual yield.")
    if int(years) < 1 or int(n) < 100:
        raise ValueError("years must be >=1 and n >=100.")

    frame = results.sort_values("module_id").reset_index(drop=True).copy()
    frame[annual_value_col] = pd.to_numeric(frame[annual_value_col], errors="coerce")
    frame = frame[np.isfinite(frame[annual_value_col]) & (frame[annual_value_col] >= 0)].reset_index(drop=True)
    if len(frame) < 2:
        raise ValueError("At least two finite candidates are required.")

    rng = np.random.default_rng(seed)
    ids = frame["module_id"].astype(str).tolist()
    base = frame[annual_value_col].to_numpy(dtype=float)
    shared_resource = _positive_lognormal_multiplier(rng, shared_resource_sigma_pct, int(n))

    common_mu = float(common_degradation_mean_pct_year)
    common_sd = float(common_degradation_sigma_pct_year)
    if not np.isfinite(common_mu) or common_mu < 0 or not np.isfinite(common_sd) or common_sd < 0:
        raise ValueError("Common degradation mean/sigma must be finite and non-negative.")
    shared_degradation = np.maximum(rng.normal(common_mu, common_sd, int(n)), 0.0) / 100.0

    year_axis = np.arange(int(years), dtype=float)
    lifetime_draws = []
    degradation_basis: dict[str, str] = {}
    candidate_sigma_used: dict[str, float] = {}

    for i, row in frame.iterrows():
        mid = ids[i]
        model_sigma = candidate_model_sigma_pct(row, default_screening_sigma_pct=default_candidate_sigma_pct)
        candidate_sigma_used[mid] = model_sigma
        annual_residual = _positive_lognormal_multiplier(rng, model_sigma, int(n))
        first_year = base[i] * shared_resource * annual_residual

        validated = str(row.get("degradation_evidence_status", "")).strip().lower() in {
            "field_validated", "validated_field", "measured_field", "independent_field"
        }
        mu = _finite_positive(row, "field_validated_degradation_pct_year") if validated else None
        sd = _finite_positive(row, "field_validated_degradation_sigma_pct_year") if validated else None
        if mu is not None:
            cand_sd = common_sd if sd is None else float(sd)
            degradation = np.maximum(rng.normal(float(mu), cand_sd, int(n)), 0.0) / 100.0
            degradation_basis[mid] = "product_specific_field_evidence"
        else:
            degradation = shared_degradation
            degradation_basis[mid] = "common_project_prior_shared_across_candidates"

        retention = np.power(1.0 - degradation[:, None], year_axis[None, :])
        lifetime = (first_year[:, None] * retention).sum(axis=1)
        lifetime_draws.append(lifetime)

    mat = np.vstack(lifetime_draws)
    tied = np.isclose(mat, mat.max(axis=0), rtol=1e-12, atol=1e-12)
    shares = tied / tied.sum(axis=0)
    probabilities = {mid: float(shares[i].mean() * 100.0) for i, mid in enumerate(ids)}
    expected = mat.mean(axis=1)
    leader_idx = int(np.argmax(expected))

    return {
        "probability_of_best_pct": probabilities,
        "p50_lifetime_kwh_kwp": {mid: float(np.percentile(mat[i], 50)) for i, mid in enumerate(ids)},
        "p90_lifetime_kwh_kwp": {mid: float(np.percentile(mat[i], 10)) for i, mid in enumerate(ids)},
        "expected_lifetime_kwh_kwp": {mid: float(expected[i]) for i, mid in enumerate(ids)},
        "leader_module_id": ids[leader_idx],
        "degradation_basis": degradation_basis,
        "candidate_model_sigma_pct": candidate_sigma_used,
        "shared_resource_sigma_pct": float(shared_resource_sigma_pct),
        "common_degradation_mean_pct_year": common_mu,
        "common_degradation_sigma_pct_year": common_sd,
        "n_samples": int(n),
        "method": "correlated lifetime Monte Carlo with shared weather and shared degradation prior unless validated product field evidence exists",
    }


def probability_of_best(
    energy_by_candidate: Mapping[str, float],
    sigma_pct_by_candidate: Mapping[str, float] | None = None,
    n: int = 20_000,
    seed: int = 95,
) -> dict[str, float]:
    """Compatibility helper for simple dictionary inputs."""
    frame = pd.DataFrame(
        [{"module_id": name, "annual_yield_kwh_kwp": value} for name, value in energy_by_candidate.items()]
    )
    comparison = compare_candidates_correlated(
        frame,
        candidate_sigma_pct=sigma_pct_by_candidate,
        n=n,
        seed=seed,
    )
    return {k: round(v, 2) for k, v in comparison["probability_of_best_pct"].items()}
