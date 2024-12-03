from opentrons import protocol_api

# metadata
# This protocol will cherrypick sample from any well in a source plate
# and transfer to any well in a destination plate.
# This is followed by Golden Gate rxn set up and incubation
# Source well, destination well and volume info are provided in csv file
# Note that line 116 must be changed to trash=True before starting real experiment

metadata = {
    "protocolName": "Cherrypicking gene fragments PLUS Golden Gate assembly",
    "author": "rwilton@anl.gov",
    "description": "Implementation of Romero protocol on the Flex",
}

# requirements
requirements = {"robotType": "Flex", "apiLevel": "2.20"}

# Function to add parameters for CSV file (just the 3 columns)
# the variable name must match the protocol.params.attribute (below)
def add_parameters(parameters):
    parameters.add_csv_file(
        variable_name="cherrypicking_wells",
        display_name="Cherrypicking wells",
        description=(
            "Table: source_well, destination_well, volume"
        )
    )
    
# protocol run function
def run(protocol: protocol_api.ProtocolContext):

# Read the CSV file and store it as a list of rows (well_data) 
    well_data = protocol.params.cherrypicking_wells.parse_as_csv()

    # load tip rack in deck slot A2
    tip50 = protocol.load_labware(
        load_name="opentrons_flex_96_tiprack_50ul", location="A2"
    )
    
    # attach pipette to left mount
    pipette50 = protocol.load_instrument(
        instrument_name="flex_1channel_50",
        mount="left",
        tip_racks=[tip50]
    )

    # attach pipette to right mount
    pipette50_8ch = protocol.load_instrument(
        instrument_name="flex_8channel_50",
        mount="right",
        tip_racks=[tip50]
    ) 

    # load trash bin
    trash = protocol.load_trash_bin("A3")

    # Load source and destination plates manually (example: plates in slots A1 and B1)
    source_plate = protocol.load_labware(
        load_name="nest_96_wellplate_200ul_flat", location="C2"
    )
    destination_plate = protocol.load_labware(
        load_name="opentrons_96_wellplate_200ul_pcr_full_skirt", location="D2"
    )

    # load temperature modules and adapters
    temp_mod1 = protocol.load_module(
        module_name="temperature module gen2", location="C3"
    )
    temp_labware = temp_mod1.load_labware(
        name="opentrons_24_aluminumblock_nest_1.5ml_snapcap",
        label="Temperature-Controlled Tubes"
    )

    temp_mod2 = protocol.load_module(
        module_name="temperature module gen2", location="D3"
    )
    temp_labware = temp_mod2.load_labware(
        name="opentrons_96_aluminumblock_biorad_wellplate_200uL",
        label="Temperature-Controlled PCR plate"
    )

    # set temperature of temp modules
    # protocol will not resume until target temps are reached; first mod1, then mod2
    temp_mod1.set_temperature(celsius=24)
    temp_mod2.set_temperature(celsius=24)

    # pause to add Golden Gate master mix tube to 24 well block at 5C
    # manually resume in App when complete
    protocol.pause("Transfer Golden Gate master mix to chilled 24-well block")

    # Iterate through the well_data (CSV rows) to perform the transfers
    for row in well_data:
        source_well = row["source_well"]
        destination_well = row["destination_well"]
        transfer_volume = float(row["volume"])

    # Get the source and destination well locations from the plates
        source_location = source_plate[source_well]
        destination_location = destination_plate[destination_well]

    # Perform the transfer
    # trash=False will return tips to rack for practice
    # change to trash=True before starting actual experiment
        pipette50.transfer(
            volume=transfer_volume,
            source=source_location,
            dest=destination_location,
            trash=False
        )

    # turn off temperature modules
    temp_mod1.deactivate()
    temp_mod2.deactivate()  

    
