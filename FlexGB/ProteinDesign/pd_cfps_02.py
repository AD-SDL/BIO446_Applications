from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design CFPS',
    'author': 'LDRD team ',
    'description': 'CFPS plate setup from PCR templates and standards followed by CFPS on the deck',
    'apiLevel': '2.20',
    'requirements': {"robotType": "Flex", "apiLevel": "2.20"},
    'source': 'FlexGB/pd_cfps_02.py'  
}

"""
This protocol is designed to set up a CFPS (Cell-Free Protein Synthesis) experiment using PCR templates and internal standards. 

2025-07-28: gbabnigg@anl.gov
There might be some issues with this proptocol. While most operations can be done with 8-channel operations, the internal standards transfer is done with single-channel pipette.
Currently the p1000 is used for multichannel operations, but it should use a 50 uL pipette for this purpose.
We could do all operations with a single-channel pipette, but this would be very slow.
Maybe we should swap the pipettes and use the 50 uL pipette for multichannel operations and the 1000 uL pipette for single-channel operations.


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
    'shaking_speed': 100,         # rpm for shaking (Is this optimal for CFPS? The pilots CFPS were run without shaking without issues in the assays)
    
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


def transfer_pcr_products(protocol, source_plate, reaction_plate, pipette, config):
    """
    Transfer PCR products from source plate (B2) to reaction plate (C1) using 8-channel pipette
    
    Args:
        protocol: Opentrons protocol object
        source_plate: Source plate with diluted PCR products (B2)
        reaction_plate: Reaction plate on temperature module (C1)
        pipette: Pipette instrument (8-channel mode)
        config: Configuration dictionary containing transfer settings
    """
    
    # Get settings from config
    pcr_volume = config['pcr_transfer_volume']
    template_cols = [col - 1 for col in config['template_columns']]  # Convert to 0-indexed
    
    # Calculate total number of PCR products to transfer
    total_combinations = calculate_total_combinations(config['combinations'])
    
    protocol.comment("\n=== Transferring PCR Products to Reaction Plate ===")
    protocol.comment(f"Total PCR products to transfer: {total_combinations}")
    protocol.comment(f"Transfer volume: {pcr_volume}µL per well")
    protocol.comment(f"Target template columns: {config['template_columns']}")
    protocol.comment("Using 8-channel pipette for column-wise transfers")
    
    # Calculate how many columns are needed for PCR products
    columns_needed = (total_combinations + 7) // 8  # Ceiling division
    
    # Transfer PCR products column by column using 8-channel
    for col_idx in range(columns_needed):
        if col_idx >= len(template_cols):
            protocol.comment(f"Warning: Need {columns_needed} columns but only {len(template_cols)} template columns defined")
            break
            
        template_col_idx = template_cols[col_idx]
        template_col_num = template_col_idx + 1  # Convert to 1-indexed for display
        
        # Source column (from source plate)
        source_column = source_plate.columns()[col_idx]
        
        # Destination column (in reaction plate)
        dest_column = reaction_plate.columns()[template_col_idx]
        
        protocol.comment(f"Transferring {pcr_volume}µL from source column {col_idx + 1} to template column {template_col_num} (8-channel)")
        
        # Transfer entire column at once (8-channel operation)
        pipette.transfer(
            pcr_volume,
            source_column[0],  # A row (represents entire column for 8-channel)
            dest_column[0],   # A row (represents entire column for 8-channel)
            new_tip='always'
        )
    
    protocol.comment("=== PCR Product Transfer Complete ===\n")
    protocol.comment(f"Transferred {columns_needed} full columns using 8-channel pipette")
    return total_combinations



def transfer_internal_standards(protocol, internal_standards_plate, reaction_plate, pipette, config, internal_standards_column):
    """
    Transfer internal standards to reaction plate in a dynamically calculated column
    
    Args:
        protocol: Opentrons protocol object
        internal_standards_plate: Internal standards plate (B3)
        reaction_plate: Reaction plate on temperature module (C1)
        pipette: Pipette instrument (single channel mode)
        config: Configuration dictionary containing transfer settings
        internal_standards_column: 1-indexed column number for internal standards
    """
    
    # Get settings from config
    transfer_volume = config['pcr_transfer_volume']
    standards_col = internal_standards_column - 1  # Convert to 0-indexed
    standards_wells = [well - 1 for well in config['internal_standards_wells']]  # Convert to 0-indexed
    
    protocol.comment("\n=== Transferring Internal Standards to Reaction Plate ===")
    protocol.comment(f"Target column: {internal_standards_column} (dynamically calculated)")
    protocol.comment(f"Transfer volume: {transfer_volume}µL per well")
    protocol.comment(f"Wells to fill: {config['internal_standards_wells']} (leaving others empty for controls)")
    
    # Get the destination column
    dest_column = reaction_plate.columns()[standards_col]
    
    # Transfer internal standards to specified wells only
    for i, well_idx in enumerate(standards_wells):
        # Source well from internal standards plate (sequential)
        source_well = internal_standards_plate.wells()[i]
        
        # Destination well in the internal standards column
        dest_well = dest_column[well_idx]
        
        protocol.comment(f"  Transferring {transfer_volume}µL from {source_well.display_name} to {dest_well.display_name}")
        
        # Transfer internal standard
        pipette.transfer(
            transfer_volume,
            source_well,
            dest_well,
            new_tip='always'  # Single tip for each transfer
        )
    
    protocol.comment(f"=== Internal Standards Transfer Complete ===")
    protocol.comment(f"Filled {len(standards_wells)} wells in column {internal_standards_column}, leaving others empty for controls\n")
    
    return len(standards_wells)


def prepare_reagent_mix(protocol, reaction_plate, pipette_8ch, pipette_1ch, config, internal_standards_column):
    """
    Prepare reagent mix by combining reagents from specified columns into mixing column,
    then distribute to template columns using 8-channel pipette and internal standards using single-channel
    
    Args:
        protocol: Opentrons protocol object
        reaction_plate: Reaction plate labware (mix A and mix B)
        pipette_8ch: 8-channel pipette instrument for template columns
        pipette_1ch: Single-channel pipette instrument for internal standards
        config: Configuration dictionary containing reagent mixing settings
        internal_standards_column: 1-indexed column number for internal standards
    """
    
    # Get settings from config
    template_cols = [col - 1 for col in config['template_columns']]  # Convert to 0-indexed
    internal_standards_col = internal_standards_column - 1  # Convert to 0-indexed
    internal_standards_wells = [well - 1 for well in config['internal_standards_wells']]  # Convert to 0-indexed
    
    mix_A_col = config['reagent_mix_A_column'] - 1  # Convert to 0-indexed
    mix_B_col = config['reagent_mix_B_column'] - 1  # Convert to 0-indexed
    mixing_col = config['reagent_mixing_column'] - 1  # Convert to 0-indexed
    
    reagent_mix_A_volume = config['reagent_mix_A_volume']
    reagent_mix_B_volume = config['reagent_mix_B_volume']
    final_reagent_volume = config['final_reagent_volume']
    mixing_repetitions = config['mixing_repetitions']
    mixing_volume = config['mixing_volume']
    
    protocol.comment("\n=== Starting Reagent Preparation ===")
    protocol.comment(f"Mix A source: Column {config['reagent_mix_A_column']}")
    protocol.comment(f"Mix B source: Column {config['reagent_mix_B_column']}")
    protocol.comment(f"Mixing column: Column {config['reagent_mixing_column']}")
    protocol.comment(f"Template columns: {config['template_columns']} (8-channel distribution)")
    protocol.comment(f"Internal standards column: {internal_standards_column} (single-channel distribution)")
    protocol.comment(f"Internal standards wells: {config['internal_standards_wells']} (others left empty)")
    
    # Define column wells for 8-channel operations
    mix_A_column = reaction_plate.columns()[mix_A_col]
    mix_B_column = reaction_plate.columns()[mix_B_col]
    mixing_column = reaction_plate.columns()[mixing_col]
    
    # Step 1: Transfer mix A to mixing column (8-channel operation)
    protocol.comment(f"Transferring {reagent_mix_A_volume}µL from column {config['reagent_mix_A_column']} to column {config['reagent_mixing_column']} (8-channel)")
    pipette_8ch.transfer(
        reagent_mix_A_volume,
        mix_A_column[0],  # A row (represents entire column for 8-channel)
        mixing_column[0],  # A row (represents entire column for 8-channel)
        new_tip='always'
    )
    
    # Step 2: Transfer mix B to mixing column (8-channel operation)
    protocol.comment(f"Transferring {reagent_mix_B_volume}µL from column {config['reagent_mix_B_column']} to column {config['reagent_mixing_column']} (8-channel)")
    pipette_8ch.transfer(
        reagent_mix_B_volume,
        mix_B_column[0],  # A row (represents entire column for 8-channel)
        mixing_column[0],  # A row (represents entire column for 8-channel)
        new_tip='always'
    )
    
    # Step 3: Mix contents in mixing column (8-channel operation)
    protocol.comment(f"Mixing contents in column {config['reagent_mixing_column']} ({mixing_repetitions} repetitions with {mixing_volume}µL, 8-channel)")
    pipette_8ch.pick_up_tip()
    pipette_8ch.mix(
        repetitions=mixing_repetitions,
        volume=mixing_volume,
        location=mixing_column[0]  # A row (represents entire column for 8-channel)
    )
    pipette_8ch.drop_tip()
    
    # Step 4: Distribute mixed reagents to template columns (8-channel operations)
    protocol.comment(f"\n--- Distributing reagents to template columns (8-channel) ---")
    for template_col_idx in template_cols:
        template_column = reaction_plate.columns()[template_col_idx]
        template_col_num = template_col_idx + 1  # Convert back to 1-indexed for display
        
        protocol.comment(f"Transferring {final_reagent_volume}µL from column {config['reagent_mixing_column']} to column {template_col_num} (8-channel)")
        pipette_8ch.transfer(
            final_reagent_volume,
            mixing_column[0],  # A row (represents entire column for 8-channel)
            template_column[0],  # A row (represents entire column for 8-channel)
            new_tip='always'
        )
    
    # Step 5: Distribute mixed reagents to internal standards column (single-channel operations)
    protocol.comment(f"\n--- Distributing reagents to internal standards column (single-channel) ---")
    internal_standards_column_wells = reaction_plate.columns()[internal_standards_col]
    
    for well_idx in internal_standards_wells:
        # Source well from mixing column
        source_well = mixing_column[well_idx]
        
        # Destination well in internal standards column
        dest_well = internal_standards_column_wells[well_idx]
        
        protocol.comment(f"Transferring {final_reagent_volume}µL from {source_well.display_name} to {dest_well.display_name} (single-channel)")
        pipette_1ch.transfer(
            final_reagent_volume,
            source_well,
            dest_well,
            new_tip='always'
        )
    
    protocol.comment("=== Reagent Preparation Complete ===\n")
    protocol.comment(f"Reagents distributed to {len(template_cols)} template columns (8-channel) + {len(internal_standards_wells)} wells in internal standards column (single-channel)")
    protocol.comment(f"Empty wells in internal standards column left without reagents for controls")


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
    
    # Load internal standards plate initially on B4, then move to B3
    internal_standards_plate = protocol.load_labware(config['internal_standards_plate_type'], config['internal_standards_initial_position'])
    protocol.comment("Moving internal standards plate from B4 to B3")
    protocol.move_labware(
        labware=internal_standards_plate,
        new_location=config['internal_standards_final_position'],
        use_gripper=True
    )
    
    # Load reaction plate initially on A4, then move to temperature module
    reaction_plate = protocol.load_labware(config['reaction_plate_type'], config['reaction_plate_initial_position'])
    protocol.comment("Moving reaction plate from A4 to temperature module (C1)")
    protocol.move_labware(
        labware=reaction_plate,
        new_location=temp_adapter,
        use_gripper=True
    )
    
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

    # Start with single channel mode for PCR product transfers
    p50.configure_nozzle_layout(style=SINGLE, start='A1', tip_racks=[tiprack_50])
    
    # Calculate internal standards column position
    internal_standards_column, total_combinations = calculate_internal_standards_column(config)
    protocol.comment(f"=== Dynamic Column Calculation ===")
    protocol.comment(f"Total combinations: {total_combinations}")
    protocol.comment(f"Columns needed for PCR products: {(total_combinations + 7) // 8}")
    protocol.comment(f"Internal standards will be placed in column: {internal_standards_column}")
    
    # Transfer PCR products from source plate (B2) to reaction plate (C1)
    protocol.comment("=== Transferring PCR Products to Reaction Plate ===")
    transfer_pcr_products(
        protocol=protocol,
        source_plate=source_plate,
        reaction_plate=reaction_plate,
        pipette=p50,
        config=config
    )
    
    # Transfer internal standards to reaction plate (C1)
    protocol.comment("=== Transferring Internal Standards to Reaction Plate ===")
    transfer_internal_standards(
        protocol=protocol,
        internal_standards_plate=internal_standards_plate,
        reaction_plate=reaction_plate,
        pipette=p50,
        config=config,
        internal_standards_column=internal_standards_column
    )
    
    # Configure pipettes for reagent preparation
    protocol.comment("=== Configuring pipettes for reagent preparation ===")
    # p50 stays in single-channel mode for internal standards
    # Configure p1000 for 8-channel mode for template columns
    p1000.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_200])
    
    # Prepare reagent mix on temperature module (C1)
    protocol.comment("=== Reaction Assembly on Temperature Module ===")
    prepare_reagent_mix(
        protocol=protocol,
        reaction_plate=reaction_plate,
        pipette_8ch=p1000,  # Use p1000 for 8-channel operations
        pipette_1ch=p50,    # Use p50 for single-channel operations
        config=config,
        internal_standards_column=internal_standards_column
    )
    
    # Move reaction plate back to A4 for staging
    protocol.comment("Moving reaction plate from temperature module back to A4")
    protocol.move_labware(
        labware=reaction_plate,
        new_location=config['reaction_plate_initial_position'],
        use_gripper=True
    )
    
    # Set up heater/shaker and start heating
    protocol.comment(f"Setting heater/shaker to {config['heater_shaker_temp']}°C and starting heating")
    shaker_mod.set_target_temperature(config['heater_shaker_temp'])
    
    # Pause for 5 minutes
    protocol.comment(f"=== Pausing for {config['pause_duration']} minutes ===")
    protocol.delay(minutes=config['pause_duration'])
    
    # Move reaction plate to heater/shaker
    protocol.comment("Moving reaction plate from A4 to heater/shaker (D1)")
    protocol.move_labware(
        labware=reaction_plate,
        new_location=shaker_adapter,
        use_gripper=True
    )
    
    # Start shaking for 3 hours
    protocol.comment(f"=== Starting shaking at {config['shaking_speed']} rpm for {config['shaking_duration']} minutes (3 hours) ===")
    shaker_mod.set_and_wait_for_shake_speed(config['shaking_speed'])
    protocol.delay(minutes=config['shaking_duration'])
    
    # Stop shaking
    protocol.comment("Stopping shaking")
    shaker_mod.deactivate_shaker()
    
    # Move reaction plate back to A4
    protocol.comment("Moving reaction plate from heater/shaker back to A4")
    protocol.move_labware(
        labware=reaction_plate,
        new_location=config['reaction_plate_initial_position'],
        use_gripper=True
    )

    # Move internal standards plate back to its final position
    protocol.comment("Moving internal standards plate from B3 back to B4")
    protocol.move_labware(
        labware=internal_standards_plate,
        new_location=config['internal_standards_initial_position'],
        use_gripper=True
    )

    protocol.comment("=== Protocol Complete ===")
    protocol.comment(f"Total combinations: {total_combinations}")
    protocol.comment(f"Internal standards placed in column: {internal_standards_column}")
    protocol.comment(f"Diluted PCR products transferred from {config['source_plate_position']} to reaction plate")
    protocol.comment(f"Internal standards plate moved from {config['internal_standards_initial_position']} to {config['internal_standards_final_position']}")
    protocol.comment(f"PCR transfer volume: {config['pcr_transfer_volume']}µL per well")
    protocol.comment(f"Reaction assembly completed on temperature module at {config['temperature']}°C")
    protocol.comment(f"Incubation completed: {config['shaking_duration']} minutes at {config['heater_shaker_temp']}°C with {config['shaking_speed']} rpm shaking")
    protocol.comment(f"Final reaction plate is staged at {config['reaction_plate_initial_position']}")


# Preview what will be transferred using the combinations defined above:
total_combos = calculate_total_combinations(config['combinations'])
all_combos = generate_all_combinations(config['combinations'])