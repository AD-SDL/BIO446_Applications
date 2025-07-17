from opentrons import protocol_api
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Golden Gate Assembly',
    'author': 'Abe Stroka',
    'description': 'Automated Golden Gate Assembly using OT-Flex',
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

def run(protocol: protocol_api.ProtocolContext):
    # Labware
    #source_plate = protocol.load_labware('nest_96_wellplate_200ul_flat', 'B1') #
    source_plate = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'B1') # TODO: change
    pcr_plate = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'B2')
    mastermix_tube = protocol.load_labware('nest_12_reservoir_15ml', 'B3') #TODO change
    water_reservoir = protocol.load_labware('nest_12_reservoir_15ml', 'A1')
    temp_mod = protocol.load_module(module_name="temperature module gen2", location="C1")
    temp_adapter = temp_mod.load_adapter("opentrons_96_well_aluminum_block")
    dna = temp_adapter.load_labware('nest_96_wellplate_100ul_pcr_full_skirt') # transfer source_plate 
    

    tiprack_50 = protocol.load_labware(
        load_name="opentrons_flex_96_tiprack_50ul", location="A2",
    )

    # 8-channel P1000
    tiprack_200 = protocol.load_labware(
        load_name="opentrons_flex_96_tiprack_200ul", location="A3"
    )



    # Pipettes
    p50 = protocol.load_instrument('flex_8channel_50', mount='right', tip_racks=[tiprack_50])
    p1000 = protocol.load_instrument('flex_8channel_1000', mount='left', tip_racks=[tiprack_200])

    p50.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_50])
    p1000.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_200])


    # load trash bin
    # _ = protocol.load_trash_bin("D1")
    chute = protocol.load_waste_chute()

    #TODO: set temperature
    temp_mod.set_temperature(4)  # Set temperature module to 4°C
    protocol.comment("Temperature module set to 4°C")
    # DNA Dilution Table
    plasmids = [
        {"name": "p53_P1F0", "well": "A1", "dil_vol": 67.2},
        {"name": "p53_P1F3", "well": "A2", "dil_vol": 38.2},
        {"name": "pET-21_P1F0", "well": "A3", "dil_vol": 35.8},
        {"name": "pET-21_P1F3", "well": "A4", "dil_vol": 30.7},
        {"name": "pJL-1_P1F0", "well": "A5", "dil_vol": 28.5},
        {"name": "pJL-1_P1F3", "well": "A6", "dil_vol": 52.9},
    ]

    water = water_reservoir.wells_by_name()['A1']

    # not needed
    #dilute plasmids to 25 fmol/µL in 96-well plate
    for plasmid in plasmids:
        p1000.transfer(plasmid["dil_vol"] - 15, water, source_plate.wells_by_name()[plasmid["well"]])
        # Add 15µL DNA manually (or adjust for pipetting from high concentration tube)
    for plasmid in plasmids:
        p50.transfer(15, dna.wells_by_name()['A1'], source_plate.wells_by_name()[plasmid["well"]]) #TODO: change dna location?


    # adding 2uL of each (4x2uL) of plasmids + 10 uL mastermix to each well + 2uL water (the mastermix and water will be premixed)
    # GoldenGate master + water can be mixed manually off-deck
    # final: 4x2uL plasmid + 12 uL diluted mastermix

    #mix F0 and F3 pairs into PCR plate
    # will rearray into columns
    assemblies = [
        {"f0": "A1", "f3": "A2", "dest": "A1"},
        {"f0": "A3", "f3": "A4", "dest": "A2"},
        {"f0": "A5", "f3": "A6", "dest": "A3"},
    ]

    for pair in assemblies:
        p50.transfer(2, source_plate.wells_by_name()[pair["f0"]], pcr_plate.wells_by_name()[pair["dest"]])
        p50.transfer(2, source_plate.wells_by_name()[pair["f3"]], pcr_plate.wells_by_name()[pair["dest"]], mix_after=(2, 5))

    # TODO: prepare Golden Gate master mix? or by hand? (39.6 µL total, 3.3x)
    #manually: 26.4 µL H2O, 6.6 µL 10x ligase buffer, 6.6 µL Golden Gate mix
    #mastermix_tube['A1']
    
    #12 µL master mix to each reaction well
    for pair in assemblies:
        dest = pcr_plate.wells_by_name()[pair["dest"]]
        p50.transfer(12, mastermix_tube.wells_by_name()['A1'], dest, mix_after=(2, 10))

    # the source plate should be on the temp block (set at 4oC)
    # the destination plate will be sealed and moved to the thermocycler
    protocol.comment("Golden Gate Assembly setup complete. Transfer the PCR plate to the thermocycler for cycling.")
