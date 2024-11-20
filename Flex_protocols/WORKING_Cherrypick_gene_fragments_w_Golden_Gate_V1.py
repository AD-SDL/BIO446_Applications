from opentrons import protocol_api

# metadata
# This protocol will cherrypick sample from any well in source plate
# and transfer to any well in the destination plate
# This is followed by Golden Gate rxn set up and incubation
# Source, destination and volume info are provided in csv file
# Note that line 87 must be changed to trash=True before starting real experiment
metadata = {
    "protocolName": "Cherrypicking gene fragments PLUS Golden Gate assembly",
    "author": "rwilton@anl.gov",
    "description": "Implementation of Romero protocol on the Flex",
}

# requirements
requirements = {"robotType": "Flex", "apiLevel": "2.20"}

def add_parameters(parameters):
# the variable name must match the protocol.params.attribute (below)
    parameters.add_csv_file(
        variable_name="cherrypicking_wells",
        display_name="Cherrypicking wells",
        description=(
            "Table:"
            " source_slot, source_well,"
            " destination_slot, destination_well,"
            " volume"
        )
    )
    
# protocol run function
def run(protocol: protocol_api.ProtocolContext):
    well_data = protocol.params.cherrypicking_wells.parse_as_csv()
    source_slots = [row[0] for row in well_data][1::]
    unique_source_slots = list(set(source_slots))
    destination_slots = [row[2] for row in well_data][3::]
    unique_destination_slots = list(set(destination_slots))

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
    
    # load temperature modules and adapters
    temp_mod1 = protocol.load_module(
        module_name="temperature module gen2", location="C3"
    )
    temp_labware = temp_mod1.load_labware(
        name="opentrons_96_well_aluminum_block",
        label="Temperature-Controlled Tubes"
    )

    temp_mod2 = protocol.load_module(
        module_name="temperature module gen2", location="D3"
    )
    temp_labware = temp_mod2.load_labware(
        name="opentrons_24_aluminumblock_nest_1.5ml_snapcap",
        label="Temperature-Controlled PCR plate"
    )

    # set temperature of temp modules
    # protocol will not resume until target temp is reached
    temp_mod1.set_temperature(celsius=5)
    temp_mod2.set_temperature(celsius=5)

    # pause to add Golden Gate master mix tube to 24 well block at 5C
    # manually resume in App when complete
    protocol.pause("Transfer Golden Gate master mix to chilled 24-well block")

    # load destination plates based on CSV data
    for slot in unique_destination_slots:
        protocol.load_labware(
        load_name="opentrons_96_wellplate_200ul_pcr_full_skirt",
        location=slot
        )

    # load source plates based on CSV data
    for slot in unique_source_slots:
        protocol.load_labware(
        load_name="nest_96_wellplate_200ul_flat",
        location=slot
        )

    for index, row in enumerate(well_data[1::]):
    # get source location from CSV
        source_slot = row[0]
        source_well = row[1]
        source_location = protocol.deck[source_slot][source_well]

    # get volume as a number
        transfer_volume = float(row[4])

    # get destination location from CSV
        destination_slot = row[2]
        destination_well = row[3]
        destination_location = protocol.deck[destination_slot][destination_well]

    # perform parameterized transfer
    # trash=False will return tips to rack for practice
    # change to trash=True before starting actual experiment
        pipette50.transfer(
        volume=transfer_volume,
        source=source_location,
        dest=destination_location,
        trash=False
    )
        

