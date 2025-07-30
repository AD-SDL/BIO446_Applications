from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design CFPS Assay Assembly',
    'author': 'LDRD team',
    'description': 'Assay assembly from completed CFPS reaction plate and internal standards',
    'apiLevel': '2.20',
    'requirements': {"robotType": "Flex", "apiLevel": "2.20"},
    'source': 'FlexGB/pd_assay_01.py'  
}

"""
This protocol is a follow-up to the CFPS protocol. It takes the completed reaction plate
and internal standards plate to assemble an assay plate with reagents and samples.
Uses 8-channel operations for efficiency.
"""

# Protocol Configuration
config = {
    # From previous protocol - needed for column calculations
    'combinations': [[2,18],[3,19],[4,20],[5,21]], # 1-indexed source well numbers (kept for total calculation)
    'template_columns': [1, 2],  # This should be calculated based on total combinations
    
    # Assay assembly settings
    'assay_reagent_volume': 180,  # µL of assay reagent to add to each well
    'sample_transfer_volume': 20,  # µL of sample from reaction plate to assay plate
    
    # Mixing settings
    'mixing_repetitions': 5,      # Number of mix cycles after sample addition
    'mixing_volume': 50,          # Volume for mixing (appropriate for ~200µL total)
    
    # Deep-well plate contents
    'water_well': 1,              # 1-indexed well position for water in deep-well plate
    'assay_reagent_well': 5,      # 1-indexed well position for assay reagent in deep-well plate (FDGlu)
    
    # Temperature settings
    'temperature': 4,  # °C for reaction plate storage during assay assembly
    
    # Labware
    'reaction_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',  # Completed CFPS reaction plate
    'internal_standards_type': 'nest_96_wellplate_100ul_pcr_full_skirt',  # Internal standards plate
    'assay_plate_type': 'nest_96_wellplate_200ul_flat',  # Assay plate for final assembly
    'deep_well_plate_type': 'nest_12_reservoir_15ml',  # Deep-well plate with reagents
    'pcr_adapter_type': 'opentrons_96_pcr_adapter',  # Aluminum adapter for PCR plates
    'tip_rack_type_50': 'opentrons_flex_96_tiprack_50ul',
    'tip_rack_type_200': 'opentrons_flex_96_tiprack_200ul',
    'pipette_type_50': 'flex_8channel_50',
    'pipette_type_1000': 'flex_8channel_1000',
    
    # Deck positions
    'temp_module_position': 'C1',          # Temperature module for reaction plate
    'reaction_plate_initial_position': 'A4',  # Initial position for reaction plate (from previous protocol)
    'internal_standards_initial_position': 'B4',  # Initial position for internal standards plate
    'assay_plate_position': 'C3',          # Position for new assay plate
    'deep_well_plate_position': 'D3',      # Position for deep-well plate with reagents
    'staging_position': 'A2',              # Final staging position for completed assay plate
    'tip_rack_50_position': 'A1',
    'tip_rack_200_position': 'B1'
}


def calculate_total_combinations(combinations):
    """Calculate total number of combinations without generating them"""
    total = 1
    for sublist in combinations:
        total *= len(sublist)
    return total


