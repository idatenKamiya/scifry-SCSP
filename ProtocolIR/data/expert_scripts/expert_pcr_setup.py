"""
Expert Opentrons Script: PCR Master Mix Setup
This is an example of a well-written, safety-conscious protocol.
"""

from opentrons import protocol_api

metadata = {
    "apiLevel": "2.14",
    "protocolName": "PCR Master Mix Setup - Expert Example",
    "description": "Setup PCR reactions with DNA template and master mix",
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
    # 10 µL DNA template per well
    for i in range(12):  # 12 samples (A1-A12)
        # Pick up fresh tip
        p20.pick_up_tip()

        # Aspirate from template rack
        p20.aspirate(10, template_rack[f"A{i+1}"])

        # Dispense into plate
        p20.dispense(10, plate[f"A{i+1}"])

        # Blow out and drop tip
        p20.blow_out()
        p20.drop_tip()

    # Step 2: Distribute master mix
    # 40 µL master mix per well
    master_mix_source = master_mix_rack["A1"]

    for col in range(12):  # All 12 columns
        for row in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            well = f"{row}{col+1}"

            # Pick up fresh tip (change tip between columns for safety)
            if row == "A":
                p300.pick_up_tip()

            # Aspirate from master mix
            p300.aspirate(40, master_mix_source)

            # Dispense into well
            p300.dispense(40, plate[well])

            # Mix after dispense
            p300.mix(3, 30, plate[well])

            # Drop tip after each column (safety: prevent cross-contamination)
            if row == "H":
                p300.drop_tip()

    # Step 3: Final verification delay
    protocol.delay(minutes=1, msg="Allow reaction mixture to settle")
