"""
LAYER 5: Learned Reward Model
Trains a reward function from expert vs corrupted demonstrations.
Uses logistic regression for efficiency in hackathon context.
"""

import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from protocolir.schemas import TrajectoryFeatures, RewardScore, IROp, Violation
from protocolir.features import extract_trajectory_features


# Default reward weights (before learning)
DEFAULT_REWARD_WEIGHTS = {
    "contamination_violations": -10000,
    "pipette_range_violations": -5000,
    "well_overflow_violations": -5000,
    "aspirate_no_tip_violations": -10000,
    "dispense_no_tip_violations": -5000,
    "unknown_location_violations": -3000,
    "drop_tip_with_liquid_violations": -10000,
    "total_violations": -100,
    "tip_changes": -2,
    "aspirate_events": 0,
    "dispense_events": 0,
    "transfer_count": +50,
    "mix_events": +100,
    "tip_changed_between_different_reagents": +500,
    "complete_transfer_pairs": +200,
    "missing_mix_events": -50,
}


class RewardModel:
    """Learned reward function for lab trajectory scoring."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize reward model.

        Args:
            weights: Dictionary of feature weights. If None, uses defaults.
        """

        self.weights = weights or DEFAULT_REWARD_WEIGHTS.copy()
        self.feature_names = list(self.weights.keys())

    def score_trajectory(self, features: TrajectoryFeatures) -> RewardScore:
        """
        Score a trajectory using the reward function.

        Args:
            features: TrajectoryFeatures extracted from IR trajectory

        Returns:
            RewardScore with total score and feature breakdown
        """

        score = RewardScore(total_score=0.0, violations_count=features.total_violations)

        feature_dict = features.model_dump(exclude_unset=False)

        total = 0.0
        for feature_name, weight in self.weights.items():
            feature_value = feature_dict.get(feature_name, 0)
            contribution = feature_value * weight
            score.feature_scores[feature_name] = contribution
            total += contribution

        score.total_score = total
        score.threshold_passed = total >= -100  # Threshold: allow some violations but penalize severely

        return score

    def save(self, path: str):
        """Save learned weights to JSON."""

        with open(path, "w") as f:
            json.dump(self.weights, f, indent=2)

    @staticmethod
    def load(path: str) -> "RewardModel":
        """Load learned weights from JSON."""

        with open(path, "r") as f:
            weights = json.load(f)

        return RewardModel(weights)


def train_reward_model(
    expert_trajectories: List[Tuple[List[IROp], List[Violation]]],
    corrupted_trajectories: List[Tuple[List[IROp], List[Violation]]],
) -> RewardModel:
    """
    Train a reward model from expert vs corrupted demonstration pairs.

    Uses logistic regression to learn P(expert > corrupted).

    Args:
        expert_trajectories: List of (ir_ops, violations) tuples for good trajectories
        corrupted_trajectories: List of (ir_ops, violations) tuples for bad trajectories

    Returns:
        Trained RewardModel
    """

    # Extract features from all trajectories
    expert_features_list = []
    for ir_ops, violations in expert_trajectories:
        features = extract_trajectory_features(ir_ops, violations)
        expert_features_list.append(features.model_dump(exclude_unset=False))

    corrupted_features_list = []
    for ir_ops, violations in corrupted_trajectories:
        features = extract_trajectory_features(ir_ops, violations)
        corrupted_features_list.append(features.model_dump(exclude_unset=False))

    # Build feature matrix and labels
    feature_names = list(expert_features_list[0].keys())

    # Stack features: expert first (label=1), corrupted second (label=0)
    X_expert = np.array([[f.get(name, 0) for name in feature_names] for f in expert_features_list])
    X_corrupted = np.array(
        [[f.get(name, 0) for name in feature_names] for f in corrupted_features_list]
    )

    X = np.vstack([X_expert, X_corrupted])
    y = np.array([1] * len(expert_features_list) + [0] * len(corrupted_features_list))

    # Train logistic regression: P(expert > corrupted) = sigmoid(w · features)
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X, y)

    # Extract learned weights
    weights = {
        name: float(coef) for name, coef in zip(feature_names, model.coef_[0])
    }

    return RewardModel(weights)


