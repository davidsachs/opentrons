"""
Test protocol for gripper movement - Using low-level gripper control.

This protocol:
1. Homes the machine
2. Moves gripper above labware WITHOUT picking it up
3. Picks up labware with gripper
4. Moves labware to new location
5. Finishes
"""

from opentrons import types

metadata = {
    "protocolName": "Gripper Movement Test",
    "author": "Test",
    "description": "Test gantry movement and gripper control",
    "apiLevel": "2.22",
}

requirements = {
    "robotType": "OT-3",
}


def run(protocol):
    # Home the robot
    protocol.home()

    # Load a labware to have a target for gripper operations
    plate = protocol.load_labware(
        "nest_96_wellplate_200ul_flat",
        "C2"
    )

    # Helper function to get labware center location at a specific height
    def labware_center_location(labware_slot, z_height):
        """Calculate the center location for a given labware"""
        slot_center = protocol.deck.get_slot_center(labware_slot)
        return types.Location(
            point=types.Point(x=slot_center.x, y=slot_center.y, z=z_height),
            labware=None
        )

    protocol.comment("Moving gripper above labware at C2")
    # Move gripper to position above C2 at 50mm height (without gripping)
    position_above_c2 = labware_center_location("C2", 50)
    protocol.robot.move_to(mount='gripper', destination=position_above_c2)

    protocol.comment("Picking up labware at C2 and moving to C3")
    # Now use standard move_labware to pick up and move the plate
    protocol.move_labware(
        labware=plate,
        new_location="C3",
        use_gripper=True
    )

    # Move it back
    # This opens and closes the gripper
    protocol.comment("Moving labware back (opening and closing gripper)")
    protocol.move_labware(
        labware=plate,
        new_location="C2",
        use_gripper=True
    )

    protocol.comment("Protocol complete")
