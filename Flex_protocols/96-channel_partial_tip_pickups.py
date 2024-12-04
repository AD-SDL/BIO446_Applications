from opentrons import protocol_api

# Import the tip layout constants (ROW is another option)
from opentrons.protocol_api import SINGLE, COLUMN, ALL

requirements = {"robotType": "Flex", "apiLevel": "2.20"}


def run(protocol: protocol_api.ProtocolContext):

# Consider tip rack placement when asking 96 channel to use single col or row    
    p1000_tips = protocol.load_labware(
        load_name="opentrons_flex_96_tiprack_1000ul",
        location="B2"
    )
    trash = protocol.load_trash_bin("A1")

    pipette = protocol.load_instrument("flex_96channel_1000")

    # Configure nozzle layout for column pickup
    pipette.configure_nozzle_layout(
        style=COLUMN,
        start="A12",             # Use the rightmost column of nozzles
        tip_racks=[p1000_tips]
    )

    pipette.pick_up_tip()  # picks up A1-H1 from tip rack
    pipette.drop_tip()
    pipette.pick_up_tip()  # picks up A2-H2 from tip rack


    pipette.configure_nozzle_layout(
        style=single,
        start="A12",             # Use A12 position to pick up tips
        tip_racks=[p1000_tips]
    )

    pipette.pick_up_tip()  # picks up A3 from tip rack
    pipette.drop_tip()
    pipette.pick_up_tip()  # picks up B3 from tip rack