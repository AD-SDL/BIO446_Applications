from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Protein Design CFPE and Assay',
    'author': 'BATS team',
    'source': 'FlexGB/pd_cfpe_assay_01.py',
    'description': 'Protein Design CFPE and Assay'
}

# requirements
requirements = {"robotType": "Flex", "apiLevel": "2.20"}


def run(protocol: protocol_api.ProtocolContext):


    # labware settings
    temp_module_temp = 4

    # CFPE reagent volume
    cpfe_reagent_vol = 18
    dna_vol = 2
    time_required_for_transfer_and_seal = 5
    cfpe_reaction_time = 240
    cfpe_reaction_dilution_vol = 80
    reaction_buffer_vol = 40
    cfpe_reaction_product_per_assay = 10
    substrate_volume = 80


    # Trash location
    trash = protocol.load_trash_bin(location="A1")

    
    # Set up temperature module in D1 at 4°C
    # is it gen2 or original (temperature module)
    temp_module = protocol.load_module('temperature module gen2', 'D1')
    temp_module.set_temperature(celsius=temp_module_temp)

    # add adpater
    temp_adapter = temp_module.load_adapter(
        "opentrons_96_well_aluminum_block"
    )

    # load a PCR plate (PCR amplicons and CFPE reagent in this case)
    source_plate = temp_adapter.load_labware(
        "nest_96_wellplate_100ul_pcr_full_skirt"
    )



    # Set up heater/shaker module at 37°C
    heater_shaker = protocol.load_module('heaterShakerModuleV1', 'C1')
    heater_shaker.set_temperature(37)


    dest_plate = temp_module.load_labware('nest_96_wellplate_100ul_pcr_full_skirt')
    

    

    # 
    # Load labware and modules (??)
    source_plate = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'D2')



    # Load additional labware
    reservoir = protocol.load_labware('nest_12_reservoir_15ml', 'B1')
    assay_plate = protocol.load_labware('nest_96_wellplate_200ul_flat', 'C2')

    staging_area = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'B1')
    
    # Load Flex gripper
    gripper = protocol.load_module('gripperV2', '')
    
    # Load tip racks (2 for P20, 1 for P1000)
    tip_racks_20 = [
        protocol.load_labware('opentrons_flex_96_tiprack_200ul', slot)
        for slot in ['A2', 'A3']
    ]
    
    tip_rack_1000 = protocol.load_labware('opentrons_96_tiprack_1000ul', 'B2')
    
    # Load pipettes
    p20 = protocol.load_instrument('p20_single_gen2', 'left', tip_racks=tip_racks_20)
    p1000 = protocol.load_instrument('p1000_single_gen2', 'right', tip_racks=[tip_rack_1000])
    

    # pipettes
    p1000 = protocol.load_instrument(
        "flex_1channel_1000", mount="right", tip_racks=[tip_rack_1000]
    )


    # load labware into FLEX (can be omitted)
    # reservoir
    gripper.pick_up_plate(reservoir)
    gripper.move_plate('B3')
    protocol.delay(minutes=2)
    gripper.pick_up_plate(reservoir)
    gripper.move_plate('B1')
  




    # Define wells on the PCR plate (source); H1 has the CFPE reagent; A1 .. D1 are the DNA templates 
    source_wells = {
        'H': source_plate['H1'],
        'A': source_plate['A1'],
        'B': source_plate['B1'],
        'C': source_plate['C1'],
        'D': source_plate['D1']
    }
    

    # the destination plate has the assembled CFPE reactions
    # it has to be different from the source plate since it is destined for 4 hr incubation at 37 oC
    # the source plate should be kept cold

    dest_wells = [
        dest_plate['A1'],
        dest_plate['B1'],
        dest_plate['C1'],
        dest_plate['D1']
    ]
    
    # Distribute cpfe_reagent_vol µL of reagent H to all destination wells
    p20.pick_up_tip()
    p20.distribute(
        cpfe_reagent_vol,
        source_wells['H'],
        dest_wells,
        new_tip='never',
        disposal_volume=2,
        blow_out=True,
        blowout_location='source well'
    )
    p20.drop_tip()
    

    # Transfer dna_vol µL of DNA to corresponding wells
    # could define destination wells similar to the source wells
    transfers = [
        (source_wells['A'], dest_plate['A1']),
        (source_wells['B'], dest_plate['B1']),
        (source_wells['C'], dest_plate['C1']),
        (source_wells['D'], dest_plate['D1'])
    ]
    
    for source, dest in transfers:
        p20.pick_up_tip()
        p20.transfer(
            dna_vol,
            source,
            dest,
            #new_tip='never',
            mix_after=(3, cpfe_reagent_vol),
            blow_out=True,
            blowout_location='destination well'
        )
        p20.drop_tip()


    # Mix the destination wells after distribution
    # for well in dest_wells:
    #     p20.pick_up_tip()
    #     p20.mix(3, cpfe_reagent_vol, well)  # Mix 3 times with cpfe_reagent_vol µL
    #     p20.blow_out(well)
    #     p20.drop_tip()
    


    
    # move to staging area (??)
    gripper.pick_up_plate(dest_plate)
    gripper.move_plate(staging_area)

    # time_required_for_transfer_and_seal minute pause after transfers (['PF400 transfer', 'plate seal', 'PF400 transfer'])
    protocol.delay(minutes=time_required_for_transfer_and_seal)
    
    # the plate is sealed and ready for incubation
    # Move plate from staging to heater/shaker using gripper
    gripper.pick_up_plate(dest_plate)
    gripper.move_plate(heater_shaker.plate_nest)
    
    # cfpe_reaction_time minutes pause to perform CPFE reaction
    protocol.delay(minutes=cfpe_reaction_time)  # cfpe_reaction_time minutes
    
    # Move plate from heater/shaker to staging area in row B using gripper
    gripper.pick_up_plate(heater_shaker.plate_nest)
    gripper.move_plate(staging_area)
    
    # time_required_for_transfer_and_seal minute pause for transfer/peel (['PF400 transfer', 'plate peel', 'PF400 transfer'])
    protocol.delay(minutes=time_required_for_transfer_and_seal)
    
    # Move plate back to heater/shaker (??)
    gripper.pick_up_plate(staging_area)
    gripper.move_plate(heater_shaker.plate_nest)
    





    # Transfer cfpe_reaction_dilution_vol µL from reservoir to destination wells with mixing
    for dest_well in ['A1', 'B1', 'C1', 'D1']:
        p1000.pick_up_tip()
        p1000.transfer(
            cfpe_reaction_dilution_vol,
            reservoir['A1'],
            heater_shaker.plate_nest[dest_well],
            #new_tip='never',
            mix_after=(3, cfpe_reaction_dilution_vol),  # Mix 3 times with cfpe_reaction_dilution_vol µL
            blow_out=True,
            blowout_location='destination well'
        )
        p1000.drop_tip()
    
    # Transfer reaction_buffer_vol µL from reservoir to rows 1-4 of assay_plate
    dest_wells_assay_plate = [
        well for row in ['A', 'B', 'C', 'D']  # Rows 1-4
        for well in [f'{row}1']  # Column 1
    ]
    #dest_wells_assay_plate = ['A1', 'B1', 'C1', 'D1']

    for dest_well in dest_wells_assay_plate:
        p1000.pick_up_tip()
        p1000.transfer(
            reaction_buffer_vol,
            reservoir['A1'],
            assay_plate[dest_well],
            new_tip='never',
            blow_out=True,
            blowout_location='destination well'
        )
        p1000.drop_tip()
        
    # Transfer reaction_buffer_vol + cfpe_reaction_product_per_assay µL from reservoir to all wells in row 5 of assay_plate
    row5_wells = [f'{row}5' for row in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']]
    
    for dest_well in row5_wells:
        p1000.pick_up_tip()
        p1000.transfer(
            reaction_buffer_vol + cfpe_reaction_product_per_assay,
            reservoir['A1'],
            assay_plate[dest_well],
            new_tip='never',
            blow_out=True,
            blowout_location='destination well'
        )
        p1000.drop_tip()


    # the lock below is repetitive; should write a more elegant routine here (A1 .. D1)

    # Distribute cfpe_reaction_product_per_assay µL from dest_plate A1 to column 1 of assay_plate
    p20.pick_up_tip()
    p20.distribute(
        cfpe_reaction_product_per_assay,
        heater_shaker.plate_nest['A1'],
        [assay_plate[f'{row}1'] for row in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']],
        new_tip='never', # this should be changed in production at some point
        mix_after=(3, reaction_buffer_vol),
        disposal_volume=2,
        blow_out=True,
        blowout_location='source well'
    )
    p20.drop_tip()
    
    # Distribute 10µL from dest_plate B1 to column 2 of assay_plate
    p20.pick_up_tip()
    p20.distribute(
        cfpe_reaction_product_per_assay,
        heater_shaker.plate_nest['B1'],
        [assay_plate[f'{row}2'] for row in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']],
        new_tip='never', # this should be changed in production at some point
        mix_after=(3, reaction_buffer_vol),
        disposal_volume=2,
        blow_out=True,
        blowout_location='source well'
    )
    p20.drop_tip()
    
    # Distribute 10µL from dest_plate C1 to column 3 of assay_plate
    p20.pick_up_tip()
    p20.distribute(
        cfpe_reaction_product_per_assay,
        heater_shaker.plate_nest['C1'],
        [assay_plate[f'{row}3'] for row in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']],
        new_tip='never', # this should be changed in production at some point
        mix_after=(3, reaction_buffer_vol),
        disposal_volume=2,
        blow_out=True,
        blowout_location='source well'
    )
    p20.drop_tip()
    
    # Distribute 10µL from dest_plate D1 to column 4 of assay_plate
    p20.pick_up_tip()
    p20.distribute(
        cfpe_reaction_product_per_assay,
        heater_shaker.plate_nest['D1'],
        [assay_plate[f'{row}4'] for row in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']],
        new_tip='never', # this should be changed in production at some point
        mix_after=(3, reaction_buffer_vol),
        disposal_volume=2,
        blow_out=True,
        blowout_location='source well'
    )
    p20.drop_tip()
    
    # Transfer substrate_volume µL from reservoir A2 to rows 1-5 of assay_plate with mixing
    dest_wells = [
        f'{row}{col}' 
        for col in range(1, 6)  # Columns 1-5
        for row in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']  # All rows
    ]
    
    for well in dest_wells:
        p1000.pick_up_tip()
        p1000.transfer(
            substrate_volume,
            reservoir['A2'],
            assay_plate[well],
            new_tip='always', 
            mix_after=(3, substrate_volume + reaction_buffer_vol),  # Mix 3 times with substrate_volume µL
            blow_out=True,
            blowout_location='destination well'
        )
        p1000.drop_tip()

    # move assay plate to the staging area
    gripper.pick_up_plate(assay_plate)
    gripper.move_plate(staging_area)