"""
LAYER 3: Typed Intermediate Representation Builder
Converts grounded actions into strict, machine-readable IR.
"""

from typing import List, Dict, Optional
from protocolir.schemas import (
    IROp,
    IROpType,
    GroundedAction,
    SemanticActionType,
    ParsedProtocol,
)
from protocolir.grounder import DEFAULT_DECK


def build_ir(grounded_actions: List[GroundedAction], deck: Dict = None) -> List[IROp]:
    """
    Convert grounded actions into typed IR operations.

    The IR is the definitive machine-readable representation.
    Each IROp maps directly to robot commands.

    Args:
        grounded_actions: List of grounded actions with resolved locations
        deck: Deck layout specification

    Returns:
        List of IROp objects representing the complete protocol
    """

    if deck is None:
        deck = DEFAULT_DECK

    ir = []

    # Step 1: Load all labware
    ir.extend(build_labware_loads(deck))

    # Step 2: Load all instruments
    ir.extend(build_instrument_loads(deck))

    # Step 3: Convert actions to IR operations
    for action in grounded_actions:
        if action.action_type == SemanticActionType.TRANSFER:
            ir.extend(build_transfer_operations(action))

        elif action.action_type == SemanticActionType.MIX:
            ir.extend(build_mix_operations(action))

        elif action.action_type == SemanticActionType.DELAY:
            ir.extend(build_delay_operations(action))

        elif action.action_type == SemanticActionType.INCUBATE:
            ir.extend(build_incubate_operations(action))

        elif action.action_type == SemanticActionType.TEMPERATURE:
            ir.extend(build_temperature_operations(action))

        elif action.action_type == SemanticActionType.COMMENT:
            pass  # Comments don't need IR ops

    return ir


def build_labware_loads(deck: Dict) -> List[IROp]:
    """Generate LoadLabware IR operations for all deck items."""

    ops = []

    for deck_item in deck.values():
        op = IROp(
            op=IROpType.LOAD_LABWARE,
            name=deck_item.get("opentrons_name"),
            opentrons_name=deck_item.get("opentrons_name"),
            slot=deck_item.get("slot"),
            alias=deck_item.get("alias"),
            max_volume_ul=deck_item.get("max_volume_ul"),
            well_count=deck_item.get("well_count"),
        )
        ops.append(op)

    return ops


def build_instrument_loads(deck: Dict) -> List[IROp]:
    """Generate LoadInstrument IR operations."""

    ops = [
        IROp(
            op=IROpType.LOAD_INSTRUMENT,
            name="p20_single_gen2",
            opentrons_name="p20_single_gen2",
            mount="left",
            tipracks=["tiprack_20"],
            min_volume=1,
            max_volume=20,
        ),
        IROp(
            op=IROpType.LOAD_INSTRUMENT,
            name="p300_single_gen2",
            opentrons_name="p300_single_gen2",
            mount="right",
            tipracks=["tiprack_300"],
            min_volume=30,
            max_volume=300,
        ),
    ]

    return ops


def build_transfer_operations(action: GroundedAction) -> List[IROp]:
    """
    Build IR operations for a transfer action.

    Generates: PickUpTip -> Aspirate -> Dispense -> (optional Mix) -> DropTip
    """

    ops = []

    if not action.source or not action.destination:
        return ops

    volume = action.volume_ul or 10  # Default 10 µL if not specified
    pipette = select_pipette(volume)

    # Pick up tip
    ops.append(
        IROp(
            op=IROpType.PICK_UP_TIP,
            pipette=pipette,
        )
    )

    # Aspirate
    ops.append(
        IROp(
            op=IROpType.ASPIRATE,
            pipette=pipette,
            volume_ul=volume,
            source=action.source,
            reagent=action.reagent,
        )
    )

    # Dispense
    ops.append(
        IROp(
            op=IROpType.DISPENSE,
            pipette=pipette,
            volume_ul=volume,
            destination=action.destination,
        )
    )

    # Mix after dispense (common best practice)
    if action.destination and "plate" in action.destination:
        mix_volume = min(volume * 0.8, 20)  # Mix at 80% of transfer volume, max 20µL
        ops.append(
            IROp(
                op=IROpType.MIX,
                pipette=pipette,
                volume_ul=mix_volume,
                location=action.destination,
                repetitions=3,
            )
        )

    # Drop tip
    ops.append(
        IROp(
            op=IROpType.DROP_TIP,
            pipette=pipette,
        )
    )

    return ops


def build_mix_operations(action: GroundedAction) -> List[IROp]:
    """Build IR operations for mixing."""

    ops = []

    if not action.destination:
        return ops

    volume = action.volume_ul or 10
    repetitions = action.repetitions or 3
    pipette = select_pipette(volume)

    # Pick up tip if not already holding one
    ops.append(IROp(op=IROpType.PICK_UP_TIP, pipette=pipette))

    ops.append(
        IROp(
            op=IROpType.MIX,
            pipette=pipette,
            volume_ul=volume,
            location=action.destination,
            repetitions=repetitions,
        )
    )

    ops.append(IROp(op=IROpType.DROP_TIP, pipette=pipette))

    return ops


def build_delay_operations(action: GroundedAction) -> List[IROp]:
    """Build IR operations for delays/incubation."""

    ops = []

    # Extract delay time from constraints or volume_ul (repurposed)
    delay_seconds = action.volume_ul or 60  # Default 60 seconds

    ops.append(
        IROp(
            op=IROpType.DELAY,
            delay_seconds=delay_seconds,
        )
    )

    return ops


def build_incubate_operations(action: GroundedAction) -> List[IROp]:
    """Build IR operations for incubation."""

    ops = []

    # Extract temperature from constraints or use default
    temp_c = 37  # Default room temperature
    if "cold" in " ".join(action.constraints).lower():
        temp_c = 4

    delay_seconds = action.volume_ul or 300  # Default 5 minutes

    ops.append(
        IROp(
            op=IROpType.SET_TEMPERATURE,
            temperature_c=temp_c,
        )
    )

    ops.append(
        IROp(
            op=IROpType.INCUBATE,
            delay_seconds=delay_seconds,
            temperature_c=temp_c,
            location=action.destination,
        )
    )

    return ops


def build_temperature_operations(action: GroundedAction) -> List[IROp]:
    """Build IR operations for temperature control."""

    ops = []

    temp_c = 37  # Default
    if action.volume_ul:
        temp_c = action.volume_ul  # Repurposed field for temperature

    ops.append(
        IROp(
            op=IROpType.SET_TEMPERATURE,
            temperature_c=temp_c,
        )
    )

    return ops


def select_pipette(volume_ul: float) -> str:
    """
    Select appropriate pipette based on volume.

    Args:
        volume_ul: Volume in microliters

    Returns:
        Pipette name (p20_single_gen2 or p300_single_gen2)
    """

    if volume_ul <= 20:
        return "p20_single_gen2"
    else:
        return "p300_single_gen2"


def ir_to_dict_list(ir_ops: List[IROp]) -> List[Dict]:
    """Convert IR operations to dictionaries for serialization."""

    return [op.model_dump(exclude_none=True) for op in ir_ops]


def dict_list_to_ir(data: List[Dict]) -> List[IROp]:
    """Convert list of dicts back to IR operations."""

    return [IROp(**d) for d in data]
