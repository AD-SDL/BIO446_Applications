from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design fdglu',
    'author': 'LDRD team ',
    'description': 'fdglu assay preparation',
    'source': 'FlexAS/pd_fdglu_assay_01.py'
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

# Protocol Configuration
config = {
    # PCR product settings
    'combinations': [[2,18],[3,19],[4,20],[5,21]], # 1-indexed source well numbers (kept for total calculation)
    'fdglu_volume': 100,    # µL of PCR product to transfer to reaction plate
    'source_samples_volume': 20,
    'protein_and_buffer_volume': 20,
    'internal_standards_wells': [1, 2, 3, 4, 5], # 1-indexed well positions (A1, B1, C1, D1, E!) in the internal standards column [copied in this order leaving empty wells for later controls in the assay protocol]
    'protein_and_buffer_wells': [15, 16],
    'fdglu_col': 5,

    # Incubation settings
    'heater_shaker_temp': 37,     # °C for heater/shaker
    'pause_duration': 5,          # minutes for pause after reaction assembly (PF400 to sealer and back)
    'shaking_duration': 180,      # minutes (3 hours) for shaking (CFPS)
    'shaking_speed': 200,         # rpm for shaking (Is this optimal for CFPS? The pilots CFPS were run without shaking without issues in the assays) #TODO 100 is too low 200-3000

    # Reagent mixing settings (using 8-channel pipette)
    # Right now we assume that the combined reagents fit into one well (max 150µL). Using 25 uL reactions this is sufficient for 6 reactions (6 columns).
    # The number of columns is calculated based on the total number of combinations + 1 for internal standards (for this eample 3 columns are needed)
    'reagent_mix_A_column': 5,    # Column number for mix A (1-indexed)
    'reagent_mix_B_column': 7,    # Column number for mix B (1-indexed)
    'reagent_mixing_column': 8,   # Column number for mixing reagents (1-indexed)
    'reagent_mix_A_volume': 60,  # µL from mix A column to mixing column
    'reagent_mix_B_volume': 30,   # µL from mix B column to mixing column
    'final_reagent_volume': 23,   # µL from mixing column to template columns
    'mixing_repetitions': 5,      # Number of mix cycles
    'mixing_volume': 20,          # Volume for mixing (appropriate for ~25µL total)

    # Template column settings
    # This is coming from the PCR dilution/assay protocol
    'template_columns': [7, 8],  # List of column numbers with templates (1-indexed)

    # Temperature settings
    'temperature': 4,  # °C

    # Labware
    'source_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',  # Diluted PCR products
    'cfps_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt', # Reagent plate for reactions
    'dest_plate_type': 'corning_96_wellplate_360ul_flat', # Internal standards
    'pcr_adapter_type': 'opentrons_96_pcr_adapter',  # Aluminum adapter for PCR plates
    'tip_rack_type_50_01': 'opentrons_flex_96_tiprack_50ul',
    'pipette_type_50': 'flex_8channel_50',
    'tip_rack_type_200_01': 'opentrons_flex_96_tiprack_200ul',
    'pipette_type_1000': 'flex_8channel_1000',
    'reagent_plate_type': 'nest_12_reservoir_15ml',


    # Deck positions
    'temp_module_position': 'C1',          # Temperature module for reaction assembly
    'shaker_module_position': 'D1',        # Heater/shaker module for incubation
    'source_plate_position': 'B2',         # Diluted PCR products plate
    'reagent_plate_position': 'B3',   # Final position for internal standards
    'cfps_plate_position': 'C2', # Initial staging position for reaction plate
    'dest_plate_position': 'A3',
    'tip_rack_position_50_01': 'A1',
    'tip_rack_position_200_01': 'A2'
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


def calculate_internal_standards_column(config):
    """
    Calculate which column to use for internal standards based on total combinations

    Args:
        config: Configuration dictionary

    Returns:
        int: 1-indexed column number for internal standards
    """
    total_combinations = calculate_total_combinations(config['combinations'])

    # Calculate how many full columns are needed for PCR products (8 wells per column)
    columns_needed = (total_combinations + 7) // 8  # Ceiling division

    # Internal standards go in the next available column
    internal_standards_column = columns_needed + 1

    return internal_standards_column, total_combinations

def fdglu_to_dest(protocol, reagent_plate, dest_plate, pipette, config):
    fdglu_col = config["fdglu_col"]
    fdglu_vol = config["fdglu_volume"]
    total_combinations = calculate_total_combinations(config['combinations'])
    columns_needed = (total_combinations + 7) // 8
    source_col = reagent_plate.columns()[fdglu_col - 1]
    pipette.pick_up_tip()
    for col_idx in range(columns_needed+1):
        dest_col = dest_plate.columns()[col_idx]
        pipette.transfer(
            fdglu_vol,
            source_col[0],  # A row (represents entire column for 8-channel)
            dest_col[0],   # A row (represents entire column for 8-channel)
            new_tip='never'
        )
    pipette.drop_tip()



def cfps_to_dest(protocol, cfps_plate, dest_plate, pipette, config):
    cfps_vol = config["source_samples_volume"]
    total_combinations = calculate_total_combinations(config['combinations'])
    columns_needed = (total_combinations + 7) // 8
    for col_idx in range(columns_needed+1):
        source_col = cfps_plate.columns()[col_idx]
        dest_col = dest_plate.columns()[col_idx]
        pipette.transfer(
            cfps_vol,
            source_col[0],  # A row (represents entire column for 8-channel)
            dest_col[0],   # A row (represents entire column for 8-channel)
            new_tip='always',
            mix_after = (5, 20)
        )



def protein_buffer_to_dest(protocol, source_plate, dest_plate, pipette, config):
    #TODO: hardcode for now, discrpency in number of controls
    pb_wells = config['protein_and_buffer_wells']
    pb_vol = config['protein_and_buffer_volume']
    for well in pb_wells:
        source_well = source_plate.wells()[well-1]
        dest_well = dest_plate.wells()[(well-1)+8] #TODO hardcoding
        pipette.transfer(
            pb_vol,
            source_well,
            dest_well,
            new_tip='always',
            mix_after=(5, 20)
        )


def run(protocol):
    # Load temperature module and adapter for reaction assembly
    temp_mod = protocol.load_module(module_name="temperature module gen2", location=config['temp_module_position'])
    temp_adapter = temp_mod.load_adapter(config['pcr_adapter_type'])

    # Load heater/shaker module for incubation
    shaker_mod = protocol.load_module(module_name="heaterShakerModuleV1", location=config['shaker_module_position'])
    shaker_adapter = shaker_mod.load_adapter(config['pcr_adapter_type'])

    # Set temperature for reaction assembly
    # temp_mod.set_temperature(config['temperature'])

    # Load source plate with diluted PCR products on B2
    source_plate = protocol.load_labware(config['source_plate_type'], config['source_plate_position'])
    source_plate.set_offset(x=0.4, y=0.4, z=0.0)

    # Load internal standards plate initially on B4, then move to B3
    cfps_plate = protocol.load_labware(config['cfps_plate_type'], config['cfps_plate_position'])
    cfps_plate.set_offset(x=0.4, y=0.4, z=0.0)

    dest_plate = protocol.load_labware(config['dest_plate_type'], config['dest_plate_position'])
    dest_plate.set_offset(x=0.4, y=0.4, z=0.0)

    reagent_plate = protocol.load_labware(config['reagent_plate_type'], config['reagent_plate_position'])

    # Load tip racks
    tiprack_50 = protocol.load_labware(
        load_name=config['tip_rack_type_50_01'], location=config['tip_rack_position_50_01']
    )

    tiprack_50.set_offset(x=-0.5, y=0.3, z=0.7) #TODO

    tiprack_200 = protocol.load_labware(
        load_name=config['tip_rack_type_200_01'], location=config['tip_rack_position_200_01']
    )

    # Load pipettes
    p50 = protocol.load_instrument('flex_8channel_50', mount='right', tip_racks=[tiprack_50])
    p1000 = protocol.load_instrument('flex_8channel_1000', mount='left', tip_racks=[tiprack_200])

    # Start with 8-channel mode for all operations
    p50.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_50])
    p1000.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_200])


    chute = protocol.load_waste_chute()

    # Calculate internal standards column position
    internal_standards_column, total_combinations = calculate_internal_standards_column(config)
    protocol.comment(f"=== Dynamic Column Calculation ===")
    protocol.comment(f"Total combinations: {total_combinations}")
    protocol.comment(f"Columns needed for PCR products: {(total_combinations + 7) // 8}")
    protocol.comment(f"Internal standards will be placed in column: {internal_standards_column}")

    fdglu_to_dest(protocol=protocol,
                  reagent_plate=reagent_plate,
                  dest_plate=dest_plate,
                  pipette=p1000,
                  config=config)

    cfps_to_dest(protocol=protocol,
                 cfps_plate=cfps_plate,
                 dest_plate=dest_plate,
                 pipette=p50,
                 config=config)

    p50.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_50])

    protein_buffer_to_dest(protocol=protocol,
                           source_plate=source_plate,
                           dest_plate=dest_plate,
                           pipette=p50,
                           config=config)

# Preview what will be transferred using the combinations defined above:
total_combos = calculate_total_combinations(config['combinations'])
all_combos = generate_all_combinations(config['combinations'])