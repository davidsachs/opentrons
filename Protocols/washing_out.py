from opentrons import protocol_api, types
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Washing out hydrogel',
    'author': 'David Sachs',
    'description': 'Washing out hydrogel',
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
    #Place holder, we'll move the pipette into the chip manually
    chip = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="C3",
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
    
    # Protocol steps
    # Step 1: Pick up a single tip
    p1000_multi.pick_up_tip()
    
    # Step 2: Get the washing out media from the well plate
    p1000_multi.aspirate(100, well_plate_1["A1"])

    # Step 3: Move to the chip
    chip_point = types.Point(x=400, y=140, z=50)
    chip_location = types.Location(point=chip_point, labware=None)
    p1000_multi.move_to(chip_location)

    #p1000_multi.move_to(chip['A1'].top())
    #Pause to adjust location manually
    protocol.comment("Pause.")

    #Set the washing rate to 2ul/s
    washing_rate = 2

    #Dispense 50ul of washing out media
    p1000_multi.dispense(50, flow_rate=washing_rate)
    #Wash 3 times
    for i in range(3):
        p1000_multi.aspirate(25, flow_rate=washing_rate)
        p1000_multi.dispense(25, flow_rate=washing_rate)

    #Put whatever's left back in the well plate
    p1000_multi.blow_out(well_plate_1["A1"])

    # Step 4: Drop the tip in the trash
    p1000_multi.drop_tip()