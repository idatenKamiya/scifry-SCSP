'''
Project Pretoria
RNA Dilutions for Reportable Range
Updated 2023-07-31
Author: OP13 LL

+----------+----------------------+---------------+------------+
|               Stock Concentrations              | # of Wells |
+----------+----------------------+---------------+------------+
| Dilution |   Stock Copy / µL    | Copy Per Well |            |
+----------+----------------------+---------------+------------+
|        1 |             1.00E+05 |      1.00E+06 |          4 |
|        2 |             4.00E+04 |      4.00E+05 |          4 |
|        3 |             1.60E+04 |      1.60E+05 |          4 |
|        4 |             6.40E+03 |      6.40E+04 |          4 |
|        5 |                2,560 |      2.60E+04 |          4 |
|        6 |                1,024 |      1.00E+04 |          4 |
|        7 |                  410 |         4,096 |          8 |
|        8 |                  164 |         1,638 |          8 |
|        9 |                   66 |           655 |         12 |
|       10 |                   26 |           262 |         12 |
|       11 |                   10 |           105 |         12 |
|       12 |                    4 |            42 |         12 |
| Negative |                      |               |          8 |
+----------+----------------------+---------------+------------+

​For the performance evaluations in Project Pretoria, eleven dilutions of 2.5-fold are prepared to generate a reportable range
from 1.0E6 to 42 copies / reaction [adding 10 µL / well]. To mitigate the time burden associated with generating these dilutions,
should we be required to repeat any of the performance evaluations at a later date, then the intention is to generate multiple
single-use aliquots at ~1.0E6 copies / µL for long-term storage. These single-use aliquots can then be loaded onto the Opentrons and diluted.  

​There are ten different synthetic RNA constructs for HIV drug resistance genotyping, all of which are named starting with “POL”.
In the Pretoria assay, there are four separate PANDAA triplexes. Each PANDAA triplex detects two drug resistance mutations
and the VQ. One triplex is added per well of a 96-well plate.  

​The dilution series prepared on the Opentrons would be sufficient volume of RNA to perform a reportable range on four 96-well plates
i.e., one reportable range series per PANDAAA.   

​Opentrons Protocol 

​Add Reagents and Consumables to Opentrons Deck 
1. ​Eleven empty 1.5mL lo-bind Eppendorf tubes arrayed in rack on the Opentrons. 
2. ​One 1.5mL lo-bind Eppendorf tube containing 900 µL RNA master stock added to Opentrons rack [tube #1]. 
3. ​One 25mL Eppendorf tube with ~10mL tRNA.  

​Program 
1. ​Opentrons dispenses 540 µL tRNA from 25mL tube to eleven empty 1.5mL tubes. 
2. ​From tube #1, the RNA master stock, transfer 360 µL to the first 1.5mL tube that contains 540 µL tRNA [tube #2]. 
3. ​After dispensing 360 µL RNA into tube #2, pipette up and down to mix thoroughly.  
4. ​Discard tip. 
5. ​Perform same transfer workflow of 360 µL RNA, this time from tube #2 into tube #3. 
6. ​Repeat until 2.5-fold dilutions have been performed eleven times. ​ 

Tube Setup

25mL tube: B1 of 6-ct 50mL rack
Single-use RNA aliquot: A1 of 24-ct 1.5mL rack
Empty 1.5mL tubes: colums 1-3 [except A1] of 24-ct 1.5mL rack

'''

from opentrons import protocol_api

metadata = {
    'apiLevel': '2.14',
    'protocolName': 'Pretoria | RNA Dilutions for Reportable Range',
    'author': 'OP13 LL',
    'description': '''Performs eleven 2.5-fold dilutions. 
                    DURATION: 15 min.'''
}

def run(protocol: protocol_api.ProtocolContext):

    protocol.home()

    ###
    ### User-defined variables
    ###

    diluent_vol = 540
    diluent_location = 'B1'
    
    RNA_vol = 360
    num_tubes = 12 # number of tubes to contain RNA; arranged in columns (A1, B1, C1, D1, A2...)
    
    
    ###
    ### Initialization
    ###

    p1000tips = protocol.load_labware('opentrons_96_filtertiprack_1000ul', 6)
    tubes = protocol.load_labware('opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap', 2)
    # custom 25mL tube definition - Eppendorf screw-top
    diluent = protocol.load_labware('opentrons_6_tuberack_25ml', 5)

    # pipette initialization
    p1000 = protocol.load_instrument('p1000_single_gen2', 'left', tip_racks=[p1000tips])


    ###
    ### Visualization of deck layout - API 2.14 and above only!
    ### To use protocol simulator, downgrade this protocol to 2.13 and comment out this section
    ###
    # ************************************
    diluent_viz = protocol.define_liquid(
        'Diluent',
        '0.05 mg/mL tRNA in dH2O',
        '#44f'
    )

    RNA_viz = protocol.define_liquid(
        'RNA',
        'Single-use RNA aliquot in 1.5mL tube',
        '#f44'
    )

    empty_viz = protocol.define_liquid(
        'Empty Tube',
        '1.5mL tubes. Once filled, tubes are arranged in columns [B1 is dilution 1, C1 is dilution 2, D1 is dilution 3, A2 is dilution 4, etc.].',
        '#777'
    )

    diluent[diluent_location].load_liquid(
        diluent_viz,
        diluent_vol*num_tubes
    )

    tubes['A1'].load_liquid(
        RNA_viz,
        RNA_vol + diluent_vol
    )

    for i in range(1, num_tubes):
        tubes.wells()[i].load_liquid(
            empty_viz,
            0
        )
    # ************************************


    ###
    ### 1. Transfer diluent
    ###

    p1000.pick_up_tip()

    for i in range(1, num_tubes):

        p1000.transfer(
            diluent_vol,
            diluent[diluent_location],
            [tubes.wells()[i]],
            new_tip = 'never'
        )


    p1000.drop_tip()


    ###
    ### 2. Transfer RNA
    ###

    for i in range(1, num_tubes):

        p1000.transfer(
            RNA_vol,
            [tubes.wells()[i - 1]],
            [tubes.wells()[i]],
            mix_after = (
                5,
                (diluent_vol + RNA_vol)*0.8
            )
        )


    protocol.home()