# This program is designed to set up Golden Gate Reactions
# Fragment mixtures in Col 1, GG reactions to be set up in Col 2.
# Sanitize thermocycler lid before run.
# At the end of the protocol, the PCR plate is transferred to 4C module to await 
#   PCR amplification of the assembled gene fragments.
# NOTE: Cycles, times and module temps may be modified for protocol testing - be sure to change!

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
    temp_module = protocol.load_module(module_name="temperature module gen2", location="C3")
    temp_module2 = protocol.load_module(module_name="temperature module gen2", location="D3")
    
    # Load labware
    tiprack = protocol.load_labware('opentrons_flex_96_tiprack_50ul', 'B2')
    pcr_plate = protocol.load_labware('opentrons_96_wellplate_200ul_pcr_full_skirt', 'D2')
    
    # Load labware onto modules
    # Note that labware is expecting a collared tube here - calibrate properly to avoid tip crash
    temp_plate = temp_module.load_labware('opentrons_24_aluminumblock_generic_2ml_screwcap')
    Al_PCR_block = temp_module2.load_adapter("opentrons_96_well_aluminum_block")

    # Load pipettes
    p50_single = protocol.load_instrument('flex_1channel_50', 'left', tip_racks=[tiprack])
    p50_multi = protocol.load_instrument('flex_8channel_50', 'right', tip_racks=[tiprack])

    # Step 1: Set module temperatures
    temp_module.set_temperature(4)

    # Once temp_module has reached 4C, the 2 ml screw top reagent tube can be placed in block, well A1.
    protocol.pause("Protocol paused to place GG reagent tube. Resume when ready.")

    thermocycler.close_lid()
    thermocycler.set_block_temperature(37)
    thermocycler.set_lid_temperature(70)
    
    # Step 2: Transfer GG reagent from temp module to PCR plate (use same tip)
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
                  mix_before=(5, 20),  # Mix 3 times with 20µL in source well
                  mix_after=(5, 10))   # Mix 5 times with 10µL in destination well
    p50_multi.drop_tip()

    # Step 4: Move plate to thermocycler and run cycles
    thermocycler.open_lid()
    protocol.move_labware(pcr_plate, thermocycler, use_gripper=True)

    # Close thermocycler lid 
    thermocycler.close_lid()  
    
    # Run thermocycler profile - adjust hold times and number of cycles: repetitions=n
    profile = [
        {"temperature":37, "hold_time_seconds":30},
        {"temperature":16, "hold_time_seconds":30},
    ]
    thermocycler.execute_profile(steps=profile, repetitions=2, block_max_volume=20)

    # Denature enzymes to stop reaction
    thermocycler.execute_profile(steps=[
        {'temperature': 60, 'hold_time_seconds': 300}
    ], repetitions=1)
    
    # Hold at 4°C
    thermocycler.deactivate_lid()
    thermocycler.set_block_temperature(4)
    
    # protocol.pause("Protocol paused for manual intervention. Resume when ready.")

    # Activate second temp module to prepare for receiving PCR plate
    temp_module2.set_temperature(10)
    
    # Open lid for plate removal
    # Transfer plate to cooled temp_module2 - NOTE: must specify the Al_PCR_block as destination
    thermocycler.open_lid()
    protocol.move_labware(pcr_plate, Al_PCR_block, use_gripper=True)

    # Step 5: Deactivate modules
    #thermocycler.deactivate()
    temp_module.deactivate()