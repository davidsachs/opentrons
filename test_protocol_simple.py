"""
Simple working protocol for testing translation.
"""

metadata = {
    "protocolName": "Simple Test Protocol",
    "author": "Test",
    "description": "A simple protocol for testing",
    "apiLevel": "2.19",
}

requirements = {
    "robotType": "Flex",
}


def run(protocol):
    # Load trash
    trash = protocol.load_trash_bin("A3")

    # Load labware
    tiprack = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "B1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "B2")

    # Load pipette
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tiprack])

    # Simple protocol
    pipette.pick_up_tip()
    pipette.aspirate(100, plate["A1"])
    pipette.dispense(100, plate["B1"])
    pipette.drop_tip()
