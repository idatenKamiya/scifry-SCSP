"""
LAYER 6: Deterministic Repair Policy
Automatically fixes violations by inserting or modifying IR operations.
"""

from typing import List, Tuple
from protocolir.schemas import IROp, IROpType, Violation


def repair_ir(
    ir_ops: List[IROp], violations: List[Violation]
) -> Tuple[List[IROp], List[str]]:
    """
    Automatically repair IR violations using deterministic rules.

    Args:
        ir_ops: List of IR operations with violations
        violations: List of violations to repair

    Returns:
        Tuple of (repaired_ir_ops, list_of_repairs_applied)
    """

    repaired_ir = ir_ops.copy()
    repairs_applied = []

    # Sort violations by action_idx in reverse so we insert from end to start
    sorted_violations = sorted(violations, key=lambda v: v.action_idx, reverse=True)

    for violation in sorted_violations:
        action_idx = violation.action_idx

        if action_idx >= len(repaired_ir):
            continue  # Action already removed or modified

        action = repaired_ir[action_idx]

        if violation.violation_type == "ASPIRATE_NO_TIP":
            # Insert pick_up_tip before this aspirate
            pipette = action.pipette
            repaired_ir.insert(
                action_idx,
                IROp(op=IROpType.PICK_UP_TIP, pipette=pipette),
            )
            repairs_applied.append(
                f"[{action_idx}] Inserted pick_up_tip before aspirate (no tip)"
            )

        elif violation.violation_type == "DISPENSE_NO_TIP":
            # Insert pick_up_tip before this dispense
            pipette = action.pipette
            repaired_ir.insert(
                action_idx,
                IROp(op=IROpType.PICK_UP_TIP, pipette=pipette),
            )
            repairs_applied.append(
                f"[{action_idx}] Inserted pick_up_tip before dispense (no tip)"
            )

        elif violation.violation_type == "CROSS_CONTAMINATION":
            # Insert drop_tip and pick_up_tip before this aspirate
            pipette = action.pipette
            repaired_ir.insert(action_idx, IROp(op=IROpType.DROP_TIP, pipette=pipette))
            repaired_ir.insert(
                action_idx + 1, IROp(op=IROpType.PICK_UP_TIP, pipette=pipette)
            )
            repairs_applied.append(
                f"[{action_idx}] Inserted tip change before aspirate (cross-contamination)"
            )

        elif violation.violation_type == "DROP_TIP_WITH_LIQUID":
            # Insert dispense before this drop_tip
            # Find the last aspirate for this pipette
            pipette = action.pipette
            last_aspirate_idx = None
            for i in range(action_idx - 1, -1, -1):
                if (
                    repaired_ir[i].op == IROpType.ASPIRATE
                    and repaired_ir[i].pipette == pipette
                ):
                    last_aspirate_idx = i
                    break

            if last_aspirate_idx is not None:
                aspirate = repaired_ir[last_aspirate_idx]
                # Dispense to same location as last aspirate source (or to waste)
                repaired_ir.insert(
                    action_idx,
                    IROp(
                        op=IROpType.DISPENSE,
                        pipette=pipette,
                        volume_ul=aspirate.volume_ul,
                        destination="waste_bin",  # Placeholder
                    ),
                )
                repairs_applied.append(
                    f"[{action_idx}] Inserted dispense before drop_tip (had liquid)"
                )

        elif violation.violation_type == "PIPETTE_RANGE_VIOLATION":
            # Switch pipette if volume is out of range
            volume = action.volume_ul
            if volume and volume > 20:
                # Use p300
                repaired_ir[action_idx].pipette = "p300_single_gen2"
                repairs_applied.append(
                    f"[{action_idx}] Switched to p300_single_gen2 for {volume} µL transfer"
                )
            elif volume and volume < 1:
                # Use p20
                repaired_ir[action_idx].pipette = "p20_single_gen2"
                repairs_applied.append(
                    f"[{action_idx}] Switched to p20_single_gen2 for {volume} µL transfer"
                )

        elif violation.violation_type == "WELL_OVERFLOW":
            # Cannot repair automatically - flag for human
            repairs_applied.append(
                f"[{action_idx}] HUMAN ESCALATION REQUIRED: Well overflow - {violation.message}"
            )

        elif violation.violation_type == "UNKNOWN_SOURCE":
            # Cannot repair - need user input
            repairs_applied.append(
                f"[{action_idx}] HUMAN ESCALATION REQUIRED: Unknown source location"
            )

        elif violation.violation_type == "UNKNOWN_DESTINATION":
            # Cannot repair - need user input
            repairs_applied.append(
                f"[{action_idx}] HUMAN ESCALATION REQUIRED: Unknown destination location"
            )

    return repaired_ir, repairs_applied


def repair_iteratively(
    ir_ops: List[IROp], violations: List[Violation], max_iterations: int = 5
) -> Tuple[List[IROp], List[str], List[Violation]]:
    """
    Repair violations iteratively until no more violations or max iterations reached.

    Args:
        ir_ops: Initial IR operations
        violations: Initial violations
        max_iterations: Maximum repair iterations

    Returns:
        Tuple of (repaired_ir, repairs_applied, remaining_violations)
    """

    current_ir = ir_ops.copy()
    all_repairs = []
    current_violations = violations.copy()

    for iteration in range(max_iterations):
        if not current_violations:
            break  # No more violations

        repaired_ir, repairs = repair_ir(current_ir, current_violations)
        all_repairs.extend(repairs)
        current_ir = repaired_ir

        # Re-verify to find any remaining violations
        from protocolir.verifier import verify_ir

        current_violations = verify_ir(current_ir)

    return current_ir, all_repairs, current_violations


def suggest_repair_for_violation(violation: Violation) -> str:
    """Return human-readable repair suggestion for a violation."""

    if violation.suggested_fix:
        return violation.suggested_fix

    repair_suggestions = {
        "ASPIRATE_NO_TIP": "Pick up a tip before aspirating",
        "DISPENSE_NO_TIP": "Pick up a tip before dispensing",
        "DROP_TIP_WITH_LIQUID": "Dispense remaining liquid before dropping tip",
        "CROSS_CONTAMINATION": "Change to a fresh tip before aspirating different reagent",
        "PIPETTE_RANGE_VIOLATION": "Use p300 for volumes >20µL, p20 for ≤20µL",
        "WELL_OVERFLOW": "Reduce transfer volume or use different wells",
        "UNKNOWN_SOURCE": "Verify source location and add to deck layout",
        "UNKNOWN_DESTINATION": "Verify destination location and add to deck layout",
    }

    return repair_suggestions.get(
        violation.violation_type,
        f"Repair needed for: {violation.violation_type}",
    )


def can_repair_automatically(violation: Violation) -> bool:
    """Check if a violation can be repaired automatically."""

    auto_repairable = [
        "ASPIRATE_NO_TIP",
        "DISPENSE_NO_TIP",
        "DROP_TIP_WITH_LIQUID",
        "CROSS_CONTAMINATION",
        "PIPETTE_RANGE_VIOLATION",
    ]

    return violation.violation_type in auto_repairable


def count_auto_repairable(violations: List[Violation]) -> int:
    """Count how many violations can be auto-repaired."""

    return sum(1 for v in violations if can_repair_automatically(v))
