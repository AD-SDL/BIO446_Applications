from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design CFPS Assay Assembly',
    'author': 'LDRD team',
    'description': 'Assay assembly from completed CFPS reaction plate and internal standards',
    'apiLevel': '2.20',
    'requirements': {"robotType": "Flex", "apiLevel": "2.20"},
    'source': 'FlexGB/pd_cfps_assay.py'  
}

"""
This protocol is a follow-up to the CFPS protocol. It takes the completed reaction plate
and internal standards plate to assemble an assay plate with reagents and samples.
The reaction plate contains samples starting from column 1, with columns calculated
from combinations plus one extra column. Internal standards can be overlaid onto
the extra column. Uses 8-channel operations for efficiency (reagents and assay standards). 
The p1000 is used in SINGLE mode for removing extra content from the extra column.
"""

# Protocol Configuration
config = {
    # From previous protocol - needed for column calculations
    'combinations': [[2,18],[3,19],[4,20],[5,21]], # 1-indexed source well numbers (kept for total calculation)
    
    # Reaction plate layout settings
    'reaction_plate_first_column': 1,  # 1-indexed column where samples start on reaction plate
    'reaction_plate_has_extra_column': True,  # Reaction plate has one extra column beyond calculated combinations
    
    # Internal standards overlay settings
    'internal_standards_source_column': 2,  # 1-indexed column in internal standards plate to use for overlay
    'overlay_extra_column': True,  # Whether to overlay internal standards onto the extra column
    'cell_free_standards': [1,2,3,4,5],  # 1-indexed row positions where existing standards are in the extra column
    'garbage_well': 12,  # 1-indexed well position in deep-well plate for waste disposal
    
    # Assay assembly settings
    'assay_reagent_volume': 180,  # µL of assay reagent to add to each well
    'sample_transfer_volume': 20,  # µL of sample from reaction plate to assay plate
    'internal_standards_transfer_volume': 20,  # µL of internal standards to overlay
    
    # Mixing settings
    'mixing_repetitions': 5,      # Number of mix cycles after sample addition
    'mixing_volume': 50,          # Volume for mixing (appropriate for ~200µL total)
    
    # Deep-well plate contents
    'water_well': 1,              # 1-indexed well position for water in deep-well plate
    'assay_reagent_well': 3,      # 1-indexed well position for assay reagent in deep-well plate
    
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


def calculate_reaction_plate_layout(config):
    """
    Calculate the layout of the reaction plate based on combinations and extra column
    
    Args:
        config: Configuration dictionary
        
    Returns:
        tuple: (total_combinations, columns_needed, extra_column_number)
    """
    total_combinations = calculate_total_combinations(config['combinations'])
    
    # Calculate how many full columns are needed for PCR products (8 wells per column)
    columns_needed = (total_combinations + 7) // 8  # Ceiling division
    
    # Extra column number (comes after the combination columns)
    extra_column_number = config['reaction_plate_first_column'] + columns_needed
    
    return total_combinations, columns_needed, extra_column_number


def determine_target_columns(config, columns_needed, extra_column_number):
    """
    Determine which columns need assay reagent based on reaction plate layout
    
    Args:
        config: Configuration dictionary
        columns_needed: Number of columns needed for combinations
        extra_column_number: 1-indexed column number for the extra column
        
    Returns:
        list: List of 1-indexed column numbers that need assay reagent
    """
    # Start from the first column and include all combination columns
    first_col = config['reaction_plate_first_column']
    combination_cols = list(range(first_col, first_col + columns_needed))
    
    # Add the extra column if it exists
    all_target_cols = combination_cols.copy()
    if config['reaction_plate_has_extra_column']:
        all_target_cols.append(extra_column_number)
    
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


def transfer_samples_and_mix(protocol, reaction_plate, assay_plate, pipette, config, target_columns, columns_needed, extra_column_number):
    """
    Transfer samples from reaction plate to assay plate and mix
    
    Args:
        protocol: Opentrons protocol object
        reaction_plate: Source reaction plate with CFPS products
        assay_plate: Target assay plate with reagent
        pipette: Pipette instrument (8-channel mode)
        config: Configuration dictionary
        target_columns: List of 1-indexed column numbers to transfer to
        columns_needed: Number of columns needed for combinations
        extra_column_number: 1-indexed column number for the extra column
    """
    
    sample_volume = config['sample_transfer_volume']
    mixing_reps = config['mixing_repetitions']
    mixing_vol = config['mixing_volume']
    first_col = config['reaction_plate_first_column']
    
    protocol.comment("\n=== Transferring Samples and Mixing ===")
    protocol.comment(f"Sample volume: {sample_volume}µL per well")
    protocol.comment(f"Mixing: {mixing_reps} repetitions with {mixing_vol}µL")
    protocol.comment(f"Reaction plate layout: columns {first_col}-{first_col + columns_needed - 1} (combinations) + column {extra_column_number} (extra)")
    protocol.comment("Using 8-channel pipette for efficient column-wise operations")
    
    # Transfer from combination columns
    for i in range(columns_needed):
        col_num = first_col + i
        if col_num in target_columns:
            col_idx = col_num - 1  # Convert to 0-indexed
            
            source_column = reaction_plate.columns()[col_idx]
            dest_column = assay_plate.columns()[col_idx]
            
            protocol.comment(f"Transferring {sample_volume}µL from reaction column {col_num} (combination) to assay column {col_num} (8-channel)")
            
            # Transfer and mix in one operation
            pipette.transfer(
                sample_volume,
                source_column[0],  # A row (represents entire column for 8-channel)
                dest_column[0],   # A row (represents entire column for 8-channel)
                mix_after=(mixing_reps, mixing_vol),
                new_tip='always'
            )
    
    # Transfer from extra column (if it exists and is in target columns)
    if config['reaction_plate_has_extra_column'] and extra_column_number in target_columns:
        extra_col_idx = extra_column_number - 1  # Convert to 0-indexed
        
        source_column = reaction_plate.columns()[extra_col_idx]
        dest_column = assay_plate.columns()[extra_col_idx]
        
        protocol.comment(f"Transferring {sample_volume}µL from reaction column {extra_column_number} (extra) to assay column {extra_column_number} (8-channel)")
        
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


def remove_unwanted_content_from_extra_column(protocol, assay_plate, deep_well_plate, pipette, config, extra_column_number):
    """
    Remove content from wells in the extra column that are not designated for cell-free standards
    
    Args:
        protocol: Opentrons protocol object
        assay_plate: Target assay plate with reagent and samples
        deep_well_plate: Deep-well plate with garbage well
        pipette: Single-channel pipette instrument (p200/p1000)
        config: Configuration dictionary
        extra_column_number: 1-indexed column number for the extra column
    """
    
    if not config['overlay_extra_column'] or not config['reaction_plate_has_extra_column']:
        protocol.comment("Removal step skipped - overlay or extra column disabled in config")
        return
    
    cell_free_rows = config['cell_free_standards']
    garbage_well_idx = config['garbage_well'] - 1  # Convert to 0-indexed
    
    protocol.comment("\n=== Removing Unwanted Content from Extra Column ===")
    protocol.comment(f"Extra column: {extra_column_number}")
    protocol.comment(f"Cell-free standards rows (to keep): {cell_free_rows}")
    protocol.comment(f"Garbage disposal: Deep-well plate well {config['garbage_well']}")
    protocol.comment("Using single-channel mode for precise well removal")
    
    # Calculate which rows need to be removed (all rows except cell-free standards)
    all_rows = list(range(1, 9))  # Rows 1-8 (1-indexed)
    rows_to_remove = [row for row in all_rows if row not in cell_free_rows]
    
    if not rows_to_remove:
        protocol.comment("No wells need to be removed - all wells contain cell-free standards")
        return
    
    protocol.comment(f"Rows to remove content from: {rows_to_remove}")
    
    # Get the garbage disposal well
    garbage_well = deep_well_plate.wells()[garbage_well_idx]
    
    # Remove content from unwanted wells
    extra_col_idx = extra_column_number - 1  # Convert to 0-indexed
    
    for row_num in rows_to_remove:
        row_idx = row_num - 1  # Convert to 0-indexed
        well_to_clear = assay_plate.wells()[extra_col_idx * 8 + row_idx]  # Calculate well index
        well_name = well_to_clear.display_name
        
        protocol.comment(f"Removing content from {well_name} (row {row_num}, column {extra_column_number})")
        
        # Pick up tip and aspirate all content
        pipette.pick_up_tip()
        
        # Aspirate the content (estimate ~200µL total volume from reagent + sample)
        aspirate_volume = config['assay_reagent_volume'] + config['sample_transfer_volume']
        
        pipette.aspirate(aspirate_volume, well_to_clear)
        
        # Dispose to garbage well
        pipette.dispense(aspirate_volume, garbage_well)
        
        pipette.drop_tip()
    
    protocol.comment("=== Content Removal Complete ===\n")
    protocol.comment(f"Removed content from {len(rows_to_remove)} wells in column {extra_column_number}")
    protocol.comment("Wells are now ready for internal standards overlay")


def overlay_internal_standards(protocol, internal_standards_plate, assay_plate, pipette, config, extra_column_number):
    """
    Overlay internal standards from internal standards plate onto specific wells in the extra column in assay plate
    
    Args:
        protocol: Opentrons protocol object
        internal_standards_plate: Source plate with internal standards
        assay_plate: Target assay plate (already has reagent and samples, with unwanted content removed)
        pipette: Pipette instrument (8-channel mode)
        config: Configuration dictionary
        extra_column_number: 1-indexed column number for the extra column to overlay
    """
    
    if not config['overlay_extra_column']:
        protocol.comment("Internal standards overlay is disabled in config")
        return
    
    standards_volume = config['internal_standards_transfer_volume']
    mixing_reps = config['mixing_repetitions']
    mixing_vol = config['mixing_volume']
    source_col = config['internal_standards_source_column']
    cell_free_rows = config['cell_free_standards']
    
    protocol.comment("\n=== Overlaying Internal Standards ===")
    protocol.comment(f"Standards volume: {standards_volume}µL per well")
    protocol.comment(f"Source: Internal standards plate column {source_col}")
    protocol.comment(f"Target: Assay plate column {extra_column_number}")
    protocol.comment(f"Target rows (cell-free standards): {cell_free_rows}")
    protocol.comment(f"Mixing after overlay: {mixing_reps} repetitions with {mixing_vol}µL")
    protocol.comment("Using 8-channel pipette for efficient column-wise overlay")
    protocol.comment("Note: Only wells with cell-free standards will receive meaningful overlay")
    
    # Source column from internal standards plate
    source_col_idx = source_col - 1  # Convert to 0-indexed
    source_column = internal_standards_plate.columns()[source_col_idx]
    
    # Destination column in assay plate (extra column)
    dest_col_idx = extra_column_number - 1  # Convert to 0-indexed
    dest_column = assay_plate.columns()[dest_col_idx]
    
    protocol.comment(f"Overlaying {standards_volume}µL from internal standards column {source_col} to assay column {extra_column_number} (8-channel)")
    protocol.comment("Wells without cell-free standards have been cleared and will receive fresh internal standards")
    
    # Transfer and mix to combine with existing samples (or add to cleared wells)
    pipette.transfer(
        standards_volume,
        source_column[0],  # A row (represents entire column for 8-channel)
        dest_column[0],   # A row (represents entire column for 8-channel)
        mix_after=(mixing_reps, mixing_vol),
        new_tip='always'
    )
    
    protocol.comment("=== Internal Standards Overlay Complete ===\n")
    protocol.comment(f"Overlaid internal standards onto column {extra_column_number}")
    protocol.comment(f"Rows {cell_free_rows}: Combined with existing cell-free standards")
    
    # Calculate which rows were cleared and now have only internal standards
    all_rows = list(range(1, 9))
    cleared_rows = [row for row in all_rows if row not in cell_free_rows]
    if cleared_rows:
        protocol.comment(f"Rows {cleared_rows}: Fresh internal standards only (previous content removed)")


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
    
    # Configure pipettes for 8-channel operation initially
    p50.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_50])
    p200.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_200])
    
    # Calculate reaction plate layout
    total_combinations, columns_needed, extra_column_number = calculate_reaction_plate_layout(config)
    protocol.comment(f"=== Reaction Plate Layout ===")
    protocol.comment(f"Total combinations: {total_combinations}")
    protocol.comment(f"Columns needed for combinations: {columns_needed}")
    protocol.comment(f"First column: {config['reaction_plate_first_column']}")
    protocol.comment(f"Combination columns: {config['reaction_plate_first_column']}-{config['reaction_plate_first_column'] + columns_needed - 1}")
    if config['reaction_plate_has_extra_column']:
        protocol.comment(f"Extra column: {extra_column_number}")
    
    # Determine which columns need assay reagent
    target_columns = determine_target_columns(config, columns_needed, extra_column_number)
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
        columns_needed=columns_needed,
        extra_column_number=extra_column_number
    )
    
    # Step 3: Remove unwanted content from extra column before overlay
    # will this work (switching between 8-channel and single-channel modes)?
    if config['overlay_extra_column'] and config['reaction_plate_has_extra_column']:
        protocol.comment("=== Step 3: Removing Unwanted Content from Extra Column ===")
        # Switch p200 to single-channel mode for precise removal
        p200.configure_nozzle_layout(style='SINGLE', start='A1', tip_racks=[tiprack_200])
        
        remove_unwanted_content_from_extra_column(
            protocol=protocol,
            assay_plate=assay_plate,
            deep_well_plate=deep_well_plate,
            pipette=p200,  # Use p200 in single-channel mode for removal
            config=config,
            extra_column_number=extra_column_number
        )
        
        # Switch p50 back to 8-channel mode for overlay
        p50.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_50])
    
    # Step 4: Overlay internal standards onto extra column (if enabled)
    if config['overlay_extra_column'] and config['reaction_plate_has_extra_column']:
        protocol.comment("=== Step 4: Overlaying Internal Standards ===")
        overlay_internal_standards(
            protocol=protocol,
            internal_standards_plate=internal_standards_plate,
            assay_plate=assay_plate,
            pipette=p50,  # Use p50 in 8-channel mode for overlay
            config=config,
            extra_column_number=extra_column_number
        )
    
    # Step 5: Move assay plate to staging area
    protocol.comment("=== Step 5: Moving Assay Plate to Staging Area ===")
    protocol.comment(f"Moving assay plate from {config['assay_plate_position']} to staging position {config['staging_position']}")
    protocol.move_labware(
        labware=assay_plate,
        new_location=config['staging_position'],
        use_gripper=True
    )
    
    protocol.comment("=== Assay Assembly Protocol Complete ===")
    protocol.comment(f"Assay reagent volume per well: {config['assay_reagent_volume']}µL")
    protocol.comment(f"Sample transfer volume per well: {config['sample_transfer_volume']}µL")
    if config['overlay_extra_column']:
        protocol.comment(f"Internal standards overlay volume per well: {config['internal_standards_transfer_volume']}µL")
        protocol.comment(f"Cell-free standards preserved in rows: {config['cell_free_standards']}")
        protocol.comment(f"Final volume per well (combination columns): ~{config['assay_reagent_volume'] + config['sample_transfer_volume']}µL")
        
        # Calculate final volumes for extra column
        all_rows = list(range(1, 9))
        cleared_rows = [row for row in all_rows if row not in config['cell_free_standards']]
        
        protocol.comment(f"Final volume per well (extra column, rows {config['cell_free_standards']}): ~{config['assay_reagent_volume'] + config['sample_transfer_volume'] + config['internal_standards_transfer_volume']}µL")
        if cleared_rows:
            protocol.comment(f"Final volume per well (extra column, rows {cleared_rows}): ~{config['assay_reagent_volume'] + config['internal_standards_transfer_volume']}µL")
    else:
        protocol.comment(f"Final volume per well: ~{config['assay_reagent_volume'] + config['sample_transfer_volume']}µL")
    protocol.comment(f"Columns processed: {target_columns}")
    protocol.comment(f"Combination columns: {config['reaction_plate_first_column']}-{config['reaction_plate_first_column'] + columns_needed - 1}")
    if config['reaction_plate_has_extra_column']:
        protocol.comment(f"Extra column: {extra_column_number}")
    protocol.comment(f"Assay plate staged at: {config['staging_position']}")
    protocol.comment(f"Reaction plate remains on temperature module at {config['temperature']}°C")