"""Layer 6: deterministic policy repairs for verifier violations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

from protocolir.ir_builder import mix_volume_for, select_pipette
from protocolir.reward_model import DEFAULT_REWARD_WEIGHTS
from protocolir.schemas import IROp, IROpType, Violation


def repair_ir(
    ir_ops: List[IROp], violations: List[Violation]
) -> Tuple[List[IROp], List[str]]:
    """Apply deterministic, auditable repairs to IR violations."""

    repaired = [op.model_copy(deep=True) for op in ir_ops]
    repairs: List[str] = []
    aspirate_no_tip = {
        (violation.action_idx, ir_ops[violation.action_idx].pipette)
        for violation in violations
        if violation.violation_type == "ASPIRATE_NO_TIP" and violation.action_idx < len(ir_ops)
    }

    for violation in sorted(
        violations,
        key=lambda item: (_repair_priority(item), item.action_idx),
        reverse=True,
    ):
        idx = violation.action_idx
        if idx >= len(repaired):
            continue

        action = repaired[idx]
        if not _violation_still_applies(repaired, idx, violation):
            continue
        if violation.violation_type in {"ASPIRATE_NO_TIP", "DISPENSE_NO_TIP", "MIX_NO_TIP"}:
            if violation.violation_type != "ASPIRATE_NO_TIP" and _covered_by_prior_no_tip_aspirate(
                idx, action.pipette, aspirate_no_tip
            ):
                continue
            if action.pipette:
                repaired.insert(idx, IROp(op=IROpType.PICK_UP_TIP, pipette=action.pipette))
                repairs.append(f"[{idx}] Inserted PickUpTip before {action.op.value}.")

        elif violation.violation_type == "CROSS_CONTAMINATION":
            if action.pipette:
                repaired.insert(idx, IROp(op=IROpType.DROP_TIP, pipette=action.pipette))
                repaired.insert(idx + 1, IROp(op=IROpType.PICK_UP_TIP, pipette=action.pipette))
                repairs.append(f"[{idx}] Inserted fresh-tip boundary to prevent cross-contamination.")

        elif violation.violation_type == "PIPETTE_RANGE_VIOLATION":
            repaired_count = _repair_pipette_range(repaired, idx)
            if repaired_count:
                repairs.append(f"[{idx}] Switched {repaired_count} operation(s) to a volume-compatible pipette.")
            else:
                repairs.append(f"[{idx}] Could not auto-repair pipette range; human review required.")

        elif violation.violation_type == "MISSING_MIX":
            if action.op == IROpType.DISPENSE and action.destination and action.pipette:
                repaired.insert(
                    idx + 1,
                    IROp(
                        op=IROpType.MIX,
                        pipette=action.pipette,
                        volume_ul=mix_volume_for(action.volume_ul or 10.0, action.pipette),
                        location=action.destination,
                        repetitions=3,
                    ),
                )
                repairs.append(f"[{idx}] Inserted Mix after dispense into {action.destination}.")

        elif violation.violation_type in {
            "WELL_OVERFLOW",
            "UNKNOWN_SOURCE",
            "UNKNOWN_DESTINATION",
            "UNKNOWN_MIX_LOCATION",
            "INVALID_SOURCE",
            "INVALID_DESTINATION",
            "INVALID_MIX_LOCATION",
            "DROP_TIP_WITH_LIQUID",
            "DISPENSE_MORE_THAN_ASPIRATED",
            "TIP_OVER_CAPACITY",
        }:
            repairs.append(f"[{idx}] HUMAN_REVIEW: {violation.violation_type}: {violation.message}")

    return repaired, repairs


def repair_iteratively(
    ir_ops: List[IROp], violations: List[Violation], max_iterations: int = 5
) -> Tuple[List[IROp], List[str], List[Violation]]:
    current_ir = [op.model_copy(deep=True) for op in ir_ops]
    current_violations = list(violations)
    all_repairs: List[str] = []

    for _ in range(max_iterations):
        if not current_violations:
            break
        current_ir, repairs = repair_ir(current_ir, current_violations)
        all_repairs.extend(repairs)

        from protocolir.verifier import verify_ir

        next_violations = verify_ir(current_ir)
        if _same_violations(current_violations, next_violations):
            current_violations = next_violations
            break
        current_violations = next_violations

    return current_ir, all_repairs, current_violations


def suggest_repair_for_violation(violation: Violation) -> str:
    if violation.suggested_fix:
        return violation.suggested_fix
    suggestions = {
        "ASPIRATE_NO_TIP": "Pick up a tip before aspirating.",
        "DISPENSE_NO_TIP": "Pick up a tip before dispensing.",
        "MIX_NO_TIP": "Pick up a tip before mixing.",
        "CROSS_CONTAMINATION": "Change to a fresh tip before aspirating a different reagent.",
        "PIPETTE_RANGE_VIOLATION": "Switch pipette or split the volume.",
        "WELL_OVERFLOW": "Reduce volume or split across wells.",
        "UNKNOWN_SOURCE": "Ground the source to a loaded labware well.",
        "UNKNOWN_DESTINATION": "Ground the destination to a loaded labware well.",
    }
    return suggestions.get(violation.violation_type, "Manual protocol review required.")


def can_repair_automatically(violation: Violation) -> bool:
    return violation.violation_type in {
        "ASPIRATE_NO_TIP",
        "DISPENSE_NO_TIP",
        "MIX_NO_TIP",
        "CROSS_CONTAMINATION",
        "PIPETTE_RANGE_VIOLATION",
        "MISSING_MIX",
    }


def count_auto_repairable(violations: List[Violation]) -> int:
    return sum(1 for violation in violations if can_repair_automatically(violation))


def repair_priority_table() -> dict[str, float]:
    """Expose how learned reward features prioritize deterministic repair classes."""

    weights = _repair_weights()
    return {
        violation_type: abs(weights.get(feature_name, 0.0))
        for violation_type, feature_name in _VIOLATION_TO_FEATURE.items()
    }


_VIOLATION_TO_FEATURE = {
    "CROSS_CONTAMINATION": "contamination_violations",
    "PIPETTE_RANGE_VIOLATION": "pipette_range_violations",
    "WELL_OVERFLOW": "well_overflow_violations",
    "ASPIRATE_NO_TIP": "aspirate_no_tip_violations",
    "DISPENSE_NO_TIP": "dispense_no_tip_violations",
    "MIX_NO_TIP": "mix_no_tip_violations",
    "UNKNOWN_SOURCE": "unknown_location_violations",
    "UNKNOWN_DESTINATION": "unknown_location_violations",
    "UNKNOWN_MIX_LOCATION": "unknown_location_violations",
    "INVALID_SOURCE": "invalid_location_violations",
    "INVALID_DESTINATION": "invalid_location_violations",
    "INVALID_MIX_LOCATION": "invalid_location_violations",
    "DROP_TIP_WITH_LIQUID": "drop_tip_with_liquid_violations",
    "MISSING_MIX": "missing_mix_events",
}


def _repair_priority(violation: Violation) -> float:
    weights = _repair_weights()
    feature_name = _VIOLATION_TO_FEATURE.get(violation.violation_type)
    if feature_name:
        return abs(weights.get(feature_name, 0.0))
    return max(abs(value) for value in weights.values())


def _repair_weights() -> dict[str, float]:
    learned_path = Path("models/learned_weights.json")
    if learned_path.exists():
        try:
            data = json.loads(learned_path.read_text(encoding="utf-8"))
            weights = data.get("weights", data)
            return {str(key): float(value) for key, value in weights.items()}
        except (OSError, ValueError, TypeError):
            pass
    return dict(DEFAULT_REWARD_WEIGHTS)


def _repair_pipette_range(ir_ops: List[IROp], idx: int) -> int:
    action = ir_ops[idx]
    if action.volume_ul is None:
        return 0
    new_pipette = select_pipette(action.volume_ul)
    old_pipette = action.pipette
    if old_pipette == new_pipette:
        return 0

    start = idx
    while start > 0 and not (
        ir_ops[start].op == IROpType.PICK_UP_TIP and ir_ops[start].pipette == old_pipette
    ):
        start -= 1

    end = idx
    while end < len(ir_ops) - 1 and not (
        ir_ops[end].op == IROpType.DROP_TIP and ir_ops[end].pipette == old_pipette
    ):
        end += 1

    changed = 0
    for op in ir_ops[start : end + 1]:
        if op.pipette == old_pipette:
            op.pipette = new_pipette
            changed += 1
        if op.op == IROpType.MIX and op.volume_ul is not None:
            op.volume_ul = mix_volume_for(op.volume_ul, new_pipette)
    return changed


def _same_violations(a: List[Violation], b: List[Violation]) -> bool:
    return [(v.violation_type, v.action_idx) for v in a] == [
        (v.violation_type, v.action_idx) for v in b
    ]


def _violation_still_applies(ir_ops: List[IROp], idx: int, violation: Violation) -> bool:
    action = ir_ops[idx]
    if violation.violation_type == "PIPETTE_RANGE_VIOLATION":
        return _pipette_range_invalid(action)
    if violation.violation_type == "TIP_OVER_CAPACITY":
        return _pipette_range_invalid(action)
    if violation.violation_type == "MISSING_MIX":
        if action.op != IROpType.DISPENSE or not action.destination:
            return False
        return not any(
            op.op == IROpType.MIX and op.location == action.destination
            for op in ir_ops[idx + 1 : idx + 4]
        )
    return True


def _pipette_range_invalid(action: IROp) -> bool:
    if action.volume_ul is None or action.pipette is None:
        return False
    if action.pipette == "p20":
        return action.volume_ul < 1 or action.volume_ul > 20
    if action.pipette == "p300":
        return action.volume_ul < 20 or action.volume_ul > 300
    return False


def _covered_by_prior_no_tip_aspirate(
    idx: int, pipette: str, aspirate_no_tip: set[tuple[int, str]]
) -> bool:
    return any(
        prior_idx < idx and prior_pipette == pipette
        for prior_idx, prior_pipette in aspirate_no_tip
    )
