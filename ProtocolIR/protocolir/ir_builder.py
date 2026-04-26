"""Layer 3: build the typed robot intermediate representation."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, List

from protocolir.grounder import DEFAULT_DECK
from protocolir.schemas import GroundedAction, IROp, IROpType, SemanticActionType


PIPETTES = {
    "p20": {
        "opentrons_name": "p20_single_gen2",
        "mount": "left",
        "tipracks": ["tiprack_20"],
        "min_volume": 1.0,
        "max_volume": 20.0,
    },
    "p300": {
        "opentrons_name": "p300_single_gen2",
        "mount": "right",
        "tipracks": ["tiprack_300"],
        "min_volume": 20.0,
        "max_volume": 300.0,
    },
}


def build_ir(grounded_actions: List[GroundedAction], deck: Dict = None) -> List[IROp]:
    """Convert grounded semantic actions into low-level robot operations."""

    deck = deepcopy(deck or DEFAULT_DECK)
    ir: List[IROp] = []
    ir.extend(build_labware_loads(deck))
    ir.extend(build_instrument_loads())

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
            if action.constraints:
                ir.append(IROp(op=IROpType.COMMENT, comment="; ".join(action.constraints)))

    return ir


def build_labware_loads(deck: Dict) -> List[IROp]:
    ops = []
    for item in sorted(deck.values(), key=lambda x: x.get("slot", 99)):
        ops.append(
            IROp(
                op=IROpType.LOAD_LABWARE,
                name=item["opentrons_name"],
                opentrons_name=item["opentrons_name"],
                slot=item["slot"],
                alias=item["alias"],
                max_volume_ul=item["max_volume_ul"],
                well_count=item["well_count"],
            )
        )
    return ops


def build_instrument_loads(deck: Dict = None) -> List[IROp]:
    return [
        IROp(
            op=IROpType.LOAD_INSTRUMENT,
            name=name,
            alias=name,
            opentrons_name=spec["opentrons_name"],
            mount=spec["mount"],
            tipracks=spec["tipracks"],
            min_volume=spec["min_volume"],
            max_volume=spec["max_volume"],
        )
        for name, spec in PIPETTES.items()
    ]


def build_transfer_operations(action: GroundedAction) -> List[IROp]:
    """Build pick/aspirate/dispense/mix/drop operations for each transfer."""

    volume = action.volume_ul or 10.0
    sources = action.sources or ([action.source] if action.source else [])
    destinations = action.destinations or ([action.destination] if action.destination else [])
    pairs = list(_pair_sources_destinations(sources, destinations))
    ops: List[IROp] = []

    for source, destination in pairs:
        remaining = volume
        chunks = split_volume(remaining)
        for chunk_idx, chunk in enumerate(chunks):
            pipette = select_pipette(chunk)
            ops.append(IROp(op=IROpType.PICK_UP_TIP, pipette=pipette))
            ops.append(
                IROp(
                    op=IROpType.ASPIRATE,
                    pipette=pipette,
                    volume_ul=chunk,
                    source=source,
                    reagent=action.reagent,
                )
            )
            ops.append(
                IROp(
                    op=IROpType.DISPENSE,
                    pipette=pipette,
                    volume_ul=chunk,
                    destination=destination,
                    reagent=action.reagent,
                )
            )
            if chunk_idx == len(chunks) - 1 and _should_mix_after_transfer(action, destination):
                ops.append(
                    IROp(
                        op=IROpType.MIX,
                        pipette=pipette,
                        volume_ul=mix_volume_for(chunk, pipette),
                        location=destination,
                        repetitions=3,
                    )
                )
            ops.append(IROp(op=IROpType.DROP_TIP, pipette=pipette))

    return ops


def build_mix_operations(action: GroundedAction) -> List[IROp]:
    volume = action.volume_ul or 10.0
    repetitions = action.repetitions or 3
    locations = action.destinations or ([action.destination] if action.destination else [])
    ops: List[IROp] = []

    for location in locations:
        pipette = select_pipette(volume)
        ops.append(IROp(op=IROpType.PICK_UP_TIP, pipette=pipette))
        ops.append(
            IROp(
                op=IROpType.MIX,
                pipette=pipette,
                volume_ul=mix_volume_for(volume, pipette),
                location=location,
                repetitions=repetitions,
            )
        )
        ops.append(IROp(op=IROpType.DROP_TIP, pipette=pipette))

    return ops


def build_delay_operations(action: GroundedAction) -> List[IROp]:
    return [IROp(op=IROpType.DELAY, delay_seconds=action.volume_ul or 60)]


def build_incubate_operations(action: GroundedAction) -> List[IROp]:
    constraints = " ".join(action.constraints).lower()
    temperature = 4.0 if "cold" in constraints or "ice" in constraints else 37.0
    return [
        IROp(op=IROpType.SET_TEMPERATURE, temperature_c=temperature),
        IROp(
            op=IROpType.INCUBATE,
            delay_seconds=action.volume_ul or 300,
            temperature_c=temperature,
            location=action.destination,
        ),
    ]


def build_temperature_operations(action: GroundedAction) -> List[IROp]:
    return [IROp(op=IROpType.SET_TEMPERATURE, temperature_c=action.volume_ul or 37)]


def select_pipette(volume_ul: float) -> str:
    if volume_ul <= PIPETTES["p20"]["max_volume"]:
        return "p20"
    return "p300"


def split_volume(volume_ul: float) -> List[float]:
    """Split transfers above p300 capacity into safe chunks."""

    if volume_ul <= PIPETTES["p300"]["max_volume"]:
        return [volume_ul]
    chunks = []
    remaining = volume_ul
    while remaining > 0:
        chunk = min(PIPETTES["p300"]["max_volume"], remaining)
        chunks.append(chunk)
        remaining -= chunk
    return chunks


def mix_volume_for(volume_ul: float, pipette: str) -> float:
    max_volume = PIPETTES[pipette]["max_volume"]
    min_volume = PIPETTES[pipette]["min_volume"]
    return max(min_volume, min(max_volume, round(volume_ul * 0.8, 2)))


def ir_to_dict_list(ir_ops: List[IROp]) -> List[Dict]:
    return [op.model_dump(exclude_none=True) for op in ir_ops]


def dict_list_to_ir(data: List[Dict]) -> List[IROp]:
    return [IROp(**item) for item in data]


def _pair_sources_destinations(sources: List[str], destinations: List[str]) -> Iterable[tuple[str, str]]:
    if not sources or not destinations:
        return []
    if len(sources) == 1 and len(destinations) > 1:
        return [(sources[0], destination) for destination in destinations]
    if len(destinations) == 1 and len(sources) > 1:
        return [(source, destinations[0]) for source in sources]
    return list(zip(sources, destinations))


def _should_mix_after_transfer(action: GroundedAction, destination: str) -> bool:
    if not destination or "plate/" not in destination:
        return False
    constraints = " ".join(action.constraints).lower()
    if "do not mix" in constraints:
        return False
    return True
