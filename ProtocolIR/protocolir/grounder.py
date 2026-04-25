"""
LAYER 2: Grounding Engine
Maps abstract location hints to concrete deck positions and labware.
"""

from typing import List, Dict, Optional, Tuple
from protocolir.schemas import (
    GroundedAction,
    SemanticAction,
    ParsedProtocol,
    Material,
    ReagentClass,
)


# Default deck layout for PCR/qPCR protocols
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
}


def resolve_location(
    location_hint: Optional[str], deck: Dict = None, materials: List[Material] = None
) -> Optional[str]:
    """
    Resolve an abstract location hint to a concrete deck position.

    Examples:
        "DNA template" -> "template_rack/A1"
        "PCR plate" -> "plate/A1"
        "master mix tube" -> "master_mix_rack/A1"

    Args:
        location_hint: Abstract location description
        deck: Deck layout dictionary
        materials: List of materials for context

    Returns:
        Resolved location string (e.g., "template_rack/A1") or None if unresolvable
    """

    if not location_hint:
        return None

    if deck is None:
        deck = DEFAULT_DECK

    location_hint_lower = location_hint.lower()

    # Direct mappings
    location_maps = {
        "pcr plate": "plate/A1",
        "pcr_plate": "plate/A1",
        "96-well plate": "plate/A1",
        "96 well plate": "plate/A1",
        "dna template": "template_rack/A1",
        "template": "template_rack/A1",
        "template tube": "template_rack/A1",
        "master mix": "master_mix_rack/A1",
        "master_mix": "master_mix_rack/A1",
        "master mix tube": "master_mix_rack/A1",
    }

    for hint, location in location_maps.items():
        if hint in location_hint_lower:
            return location

    # If it already looks like a well location, return as-is
    if "/" in location_hint:
        return location_hint

    # Fallback
    return None


def ground_actions(
    parsed: ParsedProtocol, deck: Dict = None
) -> List[GroundedAction]:
    """
    Ground semantic actions to concrete deck locations.

    Args:
        parsed: ParsedProtocol with semantic actions
        deck: Optional custom deck layout

    Returns:
        List of GroundedAction objects with resolved locations
    """

    if deck is None:
        deck = DEFAULT_DECK

    grounded = []

    for action in parsed.actions:
        source_location = resolve_location(action.source_hint, deck, parsed.materials)
        dest_location = resolve_location(
            action.destination_hint, deck, parsed.materials
        )

        # Infer well indices based on materials and action type
        if source_location and "/" not in source_location:
            source_location = infer_well_index(
                source_location, action.reagent, "source", parsed.materials
            )

        if dest_location and "/" not in dest_location:
            dest_location = infer_well_index(
                dest_location, action.reagent, "destination", parsed.materials
            )

        grounded_action = GroundedAction(
            action_type=action.action_type,
            reagent=action.reagent,
            volume_ul=action.volume_ul,
            source=source_location,
            destination=dest_location,
            repetitions=action.repetitions,
            constraints=action.constraints,
            source_location_type=get_location_type(source_location, deck),
            dest_location_type=get_location_type(dest_location, deck),
        )

        grounded.append(grounded_action)

    return grounded


def infer_well_index(
    location: str, reagent: Optional[str], direction: str, materials: List[Material]
) -> str:
    """
    Infer specific well index if not explicitly provided.

    Args:
        location: Location string (may be partial)
        reagent: Reagent name for context
        direction: "source" or "destination"
        materials: List of materials

    Returns:
        Location with well index (e.g., "template_rack/A1")
    """

    if "/" in location:
        return location

    # For template racks, distribute materials across A1, A2, A3, etc.
    if "template_rack" in location:
        if reagent:
            # Find which template this is
            template_materials = [
                m
                for m in materials
                if m.reagent_class in [ReagentClass.TEMPLATE, ReagentClass.PRIMER]
            ]
            for i, mat in enumerate(template_materials):
                if mat.name.lower() in reagent.lower():
                    well = f"A{i+1}"
                    return f"template_rack/{well}"
        return f"template_rack/A1"

    # For master mix, typically A1
    if "master_mix_rack" in location:
        return f"master_mix_rack/A1"

    # For PCR plate, start at A1 and distribute across plate
    if "plate" in location:
        return f"plate/A1"

    return location


def get_location_type(location: Optional[str], deck: Dict = None) -> Optional[str]:
    """Determine the type of location (e.g., 'plate', 'tube_rack', 'tiprack')."""

    if not location:
        return None

    if deck is None:
        deck = DEFAULT_DECK

    rack_name = location.split("/")[0]

    for deck_item in deck.values():
        if deck_item.get("alias") == rack_name:
            if "tiprack" in deck_item.get("labware", "").lower():
                return "tiprack"
            elif "96" in deck_item.get("labware", "").lower() or "plate" in deck_item.get(
                "labware", ""
            ).lower():
                return "plate"
            else:
                return "tube_rack"

    return None


def build_deck_layout(num_samples: int = 8) -> Dict:
    """
    Build a deck layout based on number of samples.

    Args:
        num_samples: Number of DNA samples to process

    Returns:
        Customized deck layout dictionary
    """

    deck = DEFAULT_DECK.copy()

    # Could customize based on sample count
    # For now, return default which works for up to 96 samples

    return deck


def validate_deck_compatibility(grounded: List[GroundedAction], deck: Dict) -> List[str]:
    """
    Validate that all grounded locations exist in the deck.

    Returns:
        List of validation errors, empty if valid
    """

    errors = []

    for action in grounded:
        if action.source and action.source not in ["unknown", "user_input"]:
            rack_name = action.source.split("/")[0]
            if rack_name not in [v.get("alias") for v in deck.values()]:
                errors.append(f"Unknown source rack: {rack_name}")

        if action.destination and action.destination not in ["unknown", "user_input"]:
            rack_name = action.destination.split("/")[0]
            if rack_name not in [v.get("alias") for v in deck.values()]:
                errors.append(f"Unknown destination rack: {rack_name}")

    return errors
