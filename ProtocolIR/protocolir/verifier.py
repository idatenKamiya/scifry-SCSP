"""
LAYER 4: Hard Safety Verifier
Enforces physical invariants and lab safety constraints.
These violations CANNOT be bypassed.
"""

from typing import List, Dict, Optional
from protocolir.schemas import IROp, IROpType, Violation


class LabState:
    """Tracks current state of the lab during IR verification."""

    def __init__(self):
        self.tip_attached = {"p20_single_gen2": False, "p300_single_gen2": False}
        self.tip_reagent = {"p20_single_gen2": None, "p300_single_gen2": None}
        self.current_volume = {"p20_single_gen2": 0.0, "p300_single_gen2": 0.0}
        self.well_volumes = {}  # well_id -> current volume
        self.loaded_labware = {}  # alias -> spec
        self.loaded_instruments = {}  # name -> spec
        self.last_action = None


def verify_ir(ir_ops: List[IROp]) -> List[Violation]:
    """
    Verify IR operations against hard safety constraints.

    Args:
        ir_ops: List of IR operations to verify

    Returns:
        List of Violation objects representing constraint violations
    """

    state = LabState()
    violations = []

    for action_idx, action in enumerate(ir_ops):
        # Track loaded labware and instruments
        if action.op == IROpType.LOAD_LABWARE:
            state.loaded_labware[action.alias] = action
            state.well_volumes[action.alias] = {}

        elif action.op == IROpType.LOAD_INSTRUMENT:
            state.loaded_instruments[action.name] = action

        # Verify pick up tip
        elif action.op == IROpType.PICK_UP_TIP:
            pipette = action.pipette
            if pipette not in state.tip_attached:
                violations.append(
                    Violation(
                        violation_type="UNKNOWN_PIPETTE",
                        severity="CRITICAL",
                        action_idx=action_idx,
                        message=f"Unknown pipette: {pipette}",
                    )
                )
            else:
                state.tip_attached[pipette] = True
                state.tip_reagent[pipette] = None
                state.current_volume[pipette] = 0.0

        # Verify drop tip
        elif action.op == IROpType.DROP_TIP:
            pipette = action.pipette
            if state.current_volume[pipette] > 0:
                violations.append(
                    Violation(
                        violation_type="DROP_TIP_WITH_LIQUID",
                        severity="CRITICAL",
                        action_idx=action_idx,
                        message=f"Dropping {pipette} while containing {state.current_volume[pipette]:.1f} µL",
                        suggested_fix="Dispense remaining liquid before dropping tip",
                    )
                )
            state.tip_attached[pipette] = False
            state.tip_reagent[pipette] = None

        # Verify aspirate
        elif action.op == IROpType.ASPIRATE:
            pipette = action.pipette

            # Check: Tip attached?
            if not state.tip_attached.get(pipette, False):
                violations.append(
                    Violation(
                        violation_type="ASPIRATE_NO_TIP",
                        severity="CRITICAL",
                        action_idx=action_idx,
                        message=f"{pipette} aspirating without attached tip",
                        suggested_fix=f"Insert 'pick_up_tip()' before aspirate",
                    )
                )

            # Check: Pipette range
            instr = state.loaded_instruments.get(pipette)
            if instr and (
                action.volume_ul < instr.min_volume
                or action.volume_ul > instr.max_volume
            ):
                violations.append(
                    Violation(
                        violation_type="PIPETTE_RANGE_VIOLATION",
                        severity="CRITICAL",
                        action_idx=action_idx,
                        message=f"{pipette} range {instr.min_volume}-{instr.max_volume} µL, attempted {action.volume_ul:.1f} µL",
                        suggested_fix=f"Use p300_single_gen2 for volumes >20 µL",
                    )
                )

            # Check: Source exists
            if action.source:
                source_rack = action.source.split("/")[0]
                if source_rack not in state.loaded_labware:
                    violations.append(
                        Violation(
                            violation_type="UNKNOWN_SOURCE",
                            severity="CRITICAL",
                            action_idx=action_idx,
                            message=f"Source rack '{source_rack}' not loaded",
                        )
                    )

            # Check: Cross-contamination (different reagent on same tip)
            if action.reagent and state.tip_reagent[pipette]:
                if (
                    state.tip_reagent[pipette] != action.reagent
                    and state.tip_reagent[pipette] is not None
                ):
                    violations.append(
                        Violation(
                            violation_type="CROSS_CONTAMINATION",
                            severity="CRITICAL",
                            action_idx=action_idx,
                            message=f"Reusing tip: had {state.tip_reagent[pipette]}, now aspirating {action.reagent}",
                            suggested_fix="Change tip before aspirating different reagent",
                        )
                    )

            # Update state
            state.current_volume[pipette] = action.volume_ul or 0.0
            state.tip_reagent[pipette] = action.reagent

        # Verify dispense
        elif action.op == IROpType.DISPENSE:
            pipette = action.pipette

            # Check: Tip attached?
            if not state.tip_attached.get(pipette, False):
                violations.append(
                    Violation(
                        violation_type="DISPENSE_NO_TIP",
                        severity="CRITICAL",
                        action_idx=action_idx,
                        message=f"{pipette} dispensing without attached tip",
                        suggested_fix="Pick up tip before dispense",
                    )
                )

            # Check: Destination exists
            if action.destination:
                dest_rack = action.destination.split("/")[0]
                if dest_rack not in state.loaded_labware:
                    violations.append(
                        Violation(
                            violation_type="UNKNOWN_DESTINATION",
                            severity="CRITICAL",
                            action_idx=action_idx,
                            message=f"Destination rack '{dest_rack}' not loaded",
                        )
                    )

            # Check: Well overflow
            if action.destination:
                dest_labware = state.loaded_labware.get(
                    action.destination.split("/")[0]
                )
                if dest_labware:
                    current_well_volume = state.well_volumes.get(action.destination, 0.0)
                    if (
                        current_well_volume + (action.volume_ul or 0.0)
                        > dest_labware.max_volume_ul
                    ):
                        violations.append(
                            Violation(
                                violation_type="WELL_OVERFLOW",
                                severity="CRITICAL",
                                action_idx=action_idx,
                                message=f"Well {action.destination} max {dest_labware.max_volume_ul} µL, would have {current_well_volume + (action.volume_ul or 0.0):.1f} µL",
                                suggested_fix="Reduce transfer volume or split across multiple wells",
                            )
                        )
                    # Update state
                    state.well_volumes[action.destination] = (
                        current_well_volume + (action.volume_ul or 0.0)
                    )

            # Update state
            state.current_volume[pipette] = max(
                0.0, (state.current_volume[pipette] or 0.0) - (action.volume_ul or 0.0)
            )

    return violations


