"""
Simple Opentrons Protocol for Testing

A basic protocol that demonstrates common operations.
"""

metadata = {
    "protocolName": "Simple Test Protocol",
    "author": "Test Author",
    "description": "A simple protocol for testing translation",
    "apiLevel": "2.19",
}

requirements = {
    "robotType": "OT-3 Standard",
}


def run(protocol):
    # Load labware
    tip_rack = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul", "A1"
    )
    plate = protocol.load_labware(
        "nest_96_wellplate_200ul_flat", "A2", label="Sample Plate"
    )
    reservoir = protocol.load_labware(
        "nest_12_reservoir_15ml", "A3"
    )

    # Load pipette
    pipette = protocol.load_instrument(
        "flex_1channel_1000",
        "left",
        tip_racks=[tip_rack],
    )

    # Load trash
    trash = protocol.load_trash_bin("A4")

    # Simple liquid transfer
    protocol.comment("Starting simple transfer")

    pipette.pick_up_tip()
    pipette.aspirate(100, reservoir["A1"])
    pipette.dispense(100, plate["A1"])
    pipette.drop_tip()

    # Multi-well transfer
    protocol.comment("Multi-well transfer")

    for well in ["A2", "A3", "A4"]:
        pipette.pick_up_tip()
        pipette.aspirate(50, reservoir["A1"])
        pipette.dispense(50, plate[well])
        pipette.blow_out()
        pipette.drop_tip()

    protocol.comment("Protocol complete")
