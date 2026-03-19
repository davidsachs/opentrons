from opentrons import protocol_api, types
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Spheroid Deposition Movement Test',
    'author': 'David Sachs',
    'description': 'Seeding a spheroid into the chip',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

def run(protocol: protocol_api.ProtocolContext):
    # Load trash bin
    trash = protocol.load_trash_bin('A3')
    
    # Load labware
    tiprack_1000 = protocol.load_labware('opentrons_flex_96_filtertiprack_1000ul', 'B2')
    well_plate_1 = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="D3",
        namespace="opentrons",
        version=4,
    )
    # Load pipettes (only using p1000)
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right')

    # Configure for single tip pickup using overhang (SINGLE nozzle configuration)
    p1000_multi.configure_nozzle_layout(
        style=SINGLE,
        start='H1',
        tip_racks=[tiprack_1000]
    )
    set_location = {}
    #protocol.comment("Pause.")
    #550.6, 149.5, 70.5/39.5
    
    # Protocol steps
    # Step 1: Pick up a single tip
    p1000_multi.pick_up_tip()

    # Move to absolute coordinates for chip position
    chip_point = types.Point(x=400, y=140, z=50)
    chip_location = types.Location(point=chip_point, labware=None)
    p1000_multi.move_to(chip_location)
    protocol.comment("Pause.")

    # Step 2: Get the spheroid from the well plate
    # Do we need to pipette to dislodge the spheroid? How quickly should we pipette?
    # Aspirate a little
    unstick_rate = 10
    pickup_rate = 30
    p1000_multi.aspirate(30, well_plate_1["A1"],flow_rate=unstick_rate)
    # Dispense to dislodge the spheroid
    p1000_multi.dispense(20, flow_rate=unstick_rate)
    # Aspirate to pick up the spheroid
    p1000_multi.aspirate(100, flow_rate=pickup_rate)
    p1000_multi.move_to(chip_location)

    # Step 3: Move to the chip
    #chip_location = types.Location(point=set_location[0], labware=None)
    #protocol.robot.move_to(mount='right', destination=chip_location)
    #protocol.comment("Pause.")
    protocol.comment("G0")
    protocol.comment("Pause")
    # Until we know what to do here, manually lower the pipette into the chip, wait, then raise it back out

    # Step 4: Drop the tip in the trash (return_tip() not supported with partial tip configuration)
    p1000_multi.drop_tip()