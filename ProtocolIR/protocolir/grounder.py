"""Layer 2: map semantic actions to concrete OT-2 deck locations."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

from protocolir.schemas import (
    GroundedAction,
    Material,
    ParsedProtocol,
    ReagentClass,
    SemanticActionType,
)


DEFAULT_DECK = {
    "PCR_plate": {
        "labware": "biorad_96_wellplate_200ul_pcr",
        "opentrons_name": "biorad_96_wellplate_200ul_pcr",
        "slot": 1,
        "alias": "plate",
        "max_volume_ul": 200,
        "well_count": 96,
    },
    "template_rack": {
        "labware": "opentrons_24_tuberack_nest_1.5ml_snapcap",
        "opentrons_name": "opentrons_24_tuberack_nest_1.5ml_snapcap",
        "slot": 2,
        "alias": "template_rack",
        "max_volume_ul": 1500,
        "well_count": 24,
    },
    "master_mix_rack": {
        "labware": "opentrons_24_tuberack_nest_1.5ml_snapcap",
        "opentrons_name": "opentrons_24_tuberack_nest_1.5ml_snapcap",
        "slot": 3,
        "alias": "master_mix_rack",
        "max_volume_ul": 1500,
        "well_count": 24,
    },
    "tiprack_20": {
        "labware": "opentrons_96_tiprack_20ul",
        "opentrons_name": "opentrons_96_tiprack_20ul",
        "slot": 4,
        "alias": "tiprack_20",
        "max_volume_ul": 20,
        "well_count": 96,
    },
    "tiprack_300": {
        "labware": "opentrons_96_tiprack_300ul",
        "opentrons_name": "opentrons_96_tiprack_300ul",
        "slot": 5,
        "alias": "tiprack_300",
        "max_volume_ul": 300,
        "well_count": 96,
    },
    "template_plate": {
        "labware": "nest_96_wellplate_100ul_pcr_full_skirt",
        "opentrons_name": "nest_96_wellplate_100ul_pcr_full_skirt",
        "slot": 6,
        "alias": "template_plate",
        "max_volume_ul": 100,
        "well_count": 96,
    },
}


def build_deck_layout(num_samples: int = 8) -> Dict:
    """Build a conservative PCR/qPCR deck layout."""

    deck = deepcopy(DEFAULT_DECK)
    if num_samples <= 24:
        # Keep the 96-well source plate out of small demos to simplify the deck.
        deck.pop("template_plate", None)
    return deck


def ground_actions(parsed: ParsedProtocol, deck: Dict = None) -> List[GroundedAction]:
    """Ground semantic actions to deck aliases and well addresses."""

    deck = deepcopy(deck) if deck is not None else build_deck_layout(parsed.sample_count)
    destination_wells = plate_wells(parsed.sample_count)
    grounded: List[GroundedAction] = []

    for action in parsed.actions:
        reagent_class = _class_for_reagent(action.reagent, parsed.materials)

        if action.action_type == SemanticActionType.TRANSFER:
            sources = _sources_for_transfer(action.source_hint, reagent_class, parsed.sample_count)
            destinations = _destinations_for_transfer(action.destination_hint, parsed.sample_count)
            grounded.append(
                GroundedAction(
                    action_type=action.action_type,
                    reagent=action.reagent,
                    volume_ul=action.volume_ul,
                    source=sources[0] if sources else None,
                    destination=destinations[0] if destinations else None,
                    sources=sources,
                    destinations=destinations,
                    repetitions=action.repetitions,
                    constraints=action.constraints,
                    source_location_type=get_location_type(sources[0], deck) if sources else None,
                    dest_location_type=get_location_type(destinations[0], deck) if destinations else None,
                )
            )
            continue

        if action.action_type == SemanticActionType.MIX:
            grounded.append(
                GroundedAction(
                    action_type=action.action_type,
                    reagent=action.reagent,
                    volume_ul=action.volume_ul,
                    destination=destination_wells[0],
                    destinations=destination_wells,
                    repetitions=action.repetitions,
                    constraints=action.constraints,
                    dest_location_type="plate",
                )
            )
            continue

        location = resolve_location(action.destination_hint or action.source_hint, deck, parsed.materials)
        grounded.append(
            GroundedAction(
                action_type=action.action_type,
                reagent=action.reagent,
                volume_ul=action.volume_ul,
                source=location,
                destination=location,
                sources=[location] if location else [],
                destinations=[location] if location else [],
                repetitions=action.repetitions,
                constraints=action.constraints,
                source_location_type=get_location_type(location, deck),
                dest_location_type=get_location_type(location, deck),
            )
        )

    return grounded


def resolve_location(
    location_hint: Optional[str], deck: Dict = None, materials: List[Material] = None
) -> Optional[str]:
    """Resolve a natural-language location hint to an alias/well string."""

    if not location_hint:
        return None

    hint = location_hint.lower()
    if "/" in location_hint:
        return location_hint
    if "plate" in hint or "well" in hint:
        return "plate/A1"
    if "master" in hint or "mix" in hint or "water" in hint:
        return "master_mix_rack/A1"
    if "primer" in hint:
        return "template_rack/B1"
    if "template" in hint or "dna" in hint or "sample" in hint:
        return "template_rack/A1"
    return None


def validate_deck_compatibility(grounded: List[GroundedAction], deck: Dict) -> List[str]:
    """Validate that grounded aliases exist in the selected deck."""

    aliases = {item["alias"] for item in deck.values()}
    errors = []
    for action in grounded:
        for location in action.sources + action.destinations:
            if not location or "/" not in location:
                continue
            alias = location.split("/", 1)[0]
            if alias not in aliases:
                errors.append(f"Unknown deck alias '{alias}' in {location}")
    return errors


def plate_wells(count: int) -> List[str]:
    return [f"plate/{well}" for well in well_names(96)[:count]]


def source_wells(count: int) -> List[str]:
    if count <= 24:
        return [f"template_rack/{well}" for well in well_names(24)[:count]]
    return [f"template_plate/{well}" for well in well_names(96)[:count]]


def well_names(well_count: int) -> List[str]:
    if well_count == 24:
        rows, cols = "ABCD", range(1, 7)
    elif well_count == 384:
        rows, cols = "ABCDEFGHIJKLMNOP", range(1, 25)
    else:
        rows, cols = "ABCDEFGH", range(1, 13)
    return [f"{row}{col}" for row in rows for col in cols]


def get_location_type(location: Optional[str], deck: Dict = None) -> Optional[str]:
    if not location or "/" not in location:
        return None
    deck = deck or DEFAULT_DECK
    alias = location.split("/", 1)[0]
    for item in deck.values():
        if item.get("alias") != alias:
            continue
        labware = item.get("labware", "").lower()
        if "tiprack" in labware:
            return "tiprack"
        if "plate" in labware:
            return "plate"
        return "tube_rack"
    return None


def _destinations_for_transfer(destination_hint: Optional[str], sample_count: int) -> List[str]:
    resolved = resolve_location(destination_hint)
    if resolved and resolved.startswith("plate/"):
        return plate_wells(sample_count)
    if resolved:
        return [resolved]
    return plate_wells(sample_count)


def _sources_for_transfer(
    source_hint: Optional[str], reagent_class: ReagentClass, sample_count: int
) -> List[str]:
    if reagent_class in {ReagentClass.TEMPLATE, ReagentClass.PRIMER}:
        if reagent_class == ReagentClass.PRIMER and sample_count <= 24:
            return ["template_rack/B1"] * sample_count
        return source_wells(sample_count)

    resolved = resolve_location(source_hint)
    if resolved:
        return [resolved] * sample_count

    if reagent_class in {ReagentClass.MASTER_MIX, ReagentClass.WATER, ReagentClass.BUFFER}:
        return ["master_mix_rack/A1"] * sample_count

    return ["master_mix_rack/A1"] * sample_count


def _class_for_reagent(reagent: Optional[str], materials: List[Material]) -> ReagentClass:
    if not reagent:
        return ReagentClass.UNKNOWN
    reagent_lower = reagent.lower()
    for material in materials:
        if material.name.lower() in reagent_lower or reagent_lower in material.name.lower():
            return material.reagent_class
    if "template" in reagent_lower or "dna" in reagent_lower or "sample" in reagent_lower:
        return ReagentClass.TEMPLATE
    if "primer" in reagent_lower:
        return ReagentClass.PRIMER
    if "master" in reagent_lower or "mix" in reagent_lower:
        return ReagentClass.MASTER_MIX
    if "water" in reagent_lower:
        return ReagentClass.WATER
    return ReagentClass.UNKNOWN
