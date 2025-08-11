from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design CFPS part 2',
    'author': 'LDRD team ',
    'description': 'CFPS plate setup from PCR templates and standards followed by CFPS on the deck',
    'source': 'FlexGB/pd_cfps_03.py'
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

"""
This protocol uses 8-channel operations for everything. It actually does not use the p1000 at all.
One issue is that the internal standards are getting CFPS reagents transferred into the empty wells where they should not be.
We will need to remove the content of these wells at the end. Is it possible to switch back from MULTI to SINGLE channel mode and remove the content of the wells?

"""
# Protocol Configuration
config = {
    # PCR product settings
    'combinations': [[2,18],[3,19],[4,20],[5,21]], # 1-indexed source well numbers (kept for total calculation)
    'pcr_transfer_volume': 2,    # µL of PCR product to transfer to reaction plate
    'internal_standards_wells': [1, 2, 3, 4, 5], # 1-indexed well positions (A1, B1, C1, D1, E!) in the internal standards column [copied in this order leaving empty wells for later controls in the assay protocol]

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
    'reaction_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt', # Reagent plate for reactions
    'internal_standards_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt', # Internal standards
    'pcr_adapter_type': 'opentrons_96_pcr_adapter',  # Aluminum adapter for PCR plates
    'tip_rack_type_50_01': 'opentrons_flex_96_tiprack_50ul',
    'pipette_type_50': 'flex_8channel_50',
    'tip_rack_type_200_01': 'opentrons_flex_96_tiprack_200ul',
    'pipette_type_1000': 'flex_8channel_1000',

    # Deck positions
    'temp_module_position': 'C1',          # Temperature module for reaction assembly
    'shaker_module_position': 'D1',        # Heater/shaker module for incubation
    'source_plate_position': 'B2',         # Diluted PCR products plate
    'internal_standards_initial_position': 'B4', # Initial position for internal standards
    'internal_standards_final_position': 'B3',   # Final position for internal standards
    'reaction_plate_initial_position': 'A4', # Initial staging position for reaction plate
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


def run(protocol):
    # Load temperature module and adapter for reaction assembly
    temp_mod = protocol.load_module(module_name="temperature module gen2", location=config['temp_module_position'])
    temp_adapter = temp_mod.load_adapter(config['pcr_adapter_type'])

    # Load heater/shaker module for incubation
    shaker_mod = protocol.load_module(module_name="heaterShakerModuleV1", location=config['shaker_module_position'])
    shaker_adapter = shaker_mod.load_adapter(config['pcr_adapter_type'])

    # Set temperature for reaction assembly
    temp_mod.set_temperature(config['temperature'])

    # Load source plate with diluted PCR products on B2
    source_plate = protocol.load_labware(config['source_plate_type'], config['source_plate_position'])
    source_plate.set_offset(x=0.4, y=0.4, z=0.0)

    reaction_plate = protocol.load_labware(config['reaction_plate_type'], config['reaction_plate_initial_position'])
    # protocol.comment("Moving reaction plate from A4 to temperature module (C1)")
    # protocol.move_labware(
    #     labware=reaction_plate,
    #     new_location=temp_adapter,
    #     use_gripper=True
    # )


    # Load tip racks
    tiprack_50 = protocol.load_labware(
        load_name=config['tip_rack_type_50_01'], location=config['tip_rack_position_50_01']
    )

    tiprack_200 = protocol.load_labware(
        load_name=config['tip_rack_type_200_01'], location=config['tip_rack_position_200_01']
    )

    # Load pipettes
    p50 = protocol.load_instrument('flex_8channel_50', mount='right', tip_racks=[tiprack_50])
    p1000 = protocol.load_instrument('flex_8channel_1000', mount='left', tip_racks=[tiprack_200])

    # Start with 8-channel mode for all operations
    p50.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_50])


    chute = protocol.load_waste_chute()

    protocol.comment(f"Setting heater/shaker to {config['heater_shaker_temp']}°C and starting heating")
    shaker_mod.set_target_temperature(config['heater_shaker_temp'])

    shaker_mod.open_labware_latch()

    # Move reaction plate to heater/shaker
    protocol.comment("Moving reaction plate from A4 to heater/shaker (D1)")
    protocol.move_labware(
        labware=reaction_plate,
        new_location=shaker_adapter,
        use_gripper=True
    )

    shaker_mod.close_labware_latch()

    # Start shaking for 3 hours
    protocol.comment(f"=== Starting shaking at {config['shaking_speed']} rpm for {config['shaking_duration']} minutes (3 hours) ===")
    shaker_mod.set_and_wait_for_shake_speed(config['shaking_speed'])
    protocol.delay(minutes=config['shaking_duration'])

    # Stop shaking
    protocol.comment("Stopping shaking")
    shaker_mod.deactivate_shaker()

    shaker_mod.open_labware_latch()

    # Move reaction plate back to A4
    protocol.comment("Moving reaction plate from heater/shaker back to A4")
    protocol.move_labware(
        labware=reaction_plate,
        new_location=config['reaction_plate_initial_position'],
        use_gripper=True
    )

    protocol.comment("=== Protocol Complete ===")
    # protocol.comment(f"Total combinations: {total_combinations}")
    # protocol.comment(f"Internal standards placed in column: {internal_standards_column}")
    protocol.comment(f"Diluted PCR products transferred from {config['source_plate_position']} to reaction plate")
    protocol.comment(f"Internal standards plate moved from {config['internal_standards_initial_position']} to {config['internal_standards_final_position']}")
    protocol.comment(f"PCR transfer volume: {config['pcr_transfer_volume']}µL per well")
    protocol.comment(f"Reaction assembly completed on temperature module at {config['temperature']}°C")
    protocol.comment(f"Incubation completed: {config['shaking_duration']} minutes at {config['heater_shaker_temp']}°C with {config['shaking_speed']} rpm shaking")
    protocol.comment(f"Final reaction plate is staged at {config['reaction_plate_initial_position']}")