def check_semantic_safety(ir_ops: List[IROp]) -> List[Violation]:
    """
    Check for semantic safety issues (not purely physical).

    Examples:
    - Missing mix after reagent addition
    - Not keeping samples on ice
    - Incorrect order of reagent additions
    """

    violations = []

    # Check for aspirate-dispense pairs
    for i, op in enumerate(ir_ops):
        if op.op == IROpType.DISPENSE:
            # Look for preceding aspirate for same pipette
            found_aspirate = False
            for j in range(i - 1, max(0, i - 5), -1):
                if (
                    ir_ops[j].op == IROpType.ASPIRATE
                    and ir_ops[j].pipette == op.pipette
                ):
                    found_aspirate = True
                    break

            if not found_aspirate:
                violations.append(
                    Violation(
                        violation_type="DISPENSE_WITHOUT_ASPIRATE",
                        severity="WARNING",
                        action_idx=i,
                        message="Dispense without preceding aspirate",
                    )
                )

    return violations


def count_violations_by_type(violations: List[Violation]) -> Dict[str, int]:
    """Count violations grouped by type."""

    counts = {}
    for v in violations:
        counts[v.violation_type] = counts.get(v.violation_type, 0) + 1

    return counts


def critical_violations_only(violations: List[Violation]) -> List[Violation]:
    """Filter to only critical violations."""

    return [v for v in violations if v.severity == "CRITICAL"]
