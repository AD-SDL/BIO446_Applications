from opentrons import protocol_api
import itertools

metadata = {
    'protocolName': 'Protein Design CFPE and Assay',
    'author': 'LDRD team <gbabnigg@anl.gov>',
    'description': 'Golden Gate Assembly for Protein Design',
    'apiLevel': '2.20',
    'requirements': {"robotType": "Flex", "apiLevel": "2.20"},
    'source': 'FlexGB/pd_golden_gate_01.py'  
}


# defining the combination
combinations = [[1,9,17],[2],[3,11],[4]]

def calculate_total_combinations(combinations):
    """Calculate total number of combinations without generating them"""
    total = 1
    for sublist in combinations:
        total *= len(sublist)
    return total

def generate_all_combinations(combinations):
    """Generate all possible combinations from the jagged array"""
    return list(itertools.product(*combinations))

def transfer_combinatorial_liquids(protocol, source_plate, dest_plate, pipette, combinations, transfer_volume=10):
    """
    Transfer liquids based on combinatorial mixing pattern
    
    Args:
        protocol: Opentrons protocol object
        source_plate: Source PCR plate labware
        dest_plate: Destination PCR plate labware  
        pipette: Pipette instrument
        combinations: 2D jagged array defining source well combinations
        transfer_volume: Volume to transfer from each source well (µL)
    """
    
    # Calculate total combinations before generating them
    total_combinations = calculate_total_combinations(combinations)
    print(f"Total destination wells needed: {total_combinations}")
    
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
        
        print(f"\nTransferring to destination well {dest_well_number}:")
        
        for source_well_number in combination:
            source_well = source_plate.wells()[source_well_number - 1]  # Convert to 0-based index
            
            print(f"  - Transferring {transfer_volume}µL from source well {source_well_number} to dest well {dest_well_number}")
            
            # Perform the transfer
            pipette.transfer(
                transfer_volume,
                source_well,
                dest_well,
                new_tip='once'  # Use same tip for all transfers to same destination
            )
        
        dest_well_number += 1

# Example usage in your protocol:
def run(protocol):
    # Load labware
    source_plate = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'B4')
    dest_plate = protocol.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 'C1')
    
    # Load tip rack
    tip_rack = protocol.load_labware('opentrons_96_tiprack_20ul', 'A1')
    
    # Load pipette
    pipette = protocol.load_instrument('p20_single_gen2', 'left', tip_racks=[tip_rack])
    
    # Your combinations
    combinations = [[1,9,17],[2],[3,11],[4]]
    
    # Perform transfers
    transfer_combinatorial_liquids(
        protocol=protocol,
        source_plate=source_plate, 
        dest_plate=dest_plate,
        pipette=pipette,
        combinations=combinations,
        transfer_volume=5  # 5µL from each source well
    )

# Preview what will be transferred using the combinations defined above:
# Calculate total combinations
total_combos = calculate_total_combinations(combinations)
print(f"Calculation: {len(combinations[0])} × {len(combinations[1])} × {len(combinations[2])} × {len(combinations[3])} = {total_combos}")

all_combos = generate_all_combinations(combinations)

print("\nCombination preview:")
print(f"Total combinations to create: {len(all_combos)}")
for i, combo in enumerate(all_combos):
    print(f"Dest well {i+1}: Mix from source wells {combo}")