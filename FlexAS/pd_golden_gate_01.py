from opentrons import protocol_api
import itertools
from opentrons.protocol_api import SINGLE


metadata = {
    'protocolName': 'Protein Design CFPE and Assay with Reagent Mixing',
    'author': 'LDRD team ',
    'description': 'Golden Gate Assembly for Protein Design with Reagent Preparation',
    'apiLevel': '2.20',
    'requirements': {"robotType": "Flex", "apiLevel": "2.20"},
    'source': 'FlexGB/pd_golden_gate_modified.py'  
}


# Protocol Configuration
config = {
    # PCR product settings (no dilution needed)
    'combinations': [[2,18],[3,19],[4,20],[5,21]], # 1-indexed source well numbers (kept for total calculation)
    
    # Incubation settings
    'heater_shaker_temp': 37,     # °C for heater/shaker
    'pause_duration': 5,          # minutes for pause after reaction assembly (PF400 to sealer and back)
    'shaking_duration': 180,      # minutes (3 hours) for shaking
    'shaking_speed': 100,         # rpm for shaking
    
    # Master mix settings
    'master_mix_volume': 12,  # µL per destination well
    'master_mix_well_volume': 100,  # µL per master mix well; should be less than 9*12 /// new entry
    'master_mix_start_well': 33,  # 1-indexed well number
    
    # Reagent mixing settings (using 8-channel pipette)
    'reagent_mix_A_column': 5,    # Column number for mix A (1-indexed)
    'reagent_mix_B_column': 7,    # Column number for mix B (1-indexed)
    'reagent_mixing_column': 8,   # Column number for mixing reagents (1-indexed)
    'reagent_mix_A_volume': 100,  # µL from mix A column to mixing column
    'reagent_mix_B_volume': 50,   # µL from mix B column to mixing column
    'final_reagent_volume': 50,   # µL from mixing column to template columns
    'mixing_repetitions': 5,      # Number of mix cycles
    'mixing_volume': 75,          # Volume for mixing (appropriate for ~150µL total)
    
    # Template column settings
    'template_columns': [1, 2, 3],  # List of column numbers with templates (1-indexed)
    
    # Temperature settings
    'temperature': 4,  # °C
    
    # Labware
    'source_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt',  # Diluted PCR products
    'reaction_plate_type': 'nest_96_wellplate_100ul_pcr_full_skirt', # Reagent plate for reactions
    'pcr_adapter_type': 'opentrons_96_pcr_adapter',  # Aluminum adapter for PCR plates
    'tip_rack_type_50_01': 'opentrons_flex_96_tiprack_50ul',
    'pipette_type_50': 'flex_8channel_50',
    'tip_rack_type_200_01': 'opentrons_flex_96_tiprack_200ul',
    'pipette_type_1000': 'flex_8channel_1000',
    
    # Deck positions
    'temp_module_position': 'C1',          # Temperature module for reaction assembly
    'shaker_module_position': 'D1',        # Heater/shaker module for incubation
    'source_plate_position': 'B2',         # Diluted PCR products plate
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
    master_mix_start_well = config['master_mix_start_well'] - 1  # Convert to 0-indexed
    
    # Calculate total combinations
    total_combinations = calculate_total_combinations(combinations)
    
    # Calculate how many destination wells can be served by one master mix well
    dispenses_per_well = master_mix_well_volume // master_mix_volume
    
    # Calculate how many master mix wells we need
    master_mix_wells_needed = (total_combinations + dispenses_per_well - 1) // dispenses_per_well  # Ceiling division
    
    # Track current master mix well and remaining volume
    current_master_mix_well = master_mix_start_well
    remaining_dispenses = dispenses_per_well
    
    for dest_well_number in range(1, total_combinations + 1):
        # Check if we need to switch to next master mix well
        if remaining_dispenses == 0:
            current_master_mix_well += 1
            remaining_dispenses = dispenses_per_well
            protocol.comment(f"  Switching to master mix well {current_master_mix_well + 1} (1-indexed)")
        
        # Get the destination well
        dest_well = dest_plate.wells()[dest_well_number - 1]  # Convert to 0-based index
        
        # Get the current master mix well
        master_mix_well = source_plate.wells()[current_master_mix_well]
        
        protocol.comment(f"  Dest well {dest_well_number}: Adding {master_mix_volume}µL from master mix well {current_master_mix_well + 1} (1-indexed)")
        
        # Transfer master mix
        pipette.transfer(
            master_mix_volume,
            master_mix_well,
            dest_well,
            new_tip='always'  # Use fresh tip for each master mix transfer
        )
        
        # Update remaining dispenses
        remaining_dispenses -= 1

    protocol.comment(f"\nMaster mix addition complete. Used wells {master_mix_start_well + 1} to {current_master_mix_well + 1} (1-indexed)")

    return current_master_mix_well  # Return the last used well

def prepare_reagent_mix(protocol, reaction_plate, pipette, config):
    """
    Prepare reagent mix by combining reagents from specified columns into mixing column,
    then distribute to template columns using 8-channel pipette
    
    Args:
        protocol: Opentrons protocol object
        reaction_plate: Reaction plate labware (mix A and mix B)
        pipette: 8-channel pipette instrument
        config: Configuration dictionary containing reagent mixing settings
    """
    
    # Get settings from config
    mix_A_col = config['reagent_mix_A_column'] - 1  # Convert to 0-indexed
    mix_B_col = config['reagent_mix_B_column'] - 1  # Convert to 0-indexed
    mixing_col = config['reagent_mixing_column'] - 1  # Convert to 0-indexed
    template_cols = [col - 1 for col in config['template_columns']]  # Convert to 0-indexed
    
    reagent_mix_A_volume = config['reagent_mix_A_volume']
    reagent_mix_B_volume = config['reagent_mix_B_volume']
    final_reagent_volume = config['final_reagent_volume']
    mixing_repetitions = config['mixing_repetitions']
    mixing_volume = config['mixing_volume']
    
    protocol.comment("\n=== Starting Reagent Preparation ===")
    protocol.comment(f"Mix A source: Column {config['reagent_mix_A_column']}")
    protocol.comment(f"Mix B source: Column {config['reagent_mix_B_column']}")
    protocol.comment(f"Mixing column: Column {config['reagent_mixing_column']}")
    protocol.comment(f"Template columns: {config['template_columns']}")
    
    # Define column wells for 8-channel operations
    mix_A_column = reaction_plate.columns()[mix_A_col]
    mix_B_column = reaction_plate.columns()[mix_B_col]
    mixing_column = reaction_plate.columns()[mixing_col]
    
    # Step 1: Transfer mix A to mixing column (8-channel operation)
    protocol.comment(f"Transferring {reagent_mix_A_volume}µL from column {config['reagent_mix_A_column']} to column {config['reagent_mixing_column']} (8-channel)")
    pipette.transfer(
        reagent_mix_A_volume,
        mix_A_column[0],  # A row (represents entire column for 8-channel)
        mixing_column[0],  # A row (represents entire column for 8-channel)
        new_tip='always'
    )
    
    # Step 2: Transfer mix B to mixing column (8-channel operation)
    protocol.comment(f"Transferring {reagent_mix_B_volume}µL from column {config['reagent_mix_B_column']} to column {config['reagent_mixing_column']} (8-channel)")
    pipette.transfer(
        reagent_mix_B_volume,
        mix_B_column[0],  # A row (represents entire column for 8-channel)
        mixing_column[0],  # A row (represents entire column for 8-channel)
        new_tip='always'
    )
    
    # Step 3: Mix contents in mixing column (8-channel operation)
    protocol.comment(f"Mixing contents in column {config['reagent_mixing_column']} ({mixing_repetitions} repetitions with {mixing_volume}µL, 8-channel)")
    pipette.pick_up_tip()
    pipette.mix(
        repetitions=mixing_repetitions,
        volume=mixing_volume,
        location=mixing_column[0]  # A row (represents entire column for 8-channel)
    )
    pipette.drop_tip()
    
    # Step 4: Distribute mixed reagents to template columns (8-channel operations)
    for template_col_idx in template_cols:
        template_column = reaction_plate.columns()[template_col_idx]
        template_col_num = template_col_idx + 1  # Convert back to 1-indexed for display
        
        protocol.comment(f"Transferring {final_reagent_volume}µL from column {config['reagent_mixing_column']} to column {template_col_num} (8-channel)")
        pipette.transfer(
            final_reagent_volume,
            mixing_column[0],  # A row (represents entire column for 8-channel)
            template_column[0],  # A row (represents entire column for 8-channel)
            new_tip='always'
        )
    
    protocol.comment("=== Reagent Preparation Complete ===\n")
    protocol.comment(f"Reagents distributed to {len(config['template_columns'])} template columns using 8-channel operations")


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

    # Configure 8-channel mode for reagent handling
    p50.configure_nozzle_layout(style='COLUMN', start='A1', tip_racks=[tiprack_50])
    
    # Prepare reagent mix on temperature module (C1)
    protocol.comment("=== Reaction Assembly on Temperature Module ===")
    prepare_reagent_mix(
        protocol=protocol,
        reaction_plate=reaction_plate,
        pipette=p50,
        config=config
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

    protocol.comment("=== Protocol Complete ===")
    protocol.comment(f"Diluted PCR products were on plate at {config['source_plate_position']}")
    protocol.comment(f"Reaction assembly completed on temperature module at {config['temperature']}°C")
    protocol.comment(f"Incubation completed: {config['shaking_duration']} minutes at {config['heater_shaker_temp']}°C with {config['shaking_speed']} rpm shaking")
    protocol.comment(f"Final reaction plate is staged at {config['reaction_plate_initial_position']}")


# Preview what will be transferred using the combinations defined above:
total_combos = calculate_total_combinations(config['combinations'])
all_combos = generate_all_combinations(config['combinations'])