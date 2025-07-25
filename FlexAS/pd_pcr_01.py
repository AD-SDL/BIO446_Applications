from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design PCR',
    'author': 'LDRD team ',
    'description': 'PCR for Protein Design',
    'source': 'FlexGB/pd_pcr_01.py'
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}


# Protocol Configuration
config = {
    # Combinatorial mixing
    'transfer_volume': 1,  # µL from each gg well
    # 'number_of_gg_samples': 6,
    'combinations': [[2,18],[3,19],[4,20],[5,21]],

    # Master mix and reagent settings
    'pcr_master_mix_well_volume': 100,
    'water_volume': 20,
    'pcr_master_mix_volume': 24,
    'water_well': 1,
    'master_mix_start_well': 48,


    # Temperature settings
    'temperature': 4,  # °C

    # Labware
    'source_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',
    'pcr_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',
    'gg_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',
    'reagent_plate_type': 'nest_12_reservoir_15ml',
    'tip_rack_type_50_01': 'opentrons_flex_96_tiprack_50ul',
    'pipette_type_50': 'flex_8channel_50',
    'tip_rack_type_200_01': 'opentrons_flex_96_tiprack_200ul',
    'pipette_type_1000': 'flex_8channel_1000',

    # Deck positions
    'temp_module_position': 'C1',
    'source_plate_initial_position': 'C1',
    'gg_plate_position': 'B2',
    'pcr_plate_position': 'B3',
    'tip_rack_position_50_01': 'A1',
    'tip_rack_position_200_01': 'A2',
    'reagent_plate_position': 'C2'
}


def calculate_total_combinations(combinations):
    """Calculate total number of combinations without generating them"""
    total = 1
    for sublist in combinations:
        total *= len(sublist)
    return total

def generate_all_combinations(combinations):
    """Generate all possible combinations from the jagged array"""
    return list(itertools.product(*combinations))

def transfer_water_to_gg(protocol, reagent_plate, gg_plate, pipette, config):
    water_volume = config['water_volume']
    # gg_wells = config['number_of_gg_samples']
    water_well = reagent_plate.wells()[config['water_well'] - 1]
    # protocol.comment(f"Total wells to add water to: {gg_wells}")
    combinations = config['combinations']

    gg_wells = calculate_total_combinations(combinations)

    for well in range(1, gg_wells + 1):
        dest_well = gg_plate.wells()[well - 1]
        protocol.comment(f"\nTransferring to destination well {dest_well}:")
        pipette.transfer(
            water_volume,
            water_well,
            dest_well,
            new_tip='always',  # Use fresh tip for each transfer
            mix_after = (3, 10)
        )

def master_mix_to_pcr_plate(protocol, source_plate, pcr_plate, pipette, config):
    master_mix_volume = config['pcr_master_mix_volume']
    # gg_wells = config['number_of_gg_samples']
    # protocol.comment(f"Total wells to add master mix to: {gg_wells}")
    pcr_master_mix_well_volume = config["pcr_master_mix_well_volume"]
    master_mix_well_volume = config["pcr_master_mix_volume"]
    master_mix_start_well = config["master_mix_start_well"]
    combinations = config['combinations']

    gg_wells = calculate_total_combinations(combinations)

    dispenses_per_well = pcr_master_mix_well_volume // master_mix_volume
    protocol.comment(f"Each master mix well ({master_mix_well_volume}µL) can serve {dispenses_per_well} destination wells")

    master_mix_wells_needed = (gg_wells + dispenses_per_well - 1) // dispenses_per_well

    current_master_mix_well = master_mix_start_well
    remaining_dispenses = dispenses_per_well
    protocol.comment(f"\nAdding {master_mix_volume}µL master mix to each destination well:")

    for dest_well_number in range(1, gg_wells + 1):
        # Check if we need to switch to next master mix well
        if remaining_dispenses == 0:
            current_master_mix_well += 1
            remaining_dispenses = dispenses_per_well
            protocol.comment(f"  Switching to master mix well {current_master_mix_well + 1} (0-indexed: {current_master_mix_well})")

        # Get the destination well
        dest_well = pcr_plate.wells()[dest_well_number - 1]  # Convert to 0-based index

        # Get the current master mix well
        master_mix_well = source_plate.wells()[current_master_mix_well]

        protocol.comment(f"  Dest well {dest_well_number}: Adding {master_mix_volume}µL from master mix well {current_master_mix_well + 1} (0-indexed: {current_master_mix_well})")

        # Transfer master mix
        pipette.transfer(
            master_mix_volume,
            master_mix_well,
            dest_well,
            new_tip='always',  # Use fresh tip for each master mix transfer
            mix_before=(3, 10),
            mix_after=(3, 10)
        )

        # Update remaining dispenses
        remaining_dispenses -= 1

    protocol.comment(f"\nMaster mix addition complete. Used wells {master_mix_start_well + 1} to {current_master_mix_well + 1} (0-indexed: {master_mix_start_well} to {current_master_mix_well})")

    return current_master_mix_well  # Return the last used well

