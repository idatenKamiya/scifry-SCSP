"""
Corrupted Opentrons Script: PCR Master Mix Setup (v1 - Cross-Contamination)
This demonstrates common LLM mistakes that create safety violations.
"""

from opentrons import protocol_api

metadata = {
    "apiLevel": "2.14",
    "protocolName": "PCR Master Mix Setup - Corrupted (Cross-Contamination)",
    "description": "Setup PCR reactions - UNSAFE VERSION",
}


def run(protocol: protocol_api.ProtocolContext):
    # Load labware
    plate = protocol.load_labware("biorad_96_wellplate_200ul_pcr", 1)
    template_rack = protocol.load_labware(
        "opentrons_24_tuberack_nest_1.5ml_snapcap", 2
    )
    master_mix_rack = protocol.load_labware(
        "opentrons_24_tuberack_nest_1.5ml_snapcap", 3
    )
    tiprack_20 = protocol.load_labware("opentrons_96_tiprack_20ul", 4)
    tiprack_300 = protocol.load_labware("opentrons_96_tiprack_300ul", 5)

    # Load instruments
    p20 = protocol.load_instrument("p20_single_gen2", "left", tip_racks=[tiprack_20])
    p300 = protocol.load_instrument(
        "p300_single_gen2", "right", tip_racks=[tiprack_300]
    )

    # Step 1: Distribute DNA templates
    # BUG: Reusing the SAME TIP across different DNA samples (cross-contamination)
    p20.pick_up_tip()  # Only pick up ONE tip for the entire step

    for i in range(12):  # All 12 samples
        # BUG: No fresh tip between samples - allows cross-contamination
        p20.aspirate(10, template_rack[f"A{i+1}"])
        p20.dispense(10, plate[f"A{i+1}"])
        # MISSING: p20.drop_tip() + p20.pick_up_tip()

    p20.drop_tip()  # Only drop tip at the end

    # Step 2: Distribute master mix
    # BUG: Using p20 for 40 µL transfer (range violation - p20 max is 20µL)
    for col in range(12):  # All 12 columns
        for row in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            well = f"{row}{col+1}"

            p20.pick_up_tip()  # Wrong pipette size!
            p20.aspirate(40, master_mix_rack["A1"])  # BUG: 40 µL exceeds p20 range
            p20.dispense(40, plate[well])
            p20.drop_tip()

    # BUG: No mixing step (will cause precipitation and inconsistent reactions)
