# This protocol is designed to PCR-amplify the Golden Gate reaction product.
# GG reactions in Col 2 will be diluted with primer in Col 3 and then
#   transferred to Col 4 for PCR reaction.
# Sanitize thermocycler lid before run.
# At the end of the protocol, the PCR plate is transferred to 4C module to await 
#   quantitation and cell-free reactions.
# NOTE: Cycles, times and module temps may be modified for protocol testing - be sure to change!

from opentrons import protocol_api

metadata = {
    'protocolName': 'PCR Amplification of Golden Gate Reaction Product',
    'author': 'rwilton@anl.gov',
    'description': 'Implementation of Romero protocol on the Flex'
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
    protocol.pause("Protocol paused to place PCR reagent tubes. Resume when ready.")

    thermocycler.close_lid()
    thermocycler.set_block_temperature(25)
    thermocycler.set_lid_temperature(103)
    
    # Step 2: Distribute primer mix with tip refilling:
    p50_single.distribute(
        volume=90,
        source=temp_plate["A2"],
        dest=[pcr_plate.columns()[2]],
        disposal_volume=0,  # reduce from default µL to 5 µL
    )
    
    # Step 3: Multi-channel transfer of GG product to primer with mix after
    p50_multi.pick_up_tip()
    # Transfer from column 2 to column 3
    p50_multi.transfer(10,
                  pcr_plate.columns()[1],  # Source: Column 2
                  pcr_plate.columns()[2],  # Destination: Column 3
                  new_tip='never',
                  mix_after=(5, 40))
    p50_multi.drop_tip()

    # Step 4: Distribute Phusion 2x master mix:
    p50_single.distribute(
        volume=10,
        source=temp_plate["A3"],
        dest=[pcr_plate.columns()[3]],
        disposal_volume=5,  # reduce from default µL to 0 µL
    )
    
    # Step 5: Multi-channel transfer with mix after
    p50_multi.pick_up_tip()
    p50_multi.transfer(10,
                  pcr_plate.columns()[2],
                  pcr_plate.columns()[3],
                  new_tip='never',
                  mix_after=(5, 10))   # Mix 5 times with 10µL in destination well
    p50_multi.drop_tip()

    # Step 6: Move plate to thermocycler and run cycles
    thermocycler.open_lid()
    protocol.move_labware(pcr_plate, thermocycler, use_gripper=True)

    # Close thermocycler lid 
    thermocycler.close_lid()  

    # Run thermocycler denaturation step
    profile = [
        {"temperature":95, "hold_time_seconds":30},
     ]
    thermocycler.execute_profile(steps=profile, repetitions=1, block_max_volume=20)
    
    # Run thermocycler profile - adjust hold times and number of cycles: repetitions=n
    profile = [
        {"temperature":95, "hold_time_seconds":30},
        {"temperature":65, "hold_time_seconds":30},
        {"temperature":72, "hold_time_seconds":30},
    ]
    thermocycler.execute_profile(steps=profile, repetitions=2, block_max_volume=20)
    
    # Hold at 4°C
    thermocycler.deactivate_lid()
    thermocycler.set_block_temperature(4)
    
    # protocol.pause("Protocol paused for manual intervention. Resume when ready.")

    # Activate second temp module to prepare for receiving PCR plate
    temp_module2.set_temperature(4)
    
    # Open lid for plate removal
    # Transfer plate to cooled temp_module2 - NOTE: must specify the Al_PCR_block as destination
    thermocycler.open_lid()
    protocol.move_labware(pcr_plate, Al_PCR_block, use_gripper=True)

    # Step 5: Deactivate modules
    thermocycler.deactivate()
    temp_module.deactivate()
