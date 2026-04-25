'''
Project Pretoria
RNA Aliquoting for Reportable Range - 96-well Plate
Updated 2023-08-25
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


The previous Python protocol prepares a set of 12 RNA dilutions, with concentrations as outlined in the table above.
​This dilution series is sufficient volume of RNA to perform a reportable range on four 96-well plates
i.e., one reportable range series per PANDAAA.   

This protocol aliquots RNA dilutions into a 96-well plate, matching the plate layout used for reportable range experiments.
RNA from these aliquots can then be "stamped" into each qPCR plate [i.e., 10µL from column 1 of the aliquot plate can be added
to column 1 of the qPCR plate, and so on]. This minimizes user time/effort, especially if a multichannel multipipette is not available.

Plate Map

     1    2    3    4    5    6    7    8    9    10   11   12 
   ┌───────────────────┬───────────────────┬───────────────────┐
 A │         1         │         2         │         3         │
   ├───────────────────┼───────────────────┼───────────────────┤
 B │         4         │         5         │         6         │
   ├───────────────────┴───────────────────┼───────────────────┤
 C │                   7                   │                   │
   ├───────────────────────────────────────┤      Negative     │
 D │                   8                   │                   │
   ├───────────────────────────────────────┴───────────────────┤
 E │                             9                             │
   ├───────────────────────────────────────────────────────────┤
 F │                            10                             │
   ├───────────────────────────────────────────────────────────┤
 G │                            11                             │
   ├───────────────────────────────────────────────────────────┤
 H │                            12                             │
   └───────────────────────────────────────────────────────────┘

Tube Setup

Empty 96-well plate
RNA dilutions [12]: columns 1-3 of 24-ct 1.5mL rack

'''

from opentrons import protocol_api

metadata = {
    'apiLevel': '2.14',
    'protocolName': 'Pretoria | RNA Aliquoting for Reportable Range',
    'author': 'OP13 LL',
    'description': '''Distributes RNA dilutions into a 96-well plate for stamping. 
                    '''
}

def run(protocol: protocol_api.ProtocolContext):

  protocol.home()

  ###
  ### User-defined variables
  ###

  aliquot_vol = 45            # volume of RNA to be aliquoted into each plate well

  negatives_tube = True       # if false, negatives will not be plated/aliquoted
  negatives_location = 'A5'   # location within 24-ct 1.5mL tube rack



  ###
  ### Initialization
  ###

  p300tips = protocol.load_labware('opentrons_96_filtertiprack_200ul', 3)
  tubes = protocol.load_labware('opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap', 2)
  plate = protocol.load_labware('armadillo_96_wellplate_200ul_pcr_full_skirt', 1)

  # pipette initialization
  p300 = protocol.load_instrument('p300_single_gen2', 'right', tip_racks=[p300tips])


  ###
  ### Visualization of deck layout - API 2.14 and above only!
  ### To use protocol simulator, downgrade this protocol to 2.13 and comment out this section
  ###
  # ************************************
  
  RNA_viz = protocol.define_liquid(
      'RNA Dilutions',
      '12 tubes arranged in columns [A1 is dilution 1, B1 is dilution 2, etc].',
      '#f44'
  )

  neg_viz = protocol.define_liquid(
      'Negative',
      '0.05 ng/µL hgDNA in 0.05 mg/mL tRNA-dH2O.',
      '#44f'
    )

  for i in range(12):
      tubes.wells()[i].load_liquid(
          RNA_viz,
          540
      )

  if negatives_tube == True:
      tubes[negatives_location].load_liquid(
          neg_viz,
          540
      )
  # ************************************



  ###
  ### 1. Aliquot dilutions to plate - 4 replicates (dilutions 1-6)
  ###

  for dil in range(6):  # dilutions with indices 0-5
     
     # create list containing wells to fill
     wells_to_fill = []
    
     if dil > 2:
        row = 1 # row B
     else:
        row = 0 # row A
        
     col_group = dil % 3  # columns 1-4, 5-8, or 9-12

     for col in range(4): # 4 replicates per row - 4 columns
        wells_to_fill.append(
            32*col_group +
            8*col +
            row
        )

     # fill wells
     p300.distribute(
         aliquot_vol,
         [tubes.wells()[dil]],
         [plate.wells()[well] for well in wells_to_fill],
         blow_out = True,
         blowout_location = 'source well'
      )



  ###
  ### 2. Aliquot dilutions to plate - 8 replicates (dilutions 7-8)
  ###

  for dil in range(6,8):  # dilutions with indices 6-7
     
     # create list containing wells to fill
     wells_to_fill = []

     row = dil - 4   # convert dilution index (ex. "6") to row index (ex. "2" - row C)

     for col in range(8): # 8 replicates per row
        wells_to_fill.append(
            8*col +
            row
        )

     # fill wells
     p300.distribute(
         aliquot_vol,
         [tubes.wells()[dil]],
         [plate.wells()[well] for well in wells_to_fill],
         blow_out = True,
         blowout_location = 'source well'
      )        
     


  ###
  ### 3. Aliquot dilutions to plate - 12 replicates (dilutions 9-12)
  ###

  for dil in range(8, 12):  # dilutions with indices 8-11
     
     # create list containing wells to fill
     wells_to_fill = []

     row = dil - 4   # convert dilution index (ex. "8") to row index (ex. "4" - row E)

     for col in range(12): # 12 replicates per row
        wells_to_fill.append(
            8*col +
            row
        )

     # fill wells
     p300.distribute(
         aliquot_vol,
         [tubes.wells()[dil]],
         [plate.wells()[well] for well in wells_to_fill],
         blow_out = True,
         blowout_location = 'source well'
      )


  ###
  ### 4. Aliquot negative control, if included
  ###

  if negatives_tube == True:
      
    # create list containing wells to fill
    wells_to_fill = []


    for row in range(2,4):  # 2 rows: C ("2") and D ("3")
      for col in range(8,12): # 4 replicates per row, in columns with indices 8-11
        wells_to_fill.append(
            8*col +
            row
        )

    # fill wells
    p300.distribute(
        aliquot_vol,
        tubes[negatives_location],
        [plate.wells()[well] for well in wells_to_fill],
        blow_out = True,
        blowout_location = 'source well'
      )
    
  protocol.home()
      
