"""Optional PyMC/NUTS validation model for the Bayesian IRL posterior.

This module is intentionally isolated from the production pipeline. It gives a
reviewer-facing way to validate the same preference likelihood with PyMC NUTS
when PyMC is installed in a research environment.
"""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np

from protocolir.bayesian_irl import _build_pair_matrix
from protocolir.reward_model import DEFAULT_REWARD_WEIGHTS


def build_pymc_model(
    expert_feature_dicts: Sequence[Dict[str, float]],
    corrupted_feature_dicts: Sequence[Dict[str, float]],
    *,
    max_pairs: int = 5000,
    seed: int = 42,
):
    try:
        import pymc as pm
    except ImportError as exc:
        raise RuntimeError(
            "PyMC is not installed. Install pymc in a research environment to run "
            "the appendix NUTS validation model."
        ) from exc

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

    with pm.Model() as model:
        weights = pm.Normal("weights", mu=prior_mean, sigma=prior_sd, shape=len(feature_names))
        margin = pm.math.dot(x_scaled, weights)
        pm.Bernoulli("expert_preferred", logit_p=margin, observed=np.ones(x_scaled.shape[0]))
    return model, feature_names, scale


def sample_nuts_validation(
    expert_feature_dicts: Sequence[Dict[str, float]],
    corrupted_feature_dicts: Sequence[Dict[str, float]],
    *,
    draws: int = 1000,
    tune: int = 1000,
    chains: int = 4,
    max_pairs: int = 5000,
    seed: int = 42,
):
    model, feature_names, scale = build_pymc_model(
        expert_feature_dicts,
        corrupted_feature_dicts,
        max_pairs=max_pairs,
        seed=seed,
    )
    import pymc as pm

    with model:
        trace = pm.sample(draws=draws, tune=tune, chains=chains, random_seed=seed)
    return trace, feature_names, scale
