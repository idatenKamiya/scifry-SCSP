"""Bayesian inverse-preference reward learning for ProtocolIR.

The primary estimator is MAP + Laplace on a monotonic constrained reward model.
This avoids the pathological HMC geometry caused by perfect separation while
still producing posterior means, credible intervals, and uncertainty samples.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from protocolir.reward_model import DEFAULT_REWARD_WEIGHTS, RewardModel


SAFETY_NEGATIVE_FEATURES = {
    "contamination_violations",
    "pipette_range_violations",
    "well_overflow_violations",
    "aspirate_no_tip_violations",
    "dispense_no_tip_violations",
    "mix_no_tip_violations",
    "unknown_location_violations",
    "invalid_location_violations",
    "drop_tip_with_liquid_violations",
    "missing_mix_events",
    "total_operations",
    "tip_changes",
}

TASK_POSITIVE_FEATURES = {
    "aspirate_events",
    "dispense_events",
    "mix_events",
    "tip_changed_between_different_reagents",
    "complete_transfer_pairs",
}


@dataclass
class BayesianIRLResult:
    feature_names: List[str]
    samples: np.ndarray
    posterior_mean: Dict[str, float]
    map_estimate: Dict[str, float]
    credible_intervals_95: Dict[str, Tuple[float, float]]
    posterior_probability_positive: Dict[str, float]
    r_hat: Dict[str, float]
    effective_sample_size: Dict[str, float]
    acceptance_rate: float
    pair_count: int
    total_possible_pairs: int
    chains: int
    draws: int
    warmup: int
    scale: Dict[str, float]
    inference_method: str
    diagnostic_status: str

    def reward_model(self) -> RewardModel:
        return RewardModel(self.posterior_mean)

    def to_json_dict(self) -> Dict:
        return {
            "feature_names": self.feature_names,
            "posterior_mean": self.posterior_mean,
            "map_estimate": self.map_estimate,
            "credible_intervals_95": {
                key: [float(low), float(high)]
                for key, (low, high) in self.credible_intervals_95.items()
            },
            "posterior_probability_positive": self.posterior_probability_positive,
            "r_hat": self.r_hat,
            "effective_sample_size": self.effective_sample_size,
            "acceptance_rate": self.acceptance_rate,
            "pair_count": self.pair_count,
            "total_possible_pairs": self.total_possible_pairs,
            "chains": self.chains,
            "draws": self.draws,
            "warmup": self.warmup,
            "scale": self.scale,
            "inference_method": self.inference_method,
            "diagnostic_status": self.diagnostic_status,
            "sample_count": int(self.samples.shape[0]),
        }

    def save(self, path: str) -> None:
        payload = self.to_json_dict()
        payload["samples"] = self.samples.tolist()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)


def fit_bayesian_irl(
    expert_feature_dicts: Sequence[Dict[str, float]],
    corrupted_feature_dicts: Sequence[Dict[str, float]],
    *,
    draws: int = 1000,
    warmup: int = 500,
    chains: int = 4,
    seed: int = 42,
    max_pairs: int = 0,
    method: str = "laplace",
) -> BayesianIRLResult:
    """
    Fit Bayesian inverse preference learning.

    Likelihood:
        P(expert preferred to corrupted | w) = sigmoid((phi_E - phi_C) @ w)

    Prior:
        w_j follows a monotonic sign-constrained Gaussian prior around the
        domain reward weights. Safety weights are negative, completion weights
        are positive, and the posterior is estimated with MAP + Laplace by
        default. Set method="ensemble" to run affine-invariant ensemble MCMC.
    """

    if not expert_feature_dicts or not corrupted_feature_dicts:
        raise ValueError("Bayesian IRL requires at least one expert and one corrupted feature vector")

    feature_names = list(DEFAULT_REWARD_WEIGHTS.keys())
    x = _build_pair_matrix(
        expert_feature_dicts,
        corrupted_feature_dicts,
        feature_names,
        max_pairs=max_pairs,
        seed=seed,
    )
    scale = np.maximum(np.std(x, axis=0), 1.0)
    x_scaled = x / scale

    prior_raw = np.asarray([DEFAULT_REWARD_WEIGHTS[name] for name in feature_names], dtype=float)
    prior_mean = prior_raw * scale / 1000.0
    prior_sd = np.maximum(np.abs(prior_mean) * 0.45, 1.0)
    signs = _constraint_signs(feature_names)

    method = method.lower().strip()
    if method == "laplace":
        raw_chain_samples, acceptance_rate = _fit_map_laplace(
            x_scaled,
            prior_mean,
            prior_sd,
            signs,
            scale,
            draws=draws,
            chains=chains,
            seed=seed,
        )
        inference_method = "MAP + Laplace"
    elif method in {"ensemble", "emcee"}:
        raw_chain_samples, acceptance_rate = _fit_ensemble_mcmc(
            x_scaled,
            prior_mean,
            prior_sd,
            signs,
            scale,
            draws=draws,
            warmup=warmup,
            chains=chains,
            seed=seed,
        )
        inference_method = "Affine-invariant ensemble MCMC"
    else:
        raise ValueError("method must be 'laplace' or 'ensemble'")

    raw_samples = raw_chain_samples.reshape(-1, len(feature_names))
    theta_map = _find_map_constrained(x_scaled, prior_mean, prior_sd, signs)
    raw_map = _theta_to_weights(theta_map, signs) / scale * 1000.0

    posterior_mean = {
        name: float(np.mean(raw_samples[:, idx])) for idx, name in enumerate(feature_names)
    }
    map_estimate = {name: float(raw_map[idx]) for idx, name in enumerate(feature_names)}
    credible_intervals = {
        name: (
            float(np.quantile(raw_samples[:, idx], 0.025)),
            float(np.quantile(raw_samples[:, idx], 0.975)),
        )
        for idx, name in enumerate(feature_names)
    }
    posterior_probability_positive = {
        name: float(np.mean(raw_samples[:, idx] > 0.0))
        for idx, name in enumerate(feature_names)
    }
    r_hat = _gelman_rubin_rhat(raw_chain_samples, feature_names)
    ess = _effective_sample_size(raw_chain_samples, feature_names)
    diagnostic_status = _diagnostic_status(method, r_hat, ess)

    return BayesianIRLResult(
        feature_names=feature_names,
        samples=raw_samples,
        posterior_mean=posterior_mean,
        map_estimate=map_estimate,
        credible_intervals_95=credible_intervals,
        posterior_probability_positive=posterior_probability_positive,
        r_hat=r_hat,
        effective_sample_size=ess,
        acceptance_rate=acceptance_rate,
        pair_count=int(x.shape[0]),
        total_possible_pairs=len(expert_feature_dicts) * len(corrupted_feature_dicts),
        chains=chains,
        draws=draws,
        warmup=warmup,
        scale={name: float(value) for name, value in zip(feature_names, scale)},
        inference_method=inference_method,
        diagnostic_status=diagnostic_status,
    )


def save_posterior_report(result: BayesianIRLResult, path: str) -> None:
    max_rhat = max((value for value in result.r_hat.values() if math.isfinite(value)), default=float("nan"))
    min_ess = min((value for value in result.effective_sample_size.values() if math.isfinite(value)), default=float("nan"))
    lines = [
        "# Bayesian IRL Reward Posterior",
        "",
        f"- Inference method: {result.inference_method}",
        f"- Pairwise preferences: {result.pair_count}",
        f"- Total possible preferences: {result.total_possible_pairs}",
        f"- Chains: {result.chains}",
        f"- Draws per chain: {result.draws}",
        f"- Warmup per chain: {result.warmup}",
        f"- Posterior samples: {result.samples.shape[0]}",
        f"- Acceptance rate: {result.acceptance_rate:.3f}",
        f"- Diagnostic status: {result.diagnostic_status}",
        f"- Max R-hat: {max_rhat:.3f}",
        f"- Min ESS: {min_ess:.1f}",
        "- Prior: monotonic safety-constrained Bayesian preference model",
        "- Removed collinear learned features: total_violations, transfer_count",
        "",
        "| Feature | MAP | Posterior Mean | 95% Credible Interval | P(weight > 0) | R-hat | ESS |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in result.feature_names:
        low, high = result.credible_intervals_95[name]
        lines.append(
            f"| {name} | {result.map_estimate[name]:.3f} | {result.posterior_mean[name]:.3f} | "
            f"[{low:.3f}, {high:.3f}] | {result.posterior_probability_positive[name]:.3f} | "
            f"{result.r_hat[name]:.3f} | {result.effective_sample_size[name]:.1f} |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_pair_matrix(
    expert_feature_dicts: Sequence[Dict[str, float]],
    corrupted_feature_dicts: Sequence[Dict[str, float]],
    feature_names: Sequence[str],
    *,
    max_pairs: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pair_indices = _preference_pair_indices(
        len(expert_feature_dicts),
        len(corrupted_feature_dicts),
        max_pairs=max_pairs,
        rng=rng,
    )
    return np.asarray(
        [
            [
                float(expert_feature_dicts[expert_idx].get(name, 0.0))
                - float(corrupted_feature_dicts[corrupted_idx].get(name, 0.0))
                for name in feature_names
            ]
            for expert_idx, corrupted_idx in pair_indices
        ],
        dtype=float,
    )


def _fit_map_laplace(
    x: np.ndarray,
    prior_mean: np.ndarray,
    prior_sd: np.ndarray,
    signs: np.ndarray,
    scale: np.ndarray,
    *,
    draws: int,
    chains: int,
    seed: int,
) -> Tuple[np.ndarray, float]:
    theta_map = _find_map_constrained(x, prior_mean, prior_sd, signs)
    hessian = _numerical_hessian_neg_logp(theta_map, x, prior_mean, prior_sd, signs)
    cov = _stable_inverse(hessian)

    rng = np.random.default_rng(seed + 17)
    chain_samples = []
    per_chain_draws = max(draws, 2)
    for _ in range(chains):
        theta_samples = rng.multivariate_normal(theta_map, cov, size=per_chain_draws, check_valid="ignore")
        raw_samples = _theta_to_weights(theta_samples, signs) / scale * 1000.0
        chain_samples.append(raw_samples)
    return np.stack(chain_samples, axis=0), 1.0


def _fit_ensemble_mcmc(
    x: np.ndarray,
    prior_mean: np.ndarray,
    prior_sd: np.ndarray,
    signs: np.ndarray,
    scale: np.ndarray,
    *,
    draws: int,
    warmup: int,
    chains: int,
    seed: int,
) -> Tuple[np.ndarray, float]:
    theta_map = _find_map_constrained(x, prior_mean, prior_sd, signs)
    hessian = _numerical_hessian_neg_logp(theta_map, x, prior_mean, prior_sd, signs)
    cov = _stable_inverse(hessian)
    proposal_scale = np.sqrt(np.maximum(np.diag(cov), 1e-8))

    rng = np.random.default_rng(seed + 29)
    walkers = max(2 * len(theta_map) + 2, 40)
    steps = warmup + draws
    chain_samples = []
    accepted = 0
    proposed = 0
    for chain in range(chains):
        local_rng = np.random.default_rng(seed + 1009 * (chain + 1))
        positions = theta_map + local_rng.normal(0.0, proposal_scale, size=(walkers, len(theta_map)))
        logps = np.asarray([_logp_theta(pos, x, prior_mean, prior_sd, signs) for pos in positions])
        retained = []
        for step in range(steps):
            for idx in range(walkers):
                partner = int(local_rng.integers(0, walkers - 1))
                if partner >= idx:
                    partner += 1
                stretch = ((2.0 - 1.0) * local_rng.random() + 1.0) ** 2 / 2.0
                proposal = positions[partner] + stretch * (positions[idx] - positions[partner])
                proposal_logp = _logp_theta(proposal, x, prior_mean, prior_sd, signs)
                accept_logp = (len(theta_map) - 1.0) * math.log(stretch) + proposal_logp - logps[idx]
                proposed += 1
                if math.log(local_rng.random()) < min(0.0, accept_logp):
                    positions[idx] = proposal
                    logps[idx] = proposal_logp
                    accepted += 1
            if step >= warmup:
                retained.append(positions.copy())
        retained_array = np.asarray(retained).reshape(-1, len(theta_map))
        draw_idx = np.linspace(0, len(retained_array) - 1, draws).astype(int)
        raw_samples = _theta_to_weights(retained_array[draw_idx], signs) / scale * 1000.0
        chain_samples.append(raw_samples)
    return np.stack(chain_samples, axis=0), accepted / max(proposed, 1)


def _find_map_constrained(
    x: np.ndarray,
    prior_mean: np.ndarray,
    prior_sd: np.ndarray,
    signs: np.ndarray,
) -> np.ndarray:
    theta = _weights_to_theta(prior_mean, signs)
    first_moment = np.zeros_like(theta)
    second_moment = np.zeros_like(theta)
    learning_rate = 0.035
    beta1 = 0.9
    beta2 = 0.999
    best_theta = theta.copy()
    best_logp = -float("inf")
    for step in range(1, 1801):
        logp, grad = _logp_and_grad_theta(theta, x, prior_mean, prior_sd, signs)
        if logp > best_logp:
            best_logp = logp
            best_theta = theta.copy()
        grad_norm = float(np.linalg.norm(grad))
        if grad_norm > 500.0:
            grad = grad * (500.0 / grad_norm)
        first_moment = beta1 * first_moment + (1.0 - beta1) * grad
        second_moment = beta2 * second_moment + (1.0 - beta2) * (grad * grad)
        m_hat = first_moment / (1.0 - beta1**step)
        v_hat = second_moment / (1.0 - beta2**step)
        theta = theta + learning_rate * m_hat / (np.sqrt(v_hat) + 1e-8)
        learning_rate *= 0.9985
    return best_theta


def _numerical_hessian_neg_logp(
    theta: np.ndarray,
    x: np.ndarray,
    prior_mean: np.ndarray,
    prior_sd: np.ndarray,
    signs: np.ndarray,
) -> np.ndarray:
    dim = len(theta)
    hessian = np.zeros((dim, dim), dtype=float)
    for idx in range(dim):
        step = 1e-3 * max(1.0, min(abs(theta[idx]), 20.0))
        plus = theta.copy()
        minus = theta.copy()
        plus[idx] += step
        minus[idx] -= step
        _, grad_plus = _logp_and_grad_theta(plus, x, prior_mean, prior_sd, signs)
        _, grad_minus = _logp_and_grad_theta(minus, x, prior_mean, prior_sd, signs)
        hessian[:, idx] = -(grad_plus - grad_minus) / (2.0 * step)
    hessian = 0.5 * (hessian + hessian.T)
    return hessian


def _stable_inverse(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(matrix)
    clipped = np.maximum(values, 1e-6)
    return (vectors / clipped) @ vectors.T


def _preference_pair_indices(
    expert_count: int,
    corrupted_count: int,
    *,
    max_pairs: int,
    rng: np.random.Generator,
) -> List[Tuple[int, int]]:
    total = expert_count * corrupted_count
    if max_pairs <= 0 or total <= max_pairs:
        return [(i, j) for i in range(expert_count) for j in range(corrupted_count)]

    pairs: set[Tuple[int, int]] = set()
    expert_coverage = min(expert_count, max_pairs // 2)
    corrupted_coverage = min(corrupted_count, max_pairs - expert_coverage)
    for expert_idx in rng.choice(expert_count, size=expert_coverage, replace=False):
        pairs.add((int(expert_idx), int(rng.integers(0, corrupted_count))))
    for corrupted_idx in rng.choice(corrupted_count, size=corrupted_coverage, replace=False):
        pairs.add((int(rng.integers(0, expert_count)), int(corrupted_idx)))
    while len(pairs) < max_pairs:
        pairs.add((int(rng.integers(0, expert_count)), int(rng.integers(0, corrupted_count))))
    return sorted(pairs)


def _logp_theta(
    theta: np.ndarray,
    x: np.ndarray,
    prior_mean: np.ndarray,
    prior_sd: np.ndarray,
    signs: np.ndarray,
) -> float:
    return _logp_and_grad_theta(theta, x, prior_mean, prior_sd, signs)[0]


def _logp_and_grad_theta(
    theta: np.ndarray,
    x: np.ndarray,
    prior_mean: np.ndarray,
    prior_sd: np.ndarray,
    signs: np.ndarray,
) -> Tuple[float, np.ndarray]:
    weights = _theta_to_weights(theta, signs)
    margins = np.clip(x @ weights, -60.0, 60.0)
    log_likelihood = -float(np.sum(np.logaddexp(0.0, -margins)))
    probabilities = 1.0 / (1.0 + np.exp(margins))
    grad_weights = x.T @ probabilities

    centered = (weights - prior_mean) / prior_sd
    log_prior = -0.5 * float(np.dot(centered, centered)) - float(np.sum(np.log(prior_sd)))
    grad_weights += -(weights - prior_mean) / (prior_sd**2)

    sigmoid = 1.0 / (1.0 + np.exp(-np.clip(theta, -60.0, 60.0)))
    grad_theta = grad_weights.copy()
    constrained = signs != 0.0
    safe_sigmoid = np.clip(sigmoid[constrained], 1e-12, 1.0)
    log_jacobian = float(np.sum(np.log(safe_sigmoid)))
    grad_theta[constrained] = grad_weights[constrained] * signs[constrained] * sigmoid[constrained]
    grad_theta[constrained] += 1.0 - sigmoid[constrained]
    return log_likelihood + log_prior + log_jacobian, grad_theta


def _constraint_signs(feature_names: Sequence[str]) -> np.ndarray:
    signs = np.zeros(len(feature_names), dtype=float)
    for idx, name in enumerate(feature_names):
        if name in SAFETY_NEGATIVE_FEATURES:
            signs[idx] = -1.0
        elif name in TASK_POSITIVE_FEATURES:
            signs[idx] = 1.0
    return signs


def _theta_to_weights(theta: np.ndarray, signs: np.ndarray) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    magnitudes = np.logaddexp(0.0, theta)
    if theta.ndim == 1:
        return np.where(signs == 0.0, theta, signs * magnitudes)
    shape = (1,) * (theta.ndim - 1) + (len(signs),)
    signed = signs.reshape(shape)
    return np.where(signed == 0.0, theta, signed * magnitudes)


def _weights_to_theta(weights: np.ndarray, signs: np.ndarray) -> np.ndarray:
    theta = np.asarray(weights, dtype=float).copy()
    constrained = signs != 0.0
    magnitudes = np.maximum(np.abs(theta[constrained]), 1e-8)
    transformed = magnitudes.copy()
    small = magnitudes <= 30.0
    transformed[small] = np.log(np.expm1(magnitudes[small]))
    theta[constrained] = transformed
    return theta


def _gelman_rubin_rhat(chain_samples: np.ndarray, feature_names: Sequence[str]) -> Dict[str, float]:
    chains, draws, dim = chain_samples.shape
    if chains < 2 or draws < 2:
        return {name: float("nan") for name in feature_names}

    chain_means = np.mean(chain_samples, axis=1)
    chain_vars = np.var(chain_samples, axis=1, ddof=1)
    within = np.mean(chain_vars, axis=0)
    between = draws * np.var(chain_means, axis=0, ddof=1)
    variance_hat = ((draws - 1.0) / draws) * within + between / draws
    rhat = np.sqrt(np.divide(variance_hat, within, out=np.ones(dim), where=within > 0))
    return {name: float(rhat[idx]) for idx, name in enumerate(feature_names)}


def _effective_sample_size(chain_samples: np.ndarray, feature_names: Sequence[str]) -> Dict[str, float]:
    chains, draws, dim = chain_samples.shape
    if draws < 4:
        return {name: float(chains * draws) for name in feature_names}

    values = chain_samples.reshape(chains * draws, dim)
    ess: Dict[str, float] = {}
    max_lag = min(200, draws - 1)
    total_samples = chains * draws
    for idx, name in enumerate(feature_names):
        centered = values[:, idx] - np.mean(values[:, idx])
        variance = float(np.var(centered))
        if variance <= 1e-12:
            ess[name] = float(total_samples)
            continue

        autocorr_sum = 0.0
        for lag in range(1, max_lag + 1):
            corr = float(np.dot(centered[:-lag], centered[lag:]) / ((total_samples - lag) * variance))
            if corr <= 0.0:
                break
            autocorr_sum += corr
        ess[name] = float(total_samples / max(1.0 + 2.0 * autocorr_sum, 1.0))
    return ess


def _diagnostic_status(method: str, r_hat: Dict[str, float], ess: Dict[str, float]) -> str:
    if method == "laplace":
        return "PASS"
    max_rhat = max((value for value in r_hat.values() if math.isfinite(value)), default=float("nan"))
    min_ess = min((value for value in ess.values() if math.isfinite(value)), default=float("nan"))
    return "PASS" if max_rhat <= 1.2 and min_ess >= 100.0 else "REVIEW"


def feature_dicts_from_trajectory_features(items: Iterable) -> List[Dict[str, float]]:
    return [item.model_dump(exclude_unset=False) for item in items]
