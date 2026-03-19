from opentrons import protocol_api, types

metadata = {
    "protocolName": "6-well plate lid and pickup test",
    "author": "David Sachs",
    "description": "Remove lid, pick up plate (no move), put plate back, replace lid",
}

requirements = {"robotType": "Flex", "apiLevel": "2.26"}

def run(protocol: protocol_api.ProtocolContext) -> None:
    # Load Labware - 6-well plate with lid in A1
    test_plate = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="A1",
        namespace="opentrons",
        version=4,
        lid="corning_96_wellplate_360ul_lid",
        lid_namespace="opentrons",
        lid_version=1,
    )

    # Load Trash Bin
    trash_bin = protocol.load_trash_bin("A3")

    # PROTOCOL STEPS

    # Step 1: Remove lid from plate in A1 and place it in A2
    protocol.comment("Step 1: Removing lid from A1 and placing in A2")
    protocol.move_lid(test_plate, "A2", use_gripper=True)

    # Step 2: Pick up the plate from A1, but don't carry it anywhere
    # We move it to A1 (same location) - this effectively picks it up and puts it back
    protocol.comment("Step 2: Picking up plate from A1")
    protocol.move_labware(test_plate, "B3", use_gripper=True)

    # Step 3: Put the plate back in A1
    protocol.comment("Step 3: Putting plate back in A1")
    protocol.move_labware(test_plate, "A1", use_gripper=True)

    # Step 4: Put the lid back on the plate
    protocol.comment("Step 4: Replacing lid on plate")
    protocol.move_lid("A2", test_plate, use_gripper=True)

    protocol.comment("Done!")
