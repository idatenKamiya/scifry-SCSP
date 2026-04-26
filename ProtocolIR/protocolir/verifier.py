"""Layer 4: hard physical and semantic safety verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from protocolir.grounder import well_names
from protocolir.schemas import IROp, IROpType, Violation


@dataclass
class LabState:
    tip_attached: Dict[str, bool] = field(default_factory=dict)
    tip_reagent: Dict[str, Optional[str]] = field(default_factory=dict)
    current_volume: Dict[str, float] = field(default_factory=dict)
    loaded_labware: Dict[str, IROp] = field(default_factory=dict)
    loaded_instruments: Dict[str, IROp] = field(default_factory=dict)
    well_volumes: Dict[str, float] = field(default_factory=dict)


def verify_ir(ir_ops: List[IROp]) -> List[Violation]:
    """Verify IR operations against constraints that reward cannot override."""

    state = LabState()
    violations: List[Violation] = []

    for idx, action in enumerate(ir_ops):
        if action.op == IROpType.LOAD_LABWARE:
            if not action.alias:
                violations.append(_violation("MISSING_LABWARE_ALIAS", idx, "Labware load missing alias."))
                continue
            state.loaded_labware[action.alias] = action
            continue

        if action.op == IROpType.LOAD_INSTRUMENT:
            if not action.name:
                violations.append(_violation("MISSING_INSTRUMENT_NAME", idx, "Instrument load missing name."))
                continue
            state.loaded_instruments[action.name] = action
            state.tip_attached[action.name] = False
            state.tip_reagent[action.name] = None
            state.current_volume[action.name] = 0.0
            continue

        if action.op == IROpType.PICK_UP_TIP:
            pipette = action.pipette
            if _unknown_pipette(pipette, state):
                violations.append(_unknown_pipette_violation(idx, pipette))
                continue
            if state.tip_attached[pipette]:
                violations.append(
                    _violation(
                        "PICKUP_WITH_TIP_ATTACHED",
                        idx,
                        f"{pipette} already has a tip attached.",
                        severity="WARNING",
                    )
                )
            state.tip_attached[pipette] = True
            state.tip_reagent[pipette] = None
            state.current_volume[pipette] = 0.0
            continue

        if action.op == IROpType.DROP_TIP:
            pipette = action.pipette
            if _unknown_pipette(pipette, state):
                violations.append(_unknown_pipette_violation(idx, pipette))
                continue
            if not state.tip_attached[pipette]:
                violations.append(
                    _violation(
                        "DROP_TIP_WITHOUT_TIP",
                        idx,
                        f"{pipette} attempted to drop a tip when no tip is attached.",
                        severity="WARNING",
                    )
                )
            if state.current_volume[pipette] > 0:
                violations.append(
                    _violation(
                        "DROP_TIP_WITH_LIQUID",
                        idx,
                        f"{pipette} drops a tip containing {state.current_volume[pipette]:.1f} uL.",
                        "Dispense remaining liquid before dropping the tip.",
                        repairable=False,
                    )
                )
            state.tip_attached[pipette] = False
            state.tip_reagent[pipette] = None
            state.current_volume[pipette] = 0.0
            continue

        if action.op == IROpType.ASPIRATE:
            _verify_aspirate(action, idx, state, violations)
            continue

        if action.op == IROpType.DISPENSE:
            _verify_dispense(action, idx, state, violations)
            continue

        if action.op == IROpType.MIX:
            _verify_mix(action, idx, state, violations)
            continue

    violations.extend(check_semantic_safety(ir_ops))
    return violations


def check_semantic_safety(ir_ops: List[IROp]) -> List[Violation]:
    """Check semantic issues that can pass syntax-level robot simulation."""

    violations: List[Violation] = []
    for idx, action in enumerate(ir_ops):
        if action.op != IROpType.DISPENSE or not action.destination:
            continue
        if "plate/" not in action.destination:
            continue
        window = ir_ops[idx + 1 : idx + 4]
        has_mix = any(
            op.op == IROpType.MIX and op.location == action.destination for op in window
        )
        if not has_mix:
            violations.append(
                _violation(
                    "MISSING_MIX",
                    idx,
                    f"Dispense into {action.destination} is not followed by a mix step.",
                    "Insert a mix at the destination well after dispense.",
                    severity="WARNING",
                    repairable=True,
                )
            )
    return violations


def count_violations_by_type(violations: List[Violation]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for violation in violations:
        counts[violation.violation_type] = counts.get(violation.violation_type, 0) + 1
    return counts


def critical_violations_only(violations: List[Violation]) -> List[Violation]:
    return [violation for violation in violations if violation.severity == "CRITICAL"]


def _verify_aspirate(
    action: IROp, idx: int, state: LabState, violations: List[Violation]
) -> None:
    pipette = action.pipette
    if _unknown_pipette(pipette, state):
        violations.append(_unknown_pipette_violation(idx, pipette))
        return

    volume = action.volume_ul or 0.0
    if not state.tip_attached[pipette]:
        violations.append(
            _violation(
                "ASPIRATE_NO_TIP",
                idx,
                f"{pipette} aspirates without an attached tip.",
                "Insert PickUpTip before aspirating.",
                repairable=True,
            )
        )

    _verify_pipette_range(action, idx, state, violations)
    _verify_location(action.source, idx, state, violations, "UNKNOWN_SOURCE", "INVALID_SOURCE")

    if state.current_volume[pipette] + volume > (state.loaded_instruments[pipette].max_volume or 0):
        violations.append(
            _violation(
                "TIP_OVER_CAPACITY",
                idx,
                f"{pipette} would hold {state.current_volume[pipette] + volume:.1f} uL.",
                "Dispense before aspirating more liquid.",
                repairable=False,
            )
        )

    existing_reagent = state.tip_reagent[pipette]
    if existing_reagent and action.reagent and existing_reagent != action.reagent:
        violations.append(
            _violation(
                "CROSS_CONTAMINATION",
                idx,
                f"Tip used for {existing_reagent} is reused for {action.reagent}.",
                "Drop the tip and pick up a fresh tip before this aspirate.",
                repairable=True,
            )
        )

    state.current_volume[pipette] += volume
    if action.reagent:
        state.tip_reagent[pipette] = action.reagent


def _verify_dispense(
    action: IROp, idx: int, state: LabState, violations: List[Violation]
) -> None:
    pipette = action.pipette
    if _unknown_pipette(pipette, state):
        violations.append(_unknown_pipette_violation(idx, pipette))
        return

    volume = action.volume_ul or 0.0
    if not state.tip_attached[pipette]:
        violations.append(
            _violation(
                "DISPENSE_NO_TIP",
                idx,
                f"{pipette} dispenses without an attached tip.",
                "Insert PickUpTip before dispensing.",
                repairable=True,
            )
        )

    if volume > state.current_volume[pipette] + 1e-9:
        violations.append(
            _violation(
                "DISPENSE_MORE_THAN_ASPIRATED",
                idx,
                f"{pipette} dispenses {volume:.1f} uL but only holds {state.current_volume[pipette]:.1f} uL.",
                "Check the transfer pair and volume.",
                repairable=False,
            )
        )

    _verify_location(
        action.destination, idx, state, violations, "UNKNOWN_DESTINATION", "INVALID_DESTINATION"
    )
    _verify_well_capacity(action.destination, volume, idx, state, violations)

    state.current_volume[pipette] = max(0.0, state.current_volume[pipette] - volume)
    if action.destination:
        state.well_volumes[action.destination] = state.well_volumes.get(action.destination, 0.0) + volume


def _verify_mix(action: IROp, idx: int, state: LabState, violations: List[Violation]) -> None:
    pipette = action.pipette
    if _unknown_pipette(pipette, state):
        violations.append(_unknown_pipette_violation(idx, pipette))
        return

    if not state.tip_attached[pipette]:
        violations.append(
            _violation(
                "MIX_NO_TIP",
                idx,
                f"{pipette} mixes without an attached tip.",
                "Insert PickUpTip before mixing.",
                repairable=True,
            )
        )
    _verify_pipette_range(action, idx, state, violations)
    _verify_location(action.location, idx, state, violations, "UNKNOWN_MIX_LOCATION", "INVALID_MIX_LOCATION")


def _verify_pipette_range(
    action: IROp, idx: int, state: LabState, violations: List[Violation]
) -> None:
    pipette = action.pipette
    instrument = state.loaded_instruments.get(pipette or "")
    if not instrument or action.volume_ul is None:
        return
    min_volume = instrument.min_volume or 0
    max_volume = instrument.max_volume or float("inf")
    if action.volume_ul < min_volume or action.volume_ul > max_volume:
        violations.append(
            _violation(
                "PIPETTE_RANGE_VIOLATION",
                idx,
                f"{pipette} range is {min_volume:g}-{max_volume:g} uL; attempted {action.volume_ul:g} uL.",
                "Switch pipette or split the transfer volume.",
                repairable=True,
                details={"volume_ul": action.volume_ul, "pipette": pipette},
            )
        )


def _verify_location(
    location: Optional[str],
    idx: int,
    state: LabState,
    violations: List[Violation],
    unknown_type: str,
    invalid_type: str,
) -> None:
    if not location:
        violations.append(
            _violation(
                unknown_type,
                idx,
                "Operation is missing a source/destination location.",
                "Ground the action to a concrete deck location.",
                repairable=False,
            )
        )
        return
    if "/" not in location:
        violations.append(_violation(invalid_type, idx, f"Location '{location}' is not alias/well formatted."))
        return
    alias, well = location.split("/", 1)
    labware = state.loaded_labware.get(alias)
    if labware is None:
        violations.append(
            _violation(
                unknown_type,
                idx,
                f"Location alias '{alias}' is not loaded on the deck.",
                "Load the referenced labware or update grounding.",
                repairable=False,
            )
        )
        return
    valid_wells = set(well_names(labware.well_count or 96))
    if well not in valid_wells:
        violations.append(
            _violation(
                invalid_type,
                idx,
                f"Well '{well}' is invalid for {alias}.",
                "Use a valid well address for the labware.",
                repairable=False,
            )
        )


def _verify_well_capacity(
    destination: Optional[str],
    volume: float,
    idx: int,
    state: LabState,
    violations: List[Violation],
) -> None:
    if not destination or "/" not in destination:
        return
    alias = destination.split("/", 1)[0]
    labware = state.loaded_labware.get(alias)
    if labware is None:
        return
    current = state.well_volumes.get(destination, 0.0)
    max_volume = labware.max_volume_ul or float("inf")
    if current + volume > max_volume:
        violations.append(
            _violation(
                "WELL_OVERFLOW",
                idx,
                f"{destination} would contain {current + volume:.1f} uL, above {max_volume:g} uL capacity.",
                "Reduce volume or route excess to another well.",
                repairable=False,
                details={"destination": destination, "projected_volume_ul": current + volume},
            )
        )


def _unknown_pipette(pipette: Optional[str], state: LabState) -> bool:
    return pipette is None or pipette not in state.loaded_instruments


def _unknown_pipette_violation(idx: int, pipette: Optional[str]) -> Violation:
    return _violation("UNKNOWN_PIPETTE", idx, f"Unknown pipette '{pipette}'.", repairable=False)


def _violation(
    violation_type: str,
    idx: int,
    message: str,
    suggested_fix: Optional[str] = None,
    *,
    severity: str = "CRITICAL",
    repairable: bool = False,
    details: Optional[Dict] = None,
) -> Violation:
    return Violation(
        violation_type=violation_type,
        severity=severity,  # type: ignore[arg-type]
        action_idx=idx,
        message=message,
        suggested_fix=suggested_fix,
        repairable=repairable,
        details=details or {},
    )
