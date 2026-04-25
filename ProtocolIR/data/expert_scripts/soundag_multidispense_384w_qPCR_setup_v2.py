# Script name: multidispense_384w_qPCR_setup_v2.py
# Directory path: C:\Users\Max\PycharmProjects\pythonProject\ot2_scripting
# Command line simulation = opentrons_simulate.exe multidispense_384w_qPCR_setup_v2.py -e

# SECOND VERSION OF SCRIPT
# UPDATES: simplified/condensed all codelines, cleaned up unused variables

from opentrons import protocol_api

metadata = {
    'apiLevel': '2.8',
    'protocolName': 'Multi-dispense 384w qPCR setup',
    'description': '''This protocol uses multi-dispense to distribute MasterMix into wells Q1/Q2 and Q3/Q4 separately; also uses multi-dispense to transfer RNA into Q1/Q3, and Q2/Q4''',
    'author': 'Max Benjamin'
    }

def run(protocol: protocol_api.ProtocolContext):

    # Set tip box locations #
    p20x8_tips1 = protocol.load_labware('opentrons_96_tiprack_20ul',7)
    p20x8_tips2 = protocol.load_labware('opentrons_96_tiprack_20ul',8)
    p300x8_tips1 = protocol.load_labware('opentrons_96_tiprack_300ul',9)

    # Set source and destination plate labware locations #
    mastermix_source_plate = protocol.load_labware('nest_96_wellplate_2ml_deep',3)
    rna_source_plate1 = protocol.load_labware('nest_96_wellplate_200ul_on_basepiece',4)
    rna_source_plate2 = protocol.load_labware('nest_96_wellplate_200ul_on_basepiece',5)
    qPCR_destination_plate = protocol.load_labware('corning_384_wellplate_112ul_flat',6)

    # Set mounted pipette types #
    p20x8 = protocol.load_instrument('p20_multi_gen2', 'left', tip_racks = [p20x8_tips1, p20x8_tips2])
    p300x8 = protocol.load_instrument('p300_multi_gen2', 'right', tip_racks = [p300x8_tips1])

    # Declare liquid handling variables for mastermix dispensing #
    rxn_volume = 15 # ul
    dispense_volume = rxn_volume # change this value as needed for volume adjustment

    # Liquid handling commands for mastermix multidispense #
    source = mastermix_source_plate.wells_by_name()['A1']
    dest = [qPCR_destination_plate.rows()[row] for row in list(range(0, 16))][0]
    p300x8.distribute(dispense_volume, source, dest, trash = True, touch_tip = False, blow_out = True, blowout_location = 'source well', disposal_volume = 15)

    source = mastermix_source_plate.wells_by_name()['A2']
    dest = [qPCR_destination_plate.rows()[row] for row in list(range(0, 16))][1]
    p300x8.distribute(dispense_volume, source, dest, trash = True, touch_tip = False, blow_out = True, blowout_location = 'source well', disposal_volume = 15)

    # Liquid handling commands for RNA multidispense #
    transfer_volume = 5
    for column in list(range(0, 12)):
        source_well = rna_source_plate1.wells()[column * 8] # use multichannel to pull from columns starting at row A, RNA plate 1
        dest_well_q1 = qPCR_destination_plate.wells()[column * 32] # destination well indices for quadrant 1
        dest_well_q3 = qPCR_destination_plate.wells()[1 + column * 32] # destination well indices for quadrant 3
        p20x8.pick_up_tip()
        p20x8.aspirate(transfer_volume*2, source_well, rate = 1.0)
        p20x8.dispense(transfer_volume, dest_well_q1.top(-4.5), rate = 1.0)
        p20x8.dispense(transfer_volume, dest_well_q3.top(-4.5), rate = 1.0)
        p20x8.drop_tip()

    for column in list(range(0, 12)):
        source_well = rna_source_plate2.wells()[column * 8] # use multichannel to pull from columns starting at row A, RNA plate 2
        dest_well_q2 = qPCR_destination_plate.wells()[16 + column * 32] # destination well indices for quadrant 2
        dest_well_q4 = qPCR_destination_plate.wells()[17 + column * 32] # destination well indices for quadrant 4
        p20x8.pick_up_tip()
        p20x8.aspirate(transfer_volume*2, source_well, rate = 1.0)
        p20x8.dispense(transfer_volume, dest_well_q2.top(-4.5), rate = 1.0)
        p20x8.dispense(transfer_volume, dest_well_q4.top(-4.5), rate = 1.0)
        p20x8.drop_tip()