"""Feature extraction for reward-guided trajectory scoring."""

from __future__ import annotations

from typing import Dict, List

from protocolir.schemas import IROp, IROpType, TrajectoryFeatures, Violation


def extract_trajectory_features(
    ir_ops: List[IROp], violations: List[Violation]
) -> TrajectoryFeatures:
    features = TrajectoryFeatures()
    violation_counts = count_violations_by_type(violations)
    op_counts = count_operations_by_type(ir_ops)

    features.contamination_violations = violation_counts.get("CROSS_CONTAMINATION", 0)
    features.pipette_range_violations = violation_counts.get("PIPETTE_RANGE_VIOLATION", 0)
    features.well_overflow_violations = violation_counts.get("WELL_OVERFLOW", 0)
    features.aspirate_no_tip_violations = violation_counts.get("ASPIRATE_NO_TIP", 0)
    features.dispense_no_tip_violations = violation_counts.get("DISPENSE_NO_TIP", 0)
    features.mix_no_tip_violations = violation_counts.get("MIX_NO_TIP", 0)
    features.unknown_location_violations = sum(
        violation_counts.get(name, 0)
        for name in [
            "UNKNOWN_SOURCE",
            "UNKNOWN_DESTINATION",
            "UNKNOWN_MIX_LOCATION",
        ]
    )
    features.invalid_location_violations = sum(
        violation_counts.get(name, 0)
        for name in [
            "INVALID_SOURCE",
            "INVALID_DESTINATION",
            "INVALID_MIX_LOCATION",
        ]
    )
    features.drop_tip_with_liquid_violations = violation_counts.get("DROP_TIP_WITH_LIQUID", 0)
    features.missing_mix_events = violation_counts.get("MISSING_MIX", 0)

    features.tip_changes = op_counts.get("DropTip", 0)
    features.aspirate_events = op_counts.get("Aspirate", 0)
    features.dispense_events = op_counts.get("Dispense", 0)
    features.mix_events = op_counts.get("Mix", 0)
    features.total_operations = len(ir_ops)

    features.tip_changed_between_different_reagents = count_tip_changes_between_reagents(ir_ops)
    features.complete_transfer_pairs = count_complete_transfer_pairs(ir_ops)
    return features


def count_violations_by_type(violations: List[Violation]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for violation in violations:
        counts[violation.violation_type] = counts.get(violation.violation_type, 0) + 1
    return counts


def count_operations_by_type(ir_ops: List[IROp]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for op in ir_ops:
        name = op.op.value if hasattr(op.op, "value") else str(op.op)
        counts[name] = counts.get(name, 0) + 1
    return counts


def count_tip_changes_between_reagents(ir_ops: List[IROp]) -> int:
    changes = 0
    previous_reagent = None
    fresh_tip = False

    for op in ir_ops:
        if op.op == IROpType.PICK_UP_TIP:
            fresh_tip = True
        elif op.op == IROpType.ASPIRATE and op.reagent:
            if previous_reagent and previous_reagent != op.reagent and fresh_tip:
                changes += 1
            previous_reagent = op.reagent
            fresh_tip = False
        elif op.op == IROpType.DROP_TIP:
            fresh_tip = False

    return changes


def count_complete_transfer_pairs(ir_ops: List[IROp]) -> int:
    count = 0
    holding = {}
    has_tip = {}

    for op in ir_ops:
        pipette = op.pipette
        if op.op == IROpType.PICK_UP_TIP and pipette:
            has_tip[pipette] = True
            holding[pipette] = False
        elif op.op == IROpType.ASPIRATE and pipette and has_tip.get(pipette):
            holding[pipette] = True
        elif op.op == IROpType.DISPENSE and pipette and holding.get(pipette):
            count += 1
            holding[pipette] = False
        elif op.op == IROpType.DROP_TIP and pipette:
            has_tip[pipette] = False
            holding[pipette] = False

    return count


def feature_vector_to_dict(features: TrajectoryFeatures) -> Dict[str, float]:
    return features.model_dump(exclude_unset=False)


def features_difference(expert_features: Dict, corrupted_features: Dict) -> Dict:
    return {
        key: expert_features.get(key, 0) - corrupted_features.get(key, 0)
        for key in expert_features
    }