def gg_to_pcr_plate(protocol, gg_plate, pcr_plate, pipette, config):

    gg_wells = config['number_of_gg_samples']
    transfer_volume = config['transfer_volume']
    
    for well in range(1, gg_wells + 1):
        dest_well = pcr_plate.wells()[well - 1]  
        source_well = gg_plate.wells()[well - 1]  

        pipette.transfer(
            transfer_volume,
            source_well,
            dest_well,
            new_tip='always',  # Use fresh tip for each transfer
            mix_before = (3, 10),
            mix_after = (3, 10)
        )     








def run(protocol: protocol_api.ProtocolContext):
    # Load temperature module and adapter
    temp_mod = protocol.load_module(module_name="temperature module gen2", location=config['temp_module_position'])
    temp_adapter = temp_mod.load_adapter("opentrons_96_well_aluminum_block")

    # Set temperature
    temp_mod.set_temperature(config['temperature']) #TODO: make seperate, or just set earlier, only 1 hour with plate

    # Load source plate initially on A4
    # source_plate = protocol.load_labware(config['source_plate_type'], config['source_plate_initial_position'])
    source_plate = temp_adapter.load_labware(config['source_plate_type'])


    chute = protocol.load_waste_chute()

    source_plate.set_offset(x=0.40, y=0.50, z=2.40)


    # Load destination plate
    pcr_plate = protocol.load_labware(config['pcr_plate_type'], config['pcr_plate_position'])
    pcr_plate.set_offset(x=0.4, y=0.4, z=0.0)

    gg_plate = protocol.load_labware(config['gg_plate_type'], config['gg_plate_position'])
    gg_plate.set_offset(x=0.4, y=0.4, z=0.0)

    reagent_plate = protocol.load_labware(config['reagent_plate_type'], config['reagent_plate_position'])


    tiprack_50 = protocol.load_labware(
        load_name=config['tip_rack_type_50_01'], location=config['tip_rack_position_50_01']
    )

    # 8-channel P1000
    tiprack_200 = protocol.load_labware(
        load_name=config['tip_rack_type_200_01'], location=config['tip_rack_position_200_01']
    )

    # Pipettes
    p50 = protocol.load_instrument('flex_8channel_50', mount='right', tip_racks=[tiprack_50])
    p1000 = protocol.load_instrument('flex_8channel_1000', mount='left', tip_racks=[tiprack_200])

    p50.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_50])
    p1000.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_200])



    # Perform combinatorial transfers #TODO: SWAP?  so adding small vols into large quant of master mix
    transfer_water_to_gg(
        protocol=protocol,
        reagent_plate=reagent_plate,
        gg_plate=gg_plate,
        pipette=p50,
        config=config
    )

    # Add master mix to each destination well
    last_master_mix_well = master_mix_to_pcr_plate(
        protocol=protocol,
        source_plate=source_plate,
        pcr_plate=pcr_plate,
        pipette=p50,
        config=config
    )

    gg_to_pcr_plate(
        protocol=protocol,
        gg_plate=gg_plate,
        pcr_plate=pcr_plate,
        pipette=p50,
        config=config
    )

    # mixing the content

    # moving the PCR plate to staging (seal and to thermocycler)

    # moving the reagents to staiging (seal and back to Flex?)

# Preview what will be transferred using the combinations defined above:
# Calculate total combinations
# total_combos = calculate_total_combinations(config['combinations'])
# protocol.comment(f"Calculation: {len(config['combinations'][0])} × {len(config['combinations'][1])} × {len(config['combinations'][2])} × {len(config['combinations'][3])} = {total_combos}")

# all_combos = generate_all_combinations(config['combinations'])

# protocol.comment("\nCombination preview:")
# protocol.comment(f"Total combinations to create: {len(all_combos)}")
# for i, combo in enumerate(all_combos):
    # protocol.comment(f"Dest well {i+1}: Mix from source wells {combo}")

