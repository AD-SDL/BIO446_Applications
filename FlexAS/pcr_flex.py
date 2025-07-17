from opentrons import protocol_api
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'PCR Using Golden Gate Products',
    'author': 'Abe Stroka',
    'description': 'PCR setup with golden gate templates',
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

def run(protocol: protocol_api.ProtocolContext):
    # Labware
    gg_plate = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'B2')  # GG reaction plate
    diluted_plate = protocol.load_labware('corning_96_wellplate_360ul_flat', 'D2')
    temp_mod = protocol.load_module(module_name="temperature module gen2", location="C1")
    temp_adapter = temp_mod.load_adapter("opentrons_96_well_aluminum_block")
    pcr_plate = temp_adapter.load_labware('nest_96_wellplate_100ul_pcr_full_skirt')               # for 1:2 diluted GG
    # pcr_plate = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'B3') # final PCR plate
    mastermix_tube = protocol.load_labware('nest_12_reservoir_15ml', 'B3') # master mix tube
    water_reservoir = protocol.load_labware('nest_12_reservoir_15ml', 'A1')
    #TODO: need second temp block for gg reaction?
    tiprack_50 = protocol.load_labware(
        load_name="opentrons_flex_96_tiprack_50ul", location="A2", 
    )

    p50 = protocol.load_instrument('flex_8channel_50', mount='right', tip_racks=[tiprack_50])
    p50.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_50]) # TODO: change start, will be using same tip rack from gg

    chute = protocol.load_waste_chute()


    # Assume 3 GG reactions:
    gg_reactions = [
        {"name": "p53", "src": "A1", "diluted": "A1", "final": "A1"},
        {"name": "pET-21", "src": "A2", "diluted": "A2", "final": "A2"},
        {"name": "pJL-1", "src": "A3", "diluted": "A3", "final": "A3"},
    ]

    water = water_reservoir.wells_by_name()['A2']
    master_mix_total_vol = 240  # µL (10x)

    # dilute GG reactions 1:2 by adding 20µL water to 20µL GG product
    for rxn in gg_reactions:
        p50.transfer(20, water, diluted_plate.wells_by_name()[rxn["diluted"]])
        p50.transfer(20, gg_plate.wells_by_name()[rxn["src"]], diluted_plate.wells_by_name()[rxn["diluted"]], mix_after=(2, 10))

    # Step 2: Master mix prep (manually prepare off-deck, then load 240µL into tube A1)
    # Details:
    # Water: 30 µL
    # 1M Trehalose: 50 µL
    # 5M Betaine: 50 µL
    # dNTPs: 50 µL
    # MgSO4: 20 µL
    # KOD Buffer: 25 µL
    # BSA: 2.5 µL
    # PolyA RNA: 2.5 µL
    # V68 Primers: 5 µL
    # KOD Polymerase: 5 µL

    # Step 3: Add 24 µL master mix to each well in PCR plate
    for rxn in gg_reactions:
        p50.transfer(24, mastermix_tube.wells_by_name()['A2'], pcr_plate.wells_by_name()[rxn["final"]])

    # Step 4: Add 1 µL diluted GG template to each PCR reaction
    for rxn in gg_reactions:
        p50.transfer(1, diluted_plate.wells_by_name()[rxn["diluted"]], pcr_plate.wells_by_name()[rxn["final"]], mix_after=(2, 5))
