from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design Golden Gate',
    'author': 'LDRD team ',
    'description': 'Golden Gate Assembly for Protein Design',
    'source': 'FlexGB/pd_golden_gate_01.py'
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}


# Protocol Configuration
config = {
    # Combinatorial mixing
    'combinations': [[2,18],[3,19],[4,20],[5,21]],
    'transfer_volume': 2,  # µL from each source well

    # Master mix settings
    'master_mix_volume': 12,  # µL per destination well
    'master_mix_well_volume': 100,  # µL per master mix well
    'master_mix_start_well': 32,  # 0-indexed well number

    # Temperature settings
    'temperature': 4,  # °C

    # Labware
    'source_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',
    'dest_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',
    'tip_rack_type_50_01': 'opentrons_flex_96_tiprack_50ul',
    'pipette_type_50': 'flex_8channel_50',
    'tip_rack_type_200_01': 'opentrons_flex_96_tiprack_200ul',
    'pipette_type_1000': 'flex_8channel_1000',

    # Deck positions
    'temp_module_position': 'C1',
    'source_plate_initial_position': 'C1',
    'dest_plate_position': 'B2',
    'tip_rack_position_50_01': 'A1',
    'tip_rack_position_200_01': 'A2',
    'reagent_block': 'D1'
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

def transfer_combinatorial_liquids(protocol, source_plate, dest_plate, pipette, config):
    """
    Transfer liquids based on combinatorial mixing pattern

    Args:
        protocol: Opentrons protocol object
        source_plate: Source PCR plate labware
        dest_plate: Destination PCR plate labware
        pipette: Pipette instrument
        config: Configuration dictionary containing combinations and transfer_volume
    """

    combinations = config['combinations']
    transfer_volume = config['transfer_volume']

    # Calculate total combinations before generating them
    total_combinations = calculate_total_combinations(combinations)
    protocol.comment(f"Total destination wells needed: {total_combinations}")

    # Generate all possible combinations
    all_combinations = generate_all_combinations(combinations)

    print(f"Generated {len(all_combinations)} combinations:")
    for i, combo in enumerate(all_combinations):
        print(f"Destination well {i+1}: Sources {combo}")

    # Perform transfers
    dest_well_number = 1

    for combination in all_combinations:
        # For each combination, transfer from all source wells to one destination well
        dest_well = dest_plate.wells()[dest_well_number - 1]  # Convert to 0-based index

        protocol.comment(f"\nTransferring to destination well {dest_well_number}:")

        for source_well_number in combination:
            source_well = source_plate.wells()[source_well_number - 1]  # Convert to 0-based index

            protocol.comment(f"  - Transferring {transfer_volume}µL from source well {source_well_number} to dest well {dest_well_number}")

            # Perform the transfer
            pipette.transfer(
                transfer_volume,
                source_well,
                dest_well,
                new_tip='always'  # Use fresh tip for each transfer
            )
        dest_well_number += 1

def add_master_mix_to_combinations(protocol, source_plate, dest_plate, pipette, config):
    """
    Add master mix to each destination well after combinatorial transfers

    Args:
        protocol: Opentrons protocol object
        source_plate: Source PCR plate labware (contains master mix)
        dest_plate: Destination PCR plate labware
        pipette: Pipette instrument
        config: Configuration dictionary containing master mix settings
    """

    combinations = config['combinations']
    master_mix_volume = config['master_mix_volume']
    master_mix_well_volume = config['master_mix_well_volume']
    master_mix_start_well = config['master_mix_start_well']

    # Calculate total combinations
    total_combinations = calculate_total_combinations(combinations)

    # Calculate how many destination wells can be served by one master mix well
    dispenses_per_well = master_mix_well_volume // master_mix_volume
    protocol.comment(f"Each master mix well ({master_mix_well_volume}µL) can serve {dispenses_per_well} destination wells")

    # Calculate how many master mix wells we need
    master_mix_wells_needed = (total_combinations + dispenses_per_well - 1) // dispenses_per_well  # Ceiling division
    protocol.comment(f"Total master mix wells needed: {master_mix_wells_needed}")

    # Track current master mix well and remaining volume
    current_master_mix_well = master_mix_start_well
    remaining_dispenses = dispenses_per_well

    protocol.comment(f"\nAdding {master_mix_volume}µL master mix to each destination well:")

    for dest_well_number in range(1, total_combinations + 1):
        # Check if we need to switch to next master mix well
        if remaining_dispenses == 0:
            current_master_mix_well += 1
            remaining_dispenses = dispenses_per_well
            protocol.comment(f"  Switching to master mix well {current_master_mix_well + 1} (0-indexed: {current_master_mix_well})")

        # Get the destination well
        dest_well = dest_plate.wells()[dest_well_number - 1]  # Convert to 0-based index

        # Get the current master mix well
        master_mix_well = source_plate.wells()[current_master_mix_well]

        protocol.comment(f"  Dest well {dest_well_number}: Adding {master_mix_volume}µL from master mix well {current_master_mix_well + 1} (0-indexed: {current_master_mix_well})")

        # Transfer master mix
        pipette.transfer(
            master_mix_volume,
            master_mix_well,
            dest_well,
            new_tip='always'  # Use fresh tip for each master mix transfer
        )

        # Update remaining dispenses
        remaining_dispenses -= 1

    protocol.comment(f"\nMaster mix addition complete. Used wells {master_mix_start_well + 1} to {current_master_mix_well + 1} (0-indexed: {master_mix_start_well} to {current_master_mix_well})")

    return current_master_mix_well  # Return the last used well




def run(protocol: protocol_api.ProtocolContext):
    # Load temperature module and adapter
    temp_mod = protocol.load_module(module_name="temperature module gen2", location=config['temp_module_position'])
    temp_adapter = temp_mod.load_adapter("opentrons_96_well_aluminum_block")

    # Set temperature
    temp_mod.set_temperature(config['temperature']) #TODO: make seperate, or just set earlier, only 1 hour with plate

    # Load source plate initially on A4
    # source_plate = protocol.load_labware(config['source_plate_type'], config['source_plate_initial_position'])
    source_plate = temp_adapter.load_labware(config['source_plate_type'])

    # Move source plate to temperature module
    # protocol.move_labware(
    #     labware=source_plate,
    #     new_location=temp_adapter,
    #     use_gripper=True
    # )

    chute = protocol.load_waste_chute()

    source_plate.set_offset(x=0.40, y=0.50, z=2.40)


    # Load destination plate
    dest_plate = protocol.load_labware(config['dest_plate_type'], config['dest_plate_position'])
    dest_plate.set_offset(x=0.4, y=0.4, z=0.0)


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
    total_dest_wells = transfer_combinatorial_liquids(
        protocol=protocol,
        source_plate=source_plate,
        dest_plate=dest_plate,
        pipette=p50,
        config=config
    )

    # Add master mix to each destination well
    last_master_mix_well = add_master_mix_to_combinations(
        protocol=protocol,
        source_plate=source_plate,
        dest_plate=dest_plate,
        pipette=p50,
        config=config
    )

    # mixing the content

    # moving the PCR plate to staging (seal and to thermocycler)

    # moving the reagents to staiging (seal and back to Flex?)

# Preview what will be transferred using the combinations defined above:
# Calculate total combinations
total_combos = calculate_total_combinations(config['combinations'])
# protocol.comment(f"Calculation: {len(config['combinations'][0])} × {len(config['combinations'][1])} × {len(config['combinations'][2])} × {len(config['combinations'][3])} = {total_combos}")

all_combos = generate_all_combinations(config['combinations'])

# protocol.comment("\nCombination preview:")
# protocol.comment(f"Total combinations to create: {len(all_combos)}")
# for i, combo in enumerate(all_combos):
    # protocol.comment(f"Dest well {i+1}: Mix from source wells {combo}")

