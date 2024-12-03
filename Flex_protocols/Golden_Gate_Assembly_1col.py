from opentrons import protocol_api


metadata = {
    'protocolName': 'Golden Gate Assembly',
    'author': 'rwilton@anl.gov',
    'description': 'Add reagents to gene frag mixtures and perform thermal cycling'
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.20'
}

def run(protocol: protocol_api.ProtocolContext):
    # Load trash bin for Flex
    trash = protocol.load_trash_bin('A3')

    # Load modules
    thermocycler = protocol.load_module('thermocyclerModuleV2')
    temp_module = protocol.load_module('temperature module gen2', 'C3')
    
    # Load labware
    reservoir = protocol.load_labware('nest_12_reservoir_15ml', 'C2')
    tiprack = protocol.load_labware('opentrons_flex_96_tiprack_50ul', 'B2')
    pcr_plate = protocol.load_labware('opentrons_96_wellplate_200ul_pcr_full_skirt', 'D2')
    
    # Load labware onto modules
    temp_plate = temp_module.load_labware('opentrons_24_aluminumblock_generic_2ml_screwcap')
    tc_plate = thermocycler.load_labware('opentrons_96_wellplate_200ul_pcr_full_skirt')

    # Load pipettes
    p50_single = protocol.load_instrument('flex_1channel_50', 'left', tip_racks=[tiprack])
    p50_multi = protocol.load_instrument('flex_8channel_50', 'right', tip_racks=[tiprack])

    # Step 1: Set module temperatures
    temp_module.set_temperature(4)
    thermocycler.open_lid()
    thermocycler.set_block_temperature(37)
    thermocycler.set_lid_temperature(70)
    
    # Step 2: Transfer reagent from temp module
    p50_single.pick_up_tip()
    for well in pcr_plate.columns()[1][:8]:  # All 8 wells in column 2
        p50_single.transfer(10,
                        temp_plate['A1'],
                        well,
                        new_tip='never')
    p50_single.drop_tip()

    # Step 3: Multi-channel transfer with mix before and after
    p50_multi.pick_up_tip()
    p50_multi.transfer(10,
                  pcr_plate.columns()[0],
                  pcr_plate.columns()[1],
                  new_tip='never',
                  mix_before=(3, 20),  # Mix 3 times with 20µL in source well
                  mix_after=(5, 10))   # Mix 5 times with 10µL in destination well
    p50_multi.drop_tip()

    # Step 4: Move plate to thermocycler and run cycles
    protocol.move_labware(pcr_plate, thermocycler, use_gripper=True)
    
    # Run thermocycler profile - adjust number of cycles in range()
    for _ in range(3):
        thermocycler.execute_profile(steps=[
            {'temperature': 37, 'hold_time_seconds': 180},
            {'temperature': 16, 'hold_time_seconds': 180}
        ], repetitions=1)
    
    # Final incubation
    thermocycler.execute_profile(steps=[
        {'temperature': 60, 'hold_time_seconds': 300}
    ], repetitions=1)
    
    # Hold at 4°C
    thermocycler.set_block_temperature(4)
    
    protocol.pause("Protocol paused for manual intervention. Resume when ready.")
    
    # Open lid for plate removal
    thermocycler.open_lid()
    
    # Step 5: Deactivate modules
    thermocycler.deactivate()
    temp_module.deactivate()