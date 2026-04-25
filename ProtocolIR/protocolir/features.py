"""
Feature extraction for reward scoring.
Extracts trajectory features from IR operations and violations.
"""

from typing import List, Dict
from protocolir.schemas import IROp, IROpType, Violation, TrajectoryFeatures


def extract_trajectory_features(
    ir_ops: List[IROp], violations: List[Violation]
) -> TrajectoryFeatures:
    """
    Extract features from IR trajectory and violations for reward scoring.

    Args:
        ir_ops: List of IR operations
        violations: List of violations detected

    Returns:
        TrajectoryFeatures object with all extracted features
    """

    features = TrajectoryFeatures()

    # Count violations by type
    violation_counts = count_violations_by_type(violations)

    features.contamination_violations = violation_counts.get("CROSS_CONTAMINATION", 0)
    features.pipette_range_violations = violation_counts.get(
        "PIPETTE_RANGE_VIOLATION", 0
    )
    features.well_overflow_violations = violation_counts.get("WELL_OVERFLOW", 0)
    features.aspirate_no_tip_violations = violation_counts.get("ASPIRATE_NO_TIP", 0)
    features.dispense_no_tip_violations = violation_counts.get("DISPENSE_NO_TIP", 0)
    features.unknown_location_violations = violation_counts.get(
        "UNKNOWN_SOURCE", 0
    ) + violation_counts.get("UNKNOWN_DESTINATION", 0)
    features.drop_tip_with_liquid_violations = violation_counts.get(
        "DROP_TIP_WITH_LIQUID", 0
    )
    features.total_violations = len(violations)

    # Count operation types
    op_counts = count_operations_by_type(ir_ops)

    features.tip_changes = op_counts.get("PickUpTip", 0) + op_counts.get("DropTip", 0)
    features.aspirate_events = op_counts.get("Aspirate", 0)
    features.dispense_events = op_counts.get("Dispense", 0)
    features.transfer_count = min(
        features.aspirate_events, features.dispense_events
    )  # Aspirate-dispense pairs
    features.mix_events = op_counts.get("Mix", 0)

    # Semantic features
    features.tip_changed_between_different_reagents = (
        count_tip_changes_between_reagents(ir_ops)
    )
    features.complete_transfer_pairs = count_complete_transfer_pairs(ir_ops)
    features.missing_mix_events = count_missing_mix_after_dispense(ir_ops)

    return features


def count_violations_by_type(violations: List[Violation]) -> Dict[str, int]:
    """Count violations grouped by type."""

    counts = {}
    for v in violations:
        counts[v.violation_type] = counts.get(v.violation_type, 0) + 1

    return counts


def count_operations_by_type(ir_ops: List[IROp]) -> Dict[str, int]:
    """Count IR operations grouped by type."""

    counts = {}
    for op in ir_ops:
        op_name = op.op.value if hasattr(op.op, "value") else str(op.op)
        counts[op_name] = counts.get(op_name, 0) + 1

    return counts


def count_tip_changes_between_reagents(ir_ops: List[IROp]) -> int:
    """
    Count how many times tip was changed between different reagents.
    Higher is better (more safety).
    """

    count = 0
    current_reagent = None
    last_tip_drop = None

    for i, op in enumerate(ir_ops):
        if op.op == IROpType.ASPIRATE:
            if op.reagent and op.reagent != current_reagent:
                # Check if there was a tip drop before this
                if last_tip_drop is not None and last_tip_drop > i - 5:
                    count += 1
                    current_reagent = op.reagent

        elif op.op == IROpType.DROP_TIP:
            last_tip_drop = i

    return count


def count_complete_transfer_pairs(ir_ops: List[IROp]) -> int:
    """
    Count aspirate-dispense pairs that are complete (have pick_up before, drop after).
    """

    count = 0

    for i, op in enumerate(ir_ops):
        if op.op == IROpType.DISPENSE:
            # Look back for Pick -> Aspirate -> Dispense pattern
            found_aspirate = False
            found_pickup = False

            # Look for aspirate immediately before
            if i > 0 and ir_ops[i - 1].op == IROpType.ASPIRATE:
                found_aspirate = True

                # Look for pickup before aspirate
                if i > 1 and ir_ops[i - 2].op == IROpType.PICK_UP_TIP:
                    found_pickup = True

            # Look for drop after
            found_drop = False
            if i < len(ir_ops) - 1 and ir_ops[i + 1].op == IROpType.DROP_TIP:
                found_drop = True

            if found_aspirate and found_pickup and found_drop:
                count += 1

    return count


def count_missing_mix_after_dispense(ir_ops: List[IROp]) -> int:
    """
    Count dispenses to wells that should be mixed but aren't.
    Returns count of missing mix events (negative feature).
    """

    missing = 0

    for i, op in enumerate(ir_ops):
        if op.op == IROpType.DISPENSE and op.destination:
            # Check if next operation is mix to same location
            if (
                i < len(ir_ops) - 1
                and ir_ops[i + 1].op == IROpType.MIX
                and ir_ops[i + 1].location == op.destination
            ):
                # Mix found, ok
                pass
            elif "plate" in op.destination:
                # Dispensing to plate without mix - should have mixed
                missing += 1

    return missing


def feature_vector_to_dict(features: TrajectoryFeatures) -> Dict[str, float]:
    """Convert TrajectoryFeatures to dictionary for reward calculation."""

    return features.model_dump(exclude_unset=False)


def features_difference(expert_features: Dict, corrupted_features: Dict) -> Dict:
    """
    Calculate difference between expert and corrupted trajectories.
    Used for learning reward function.
    """

    diff = {}
    for key in expert_features:
        diff[key] = expert_features[key] - corrupted_features.get(key, 0)

    return diff