def learn_reward_heuristically() -> RewardModel:
    """
    Return a heuristic reward model based on domain knowledge.
    Used when we don't have enough training data.

    The heuristics encode what makes a good lab protocol:
    - Avoid contamination at all costs
    - Respect pipette ranges
    - Don't overflow wells
    - Change tips appropriately
    - Mix after reagent addition
    """

    heuristic_weights = {
        "contamination_violations": -100000,  # Absolute worst
        "pipette_range_violations": -50000,   # Severe
        "well_overflow_violations": -50000,   # Severe
        "aspirate_no_tip_violations": -50000, # Severe
        "dispense_no_tip_violations": -50000, # Severe
        "unknown_location_violations": -10000,
        "drop_tip_with_liquid_violations": -50000,
        "total_violations": -1000,
        "tip_changes": -5,  # Slightly penalize unnecessary changes
        "aspirate_events": 10,  # Bonus for each action
        "dispense_events": 10,
        "transfer_count": 100,  # Bonus for complete transfers
        "mix_events": 500,  # Big bonus for mixing (critical safety)
        "tip_changed_between_different_reagents": 5000,  # Huge bonus for safety
        "complete_transfer_pairs": 500,  # Bonus for well-formed transfers
        "missing_mix_events": -500,  # Penalize missing mixes
    }

    return RewardModel(heuristic_weights)


def compare_trajectories(
    expert_features: TrajectoryFeatures,
    corrupted_features: TrajectoryFeatures,
    model: RewardModel,
) -> Dict:
    """
    Compare expert vs corrupted trajectory scores.
    Returns comparison report.
    """

    expert_score = model.score_trajectory(expert_features)
    corrupted_score = model.score_trajectory(corrupted_features)

    return {
        "expert_score": expert_score.total_score,
        "corrupted_score": corrupted_score.total_score,
        "difference": expert_score.total_score - corrupted_score.total_score,
        "expert_violations": expert_features.total_violations,
        "corrupted_violations": corrupted_features.total_violations,
        "expert_passed": expert_score.threshold_passed,
        "corrupted_passed": corrupted_score.threshold_passed,
    }


def update_weights_bayesian(
    prior_weights: Dict[str, float],
    expert_trajectories: List[Tuple[List[IROp], List[Violation]]],
    corrupted_trajectories: List[Tuple[List[IROp], List[Violation]]],
    learning_rate: float = 0.01,
) -> Dict[str, float]:
    """
    Update weights using gradient-based Bayesian learning.
    Simpler than full MCMC, sufficient for hackathon.

    Args:
        prior_weights: Initial weights
        expert_trajectories: Good examples
        corrupted_trajectories: Bad examples
        learning_rate: Step size for updates

    Returns:
        Updated weights
    """

    model = RewardModel(prior_weights)
    updated_weights = prior_weights.copy()

    # Simple learning loop
    for expert_ir, expert_viol in expert_trajectories[:5]:  # Limit iterations
        expert_features = extract_trajectory_features(expert_ir, expert_viol)
        expert_score = model.score_trajectory(expert_features).total_score

        # Increase weight of features that appear in good trajectories
        feature_dict = expert_features.model_dump(exclude_unset=False)
        for feature_name, value in feature_dict.items():
            if value > 0:
                updated_weights[feature_name] = (
                    updated_weights[feature_name] + learning_rate * value
                )

    for corrupted_ir, corrupted_viol in corrupted_trajectories[:5]:
        corrupted_features = extract_trajectory_features(corrupted_ir, corrupted_viol)
        corrupted_score = model.score_trajectory(corrupted_features).total_score

        # Decrease weight of features that appear in bad trajectories
        feature_dict = corrupted_features.model_dump(exclude_unset=False)
        for feature_name, value in feature_dict.items():
            if value > 0 and corrupted_viol:
                updated_weights[feature_name] = (
                    updated_weights[feature_name] - learning_rate * value
                )

    return updated_weights
