#!/usr/bin/env python3
"""
Train an improved reward model using expanded protocol data.
Uses both the demo protocols and newly fetched protocols.io data.

This script:
1. Processes all protocols in data/protocols_io_raw/
2. Builds expert vs corrupted trajectory pairs
3. Trains logistic regression reward model
4. Saves weights for future use

Run with: python3 train_reward_model.py
"""

import json
import os
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import protocolir as pir
from protocolir.features import extract_trajectory_features


def load_all_protocols(protocols_dir: str = "data/protocols_io_raw") -> list[str]:
    """Load all protocol files from directory."""
    protocol_texts = []
    protocols_path = Path(protocols_dir)

    if not protocols_path.exists():
        print(f"✗ Protocol directory not found: {protocols_dir}")
        return []

    for file in sorted(protocols_path.glob("*.txt")):
        try:
            with open(file) as f:
                text = f.read()
                if text.strip():
                    protocol_texts.append(text)
                    print(f"  ✓ Loaded: {file.name}")
        except Exception as e:
            print(f"  ✗ Error loading {file.name}: {e}")

    return protocol_texts


def process_protocol_to_trajectory(protocol_text: str) -> dict:
    """Process protocol text through ProtocolIR pipeline to get trajectory."""
    try:
        # Parse
        parsed = pir.parse_protocol(protocol_text)

        # Ground
        grounded = pir.ground_actions(parsed)

        # Build IR
        ir = pir.build_ir(grounded)

        # Verify
        violations = pir.verify_ir(ir)

        # Repair
        ir_repaired, repairs = pir.repair_ir(ir, violations)

        return {
            "ir": ir_repaired,
            "violations_before": len(violations),
            "violations_after": 0 if not repairs else len([r for r in repairs if "fixed" in r]),
            "success": True
        }
    except Exception as e:
        print(f"    Warning: Could not process protocol: {e}")
        return {"success": False}


def build_training_data(protocols: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Build feature vectors and labels for training."""
    X = []  # Features
    y = []  # Labels (1=good/fixed, 0=corrupted)

    print(f"\n Processing {len(protocols)} protocols...")

    for i, protocol_text in enumerate(protocols):
        print(f"  [{i+1}/{len(protocols)}]", end=" ")

        result = process_protocol_to_trajectory(protocol_text)

        if not result["success"]:
            print("✗ (parse error)")
            continue

        ir = result["ir"]

        # Extract features
        try:
            features = extract_trajectory_features(ir, [])

            # Convert features object to vector
            feature_vector = np.array([
                features.violation_count,
                features.contamination_violations,
                features.pipette_range_violations,
                features.well_overflow_violations,
                features.missing_mix_violations,
                features.total_operations,
                features.aspirate_count,
                features.dispense_count,
                features.mix_count,
                features.tip_changes,
            ])

            X.append(feature_vector)
            # Label: 1 if violations were fixed, 0 if still has violations
            y.append(1 if result["violations_before"] > result["violations_after"] else 0)
            print(f"✓ ({len(feature_vector)} features)")

        except Exception as e:
            print(f"✗ (feature error: {e})")

    return np.array(X), np.array(y)


def train_model(X: np.ndarray, y: np.ndarray, output_path: str = "models/learned_weights.json"):
    """Train logistic regression reward model."""
    print(f"\n Training reward model on {len(X)} trajectories...")

    if len(X) < 2:
        print("✗ Need at least 2 trajectories to train")
        return False

    try:
        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train model
        model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X_scaled, y)

        # Evaluate
        score = model.score(X_scaled, y)
        print(f"  Model accuracy: {score:.2%}")

        # Save model
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        weights = {
            "coefficients": model.coef_[0].tolist(),
            "intercept": float(model.intercept_[0]),
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
            "feature_names": [
                "violation_count",
                "contamination_violations",
                "pipette_range_violations",
                "well_overflow_violations",
                "missing_mix_violations",
                "total_operations",
                "aspirate_count",
                "dispense_count",
                "mix_count",
                "tip_changes",
            ],
            "accuracy": float(score),
            "training_samples": len(X),
        }

        with open(output_path, "w") as f:
            json.dump(weights, f, indent=2)

        print(f"  ✓ Model saved to: {output_path}")
        return True

    except Exception as e:
        print(f"✗ Training failed: {e}")
        return False


def main():
    """Main training pipeline."""
    print("=" * 70)
    print("PROTOCOLIR REWARD MODEL TRAINING")
    print("=" * 70)

    # Load protocols
    print("\n📥 Loading protocols...")
    protocols = load_all_protocols("data/protocols_io_raw")

    if not protocols:
        print("✗ No protocols found. Run data_fetcher.py first:")
        print("  python3 data_fetcher.py")
        return

    print(f"✓ Loaded {len(protocols)} protocols")

    # Build training data
    X, y = build_training_data(protocols)

    if len(X) < 2:
        print("✗ Not enough valid training data")
        return

    print(f"✓ Built training set: {len(X)} trajectories, {X.shape[1]} features")

    # Train model
    success = train_model(X, y)

    print("\n" + "=" * 70)
    if success:
        print("✓ Training complete!")
        print("  New reward model ready in: models/learned_weights.json")
        print("  Use with: protocolir.reward_model.RewardModel.from_file(...)")
    else:
        print("✗ Training failed")
    print("=" * 70)


if __name__ == "__main__":
    main()
