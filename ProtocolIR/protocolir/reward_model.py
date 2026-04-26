"""Layer 5: learned/preference reward model for lab trajectories."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

import numpy as np

from protocolir.features import extract_trajectory_features
from protocolir.schemas import IROp, RewardScore, TrajectoryFeatures, Violation


DEFAULT_REWARD_WEIGHTS = {
    "contamination_violations": -100000.0,
    "pipette_range_violations": -50000.0,
    "well_overflow_violations": -50000.0,
    "aspirate_no_tip_violations": -50000.0,
    "dispense_no_tip_violations": -50000.0,
    "mix_no_tip_violations": -25000.0,
    "unknown_location_violations": -10000.0,
    "invalid_location_violations": -10000.0,
    "drop_tip_with_liquid_violations": -50000.0,
    "missing_mix_events": -500.0,
    "tip_changes": -2.0,
    "aspirate_events": 10.0,
    "dispense_events": 10.0,
    "mix_events": 250.0,
    "total_operations": -0.2,
    "tip_changed_between_different_reagents": 5000.0,
    "complete_transfer_pairs": 500.0,
}


LEGACY_FEATURE_MAP = {
    "violation_count": "contamination_violations",
    "missing_mix_violations": "missing_mix_events",
    "total_operations": "total_operations",
    "aspirate_count": "aspirate_events",
    "dispense_count": "dispense_events",
    "mix_count": "mix_events",
}


class RewardModel:
    """Linear reward function over verified IR trajectory features."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = dict(DEFAULT_REWARD_WEIGHTS)
        if weights:
            for name, value in weights.items():
                self.weights[name] = float(value)
        self.feature_names = list(self.weights.keys())

    def score_trajectory(self, features: TrajectoryFeatures) -> RewardScore:
        values = features.model_dump(exclude_unset=False)
        violation_count = _feature_violation_count(values)
        total = 0.0
        breakdown: Dict[str, float] = {}
        for name, weight in self.weights.items():
            contribution = float(values.get(name, 0)) * weight
            breakdown[name] = contribution
            total += contribution
        return RewardScore(
            total_score=total,
            feature_scores=breakdown,
            violations_count=violation_count,
            threshold_passed=violation_count == 0 and total >= 0,
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"weights": self.weights, "feature_names": self.feature_names}, handle, indent=2)

    @staticmethod
    def load(path: str) -> "RewardModel":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if "weights" in data:
            return RewardModel({str(k): float(v) for k, v in data["weights"].items()})
        if "coefficients" in data and "feature_names" in data:
            return RewardModel(_weights_from_legacy_coefficients(data))
        return RewardModel({str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))})


def train_reward_model(
    expert_trajectories: List[Tuple[List[IROp], List[Violation]]],
    corrupted_trajectories: List[Tuple[List[IROp], List[Violation]]],
) -> RewardModel:
    """
    Learn reward weights from expert-vs-corrupted preference pairs.

    This is inverse preference learning: for each pair, optimize weights so
    score(expert) > score(corrupted). It avoids a heavyweight sklearn dependency
    while preserving the publishable framing: reward learning from demonstrations
    and counterfactual unsafe variants.
    """

    if not expert_trajectories or not corrupted_trajectories:
        raise ValueError("Reward learning requires expert and corrupted trajectories")

    feature_names = list(DEFAULT_REWARD_WEIGHTS.keys())
    pair_vectors = []
    for expert, corrupted in zip(expert_trajectories, corrupted_trajectories):
        expert_features = extract_trajectory_features(*expert).model_dump(exclude_unset=False)
        corrupted_features = extract_trajectory_features(*corrupted).model_dump(exclude_unset=False)
        pair_vectors.append(
            [expert_features.get(name, 0) - corrupted_features.get(name, 0) for name in feature_names]
        )

    if not pair_vectors:
        raise ValueError("Reward learning produced no preference pairs")

    x = np.asarray(pair_vectors, dtype=float)
    scale = np.maximum(np.std(x, axis=0), 1.0)
    x_scaled = x / scale

    weights = np.asarray([DEFAULT_REWARD_WEIGHTS[name] for name in feature_names], dtype=float)
    weights = weights / np.maximum(np.linalg.norm(weights), 1.0)

    learning_rate = 0.2
    l2 = 0.01
    for _ in range(400):
        margins = x_scaled @ weights
        gradients = -(x_scaled.T @ (1.0 / (1.0 + np.exp(margins)))) / len(x_scaled)
        gradients += l2 * weights
        weights -= learning_rate * gradients

    learned = {name: float(w / s * 1000.0) for name, w, s in zip(feature_names, weights, scale)}

    # Keep safety invariants dominated by domain priors; let data tune softer terms.
    combined = dict(DEFAULT_REWARD_WEIGHTS)
    for name, value in learned.items():
        if "violations" in name or "contamination" in name or "overflow" in name:
            combined[name] = min(combined[name], value)
        else:
            combined[name] = 0.7 * combined[name] + 0.3 * value
    return RewardModel(combined)


def domain_prior_reward_model() -> RewardModel:
    return RewardModel(DEFAULT_REWARD_WEIGHTS)


def compare_trajectories(
    expert_features: TrajectoryFeatures,
    corrupted_features: TrajectoryFeatures,
    model: RewardModel,
) -> Dict:
    expert_score = model.score_trajectory(expert_features)
    corrupted_score = model.score_trajectory(corrupted_features)
    expert_values = expert_features.model_dump(exclude_unset=False)
    corrupted_values = corrupted_features.model_dump(exclude_unset=False)
    return {
        "expert_score": expert_score.total_score,
        "corrupted_score": corrupted_score.total_score,
        "difference": expert_score.total_score - corrupted_score.total_score,
        "expert_violations": _feature_violation_count(expert_values),
        "corrupted_violations": _feature_violation_count(corrupted_values),
        "expert_passed": expert_score.threshold_passed,
        "corrupted_passed": corrupted_score.threshold_passed,
    }


def update_weights_bayesian(
    prior_weights: Dict[str, float],
    expert_trajectories: List[Tuple[List[IROp], List[Violation]]],
    corrupted_trajectories: List[Tuple[List[IROp], List[Violation]]],
    learning_rate: float = 0.01,
) -> Dict[str, float]:
    """Lightweight posterior-style update around prior weights."""

    trained = train_reward_model(expert_trajectories, corrupted_trajectories)
    updated = dict(prior_weights)
    for name, value in trained.weights.items():
        prior = updated.get(name, DEFAULT_REWARD_WEIGHTS.get(name, 0.0))
        updated[name] = (1.0 - learning_rate) * prior + learning_rate * value
    return updated


def _weights_from_legacy_coefficients(data: Dict) -> Dict[str, float]:
    weights = dict(DEFAULT_REWARD_WEIGHTS)
    for name, coefficient in zip(data.get("feature_names", []), data.get("coefficients", [])):
        mapped = LEGACY_FEATURE_MAP.get(name, name)
        if mapped in weights:
            weights[mapped] = float(coefficient) * 1000.0
    return weights


def _feature_violation_count(values: Dict[str, float]) -> int:
    return int(
        sum(
            float(values.get(name, 0.0))
            for name in [
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
            ]
        )
    )
