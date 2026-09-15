from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


DEFAULT_SIGMA_PCT = {
    "resource": 3.0,
    "transposition": 1.5,
    "temperature": 1.0,
    "module_model": 2.5,
    "soiling": 2.0,
    "system_losses": 1.5,
    "degradation": 1.5,
    "availability": 1.0,
}


@dataclass(frozen=True)
class DecisionUncertaintyPolicy:
    """Product-governance thresholds for recommendation labels.

    These thresholds are deliberately separated from the physics. They can be
    adjusted to match an EPC/client risk appetite without changing modeled mean
    energy. Robustness still requires passing evidence/resource gates in the
    decision engine.
    """

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
    for sigma in u.values():
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


def candidate_model_sigma_pct(row: Mapping) -> float:
    """Map evidence class to candidate-model uncertainty width, never to mean bias.

    The values are conservative screening priors. Where measured residuals are
    available, callers should pass those residual-derived sigmas explicitly.
    """
    level = str(row.get("model_evidence_level", "")).lower()
    electrical_model = str(row.get("electrical_model", "")).lower()
    if "module_specific_measured_matrix" in level or "iec61853" in electrical_model:
        electrical = 1.5
    elif "datasheet_fit_crystalline" in level or "cec_single_diode_datasheet_fit" in electrical_model:
        electrical = 3.5
    else:
        electrical = 8.0

    thermal_level = str(row.get("thermal_evidence_level", "")).lower()
    thermal = 0.75 if "module_specific" in thermal_level or "measured" in thermal_level else 1.5

    # Rear-side geometry is a candidate-specific modeling path. Do not alter the
    # mean as a hidden confidence bonus/penalty; only widen the screening prior.
    rear_active = bool(row.get("rear_irradiance_model_active", False))
    rear = 1.5 if rear_active and float(row.get("bifaciality_factor", 0.0) or 0.0) > 0 else 0.0
    return float(np.sqrt(electrical**2 + thermal**2 + rear**2))


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
    n: int = 20_000,
    seed: int = 95,
) -> dict:
    """Compare co-located candidates with correlated resource uncertainty.

    Preferred path: if at least two complete annual scenarios are supplied, each
    Monte-Carlo sample draws one *shared* historical resource year and applies that
    same year to every candidate. This preserves cross-candidate correlation and
    observed interannual variability. Candidate-model residuals are then applied
    independently because their electrical/thermal evidence differs.

    Fallback path: when multi-year scenarios are unavailable, a single shared
    lognormal resource multiplier is used for all candidates. In both paths,
    evidence quality affects distribution width rather than the predicted mean.
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
        shared_base = empirical.to_numpy(dtype=float)[year_idx, :].T  # candidates × samples
        annual_mean = empirical.mean(axis=0).to_numpy(dtype=float)
        # Preserve the current model's multi-year mean if caller's annual result and
        # scenario mean differ by rounding/weighting. Scaling is candidate-specific but
        # constant over samples and therefore does not destroy shared-year correlation.
        scale = np.divide(base, annual_mean, out=np.ones_like(base), where=annual_mean > 0)
        shared_base = shared_base * scale[:, None]
        avg_year_energy = empirical.mean(axis=1).to_numpy(dtype=float)
        resource_cv_pct = float(
            np.std(avg_year_energy, ddof=1) / max(abs(np.mean(avg_year_energy)), 1e-12) * 100.0
        )
        method = "empirical shared interannual resource scenarios + evidence-width candidate residuals"
    else:
        shared = _positive_lognormal_multiplier(rng, shared_resource_sigma_pct, int(n))
        shared_base = base[:, None] * shared[None, :]
        resource_cv_pct = float(shared_resource_sigma_pct)
        method = "shared-resource correlated Monte Carlo + evidence-width candidate residuals"

    draws = []
    sigma_used: dict[str, float] = {}
    candidate_sigma_pct = dict(candidate_sigma_pct or {})
    for i, row in frame.iterrows():
        mid = str(row["module_id"])
        sigma = float(candidate_sigma_pct.get(mid, candidate_model_sigma_pct(row)))
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
        "resource_uncertainty_basis": "empirical_interannual" if empirical is not None else "screening_prior",
        "candidate_model_sigma_pct": sigma_used,
        "n_samples": int(n),
        "method": method,
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