def calculate_internal_standards_column(config):
    """
    Calculate which column internal standards are in based on total combinations
    (Same logic as previous protocol for consistency)
    
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


def determine_target_columns(config, internal_standards_column):
    """
    Determine which columns need assay reagent based on template columns and internal standards
    
    Args:
        config: Configuration dictionary
        internal_standards_column: 1-indexed column number for internal standards
        
    Returns:
        list: List of 1-indexed column numbers that need assay reagent
    """
    # Get template columns from config
    template_cols = config['template_columns'].copy()
    
    # Add internal standards column
    all_target_cols = template_cols + [internal_standards_column]
    
    # Sort for consistent ordering
    all_target_cols.sort()
    
    return all_target_cols


def dispense_assay_reagent(protocol, deep_well_plate, assay_plate, pipette, config, target_columns):
    """
    Dispense assay reagent from deep-well plate to assay plate columns
    
    Args:
        protocol: Opentrons protocol object
        deep_well_plate: Deep-well plate with assay reagent
        assay_plate: Target assay plate
        pipette: Pipette instrument (8-channel mode)
        config: Configuration dictionary
        target_columns: List of 1-indexed column numbers to fill with reagent
    """
    
    reagent_volume = config['assay_reagent_volume']
    reagent_well_idx = config['assay_reagent_well'] - 1  # Convert to 0-indexed
    
    protocol.comment("\n=== Dispensing Assay Reagent ===")
    protocol.comment(f"Reagent volume: {reagent_volume}µL per well")
    protocol.comment(f"Source: Deep-well plate well {config['assay_reagent_well']}")
    protocol.comment(f"Target columns: {target_columns}")
    protocol.comment("Using 8-channel pipette for efficient column-wise dispensing")
    
    # Get the reagent source well
    reagent_source = deep_well_plate.wells()[reagent_well_idx]
    
    # Dispense to each target column
    for col_num in target_columns:
        col_idx = col_num - 1  # Convert to 0-indexed
        target_column = assay_plate.columns()[col_idx]
        
        protocol.comment(f"Dispensing {reagent_volume}µL to column {col_num} (8-channel)")
        
        pipette.transfer(
            reagent_volume,
            reagent_source,
            target_column[0],  # A row (represents entire column for 8-channel)
            new_tip='always'
        )
    
    protocol.comment("=== Assay Reagent Dispensing Complete ===\n")
    protocol.comment(f"Dispensed reagent to {len(target_columns)} columns using 8-channel operations")


def transfer_samples_and_mix(protocol, reaction_plate, assay_plate, pipette, config, target_columns, internal_standards_column):
    """
    Transfer samples from reaction plate to assay plate and mix
    
    Args:
        protocol: Opentrons protocol object
        reaction_plate: Source reaction plate with CFPS products
        assay_plate: Target assay plate with reagent
        pipette: Pipette instrument (8-channel mode)
        config: Configuration dictionary
        target_columns: List of 1-indexed column numbers to transfer to
        internal_standards_column: 1-indexed column number for internal standards
    """
    
    sample_volume = config['sample_transfer_volume']
    mixing_reps = config['mixing_repetitions']
    mixing_vol = config['mixing_volume']
    template_cols = config['template_columns']
    
    protocol.comment("\n=== Transferring Samples and Mixing ===")
    protocol.comment(f"Sample volume: {sample_volume}µL per well")
    protocol.comment(f"Mixing: {mixing_reps} repetitions with {mixing_vol}µL")
    protocol.comment(f"Template columns: {template_cols}")
    protocol.comment(f"Internal standards column: {internal_standards_column}")
    protocol.comment("Using 8-channel pipette for efficient column-wise operations")
    
    # Transfer from template columns
    for col_num in template_cols:
        if col_num in target_columns:
            col_idx = col_num - 1  # Convert to 0-indexed
            
            source_column = reaction_plate.columns()[col_idx]
            dest_column = assay_plate.columns()[col_idx]
            
            protocol.comment(f"Transferring {sample_volume}µL from reaction column {col_num} to assay column {col_num} (8-channel)")
            
            # Transfer and mix in one operation
            pipette.transfer(
                sample_volume,
                source_column[0],  # A row (represents entire column for 8-channel)
                dest_column[0],   # A row (represents entire column for 8-channel)
                mix_after=(mixing_reps, mixing_vol),
                new_tip='always'
            )
    
    # Transfer from internal standards column
    if internal_standards_column in target_columns:
        standards_col_idx = internal_standards_column - 1  # Convert to 0-indexed
        
        source_column = reaction_plate.columns()[standards_col_idx]
        dest_column = assay_plate.columns()[standards_col_idx]
        
        protocol.comment(f"Transferring {sample_volume}µL from reaction column {internal_standards_column} (internal standards) to assay column {internal_standards_column} (8-channel)")
        
        # Transfer and mix in one operation
        pipette.transfer(
            sample_volume,
            source_column[0],  # A row (represents entire column for 8-channel)
            dest_column[0],   # A row (represents entire column for 8-channel)
            mix_after=(mixing_reps, mixing_vol),
            new_tip='always'
        )
    
    protocol.comment("=== Sample Transfer and Mixing Complete ===\n")
    protocol.comment(f"Transferred samples from {len(target_columns)} columns with mixing")


def run(protocol):
    # Load temperature module and adapter for reaction plate
    temp_mod = protocol.load_module(module_name="temperature module gen2", location=config['temp_module_position'])
    temp_adapter = temp_mod.load_adapter(config['pcr_adapter_type'])
    
    # Set temperature for reaction plate storage
    temp_mod.set_temperature(config['temperature'])
    
    # Load reaction plate from initial position (A4) and move to temperature module
    reaction_plate = protocol.load_labware(config['reaction_plate_type'], config['reaction_plate_initial_position'])
    protocol.comment("Moving reaction plate from A4 to temperature module (C1)")
    protocol.move_labware(
        labware=reaction_plate,
        new_location=temp_adapter,
        use_gripper=True
    )
    
    # Load internal standards plate (not moved, stays at B4)
    internal_standards_plate = protocol.load_labware(config['internal_standards_type'], config['internal_standards_initial_position'])
    
    # Load new assay plate
    assay_plate = protocol.load_labware(config['assay_plate_type'], config['assay_plate_position'])
    
    # Load deep-well plate with reagents
    deep_well_plate = protocol.load_labware(config['deep_well_plate_type'], config['deep_well_plate_position'])
    
    # Load tip racks
    tiprack_50 = protocol.load_labware(config['tip_rack_type_50'], config['tip_rack_50_position'])
    tiprack_200 = protocol.load_labware(config['tip_rack_type_200'], config['tip_rack_200_position'])
    
    # Load pipettes
    p50 = protocol.load_instrument(config['pipette_type_50'], mount='right', tip_racks=[tiprack_50])
    p200 = protocol.load_instrument(config['pipette_type_1000'], mount='left', tip_racks=[tiprack_200])
    
    # Configure pipettes for 8-channel operation
    p50.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_50])
    p200.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_200])
    
    # Calculate internal standards column position (same logic as previous protocol)
    internal_standards_column, total_combinations = calculate_internal_standards_column(config)
    protocol.comment(f"=== Column Layout from Previous Protocol ===")
    protocol.comment(f"Total combinations: {total_combinations}")
    protocol.comment(f"Template columns: {config['template_columns']}")
    protocol.comment(f"Internal standards column: {internal_standards_column}")
    
    # Determine which columns need assay reagent
    target_columns = determine_target_columns(config, internal_standards_column)
    protocol.comment(f"Target columns for assay: {target_columns}")
    
    # Step 1: Dispense assay reagent to all target columns
    protocol.comment("=== Step 1: Dispensing Assay Reagent ===")
    dispense_assay_reagent(
        protocol=protocol,
        deep_well_plate=deep_well_plate,
        assay_plate=assay_plate,
        pipette=p200,  # Use larger pipette for 180µL transfers
        config=config,
        target_columns=target_columns
    )
    
    # Step 2: Transfer samples from reaction plate and mix
    protocol.comment("=== Step 2: Transferring Samples and Mixing ===")
    transfer_samples_and_mix(
        protocol=protocol,
        reaction_plate=reaction_plate,
        assay_plate=assay_plate,
        pipette=p50,  # Use smaller pipette for 20µL transfers
        config=config,
        target_columns=target_columns,
        internal_standards_column=internal_standards_column
    )
    
    # Step 3: Move assay plate to staging area
    protocol.comment("=== Step 3: Moving Assay Plate to Staging Area ===")
    protocol.comment(f"Moving assay plate from {config['assay_plate_position']} to staging position {config['staging_position']}")
    protocol.move_labware(
        labware=assay_plate,
        new_location=config['staging_position'],
        use_gripper=True
    )
    
    protocol.comment("=== Assay Assembly Protocol Complete ===")
    protocol.comment(f"Assay reagent volume per well: {config['assay_reagent_volume']}µL")
    protocol.comment(f"Sample transfer volume per well: {config['sample_transfer_volume']}µL")
    protocol.comment(f"Final volume per well: ~{config['assay_reagent_volume'] + config['sample_transfer_volume']}µL")
    protocol.comment(f"Columns processed: {target_columns}")
    protocol.comment(f"Template columns: {config['template_columns']}")
    protocol.comment(f"Internal standards column: {internal_standards_column}")
    protocol.comment(f"Assay plate staged at: {config['staging_position']}")
    protocol.comment(f"Reaction plate remains on temperature module at {config['temperature']}°C")