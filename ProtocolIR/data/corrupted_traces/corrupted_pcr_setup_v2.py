"""
Corrupted Opentrons Script: PCR Master Mix Setup (v2 - Well Overflow & Missing Mix)
"""

from opentrons import protocol_api

metadata = {
    "apiLevel": "2.14",
    "protocolName": "PCR Master Mix Setup - Corrupted (Overflow)",
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

    # Step 1: Distribute DNA templates (OK)
    for i in range(12):
        p20.pick_up_tip()
        p20.aspirate(10, template_rack[f"A{i+1}"])
        p20.dispense(10, plate[f"A{i+1}"])
        p20.drop_tip()

    # Step 2: Distribute master mix
    # BUG: Using 100 µL instead of 40 µL (well capacity is 200 µL, now 110 + 100 = 210, OVERFLOW!)
    for col in range(12):
        for row in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            well = f"{row}{col+1}"

            p300.pick_up_tip()
            p300.aspirate(100, master_mix_rack["A1"])  # BUG: Too much volume!
            p300.dispense(100, plate[well])  # BUG: Will overflow well (10 + 100 > 200 capacity)
            # MISSING: p300.mix() step - no mixing after reagent addition
            p300.drop_tip()
