from opentrons import protocol_api
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Spheroid Deposition Movement Test',
    'author': 'OpentronsAI',
    'description': 'Testing single tip pickup and movement to tube rack and well plate',
    'source': 'OpentronsAI'
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

def run(protocol: protocol_api.ProtocolContext):
    # Load trash bin
    trash = protocol.load_trash_bin('A3')
    
    # Load labware
    tiprack_1000 = protocol.load_labware('opentrons_flex_96_filtertiprack_1000ul', 'A1')
    well_plate_1 = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="B1",
        namespace="opentrons",
        version=4,
        #lid="corning_96_wellplate_360ul_lid",
        #lid_namespace="opentrons",
        #lid_version=1,
    )
    #Place holder, we'll move the pipette into the chip manually
    chip = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="C3",
        namespace="opentrons",
        version=4,
        #lid="corning_96_wellplate_360ul_lid",
        #lid_namespace="opentrons",
        #lid_version=1,
    )
    
    #tube_rack = protocol.load_labware('opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap', 'B1')
    #well_plate = protocol.load_labware('biorad_384_wellplate_50ul', 'C3')
    #tiprack_1000.set_offset(x=0.0, y=0.0, z=0.0)
    #tube_rack.set_offset(x=0.0, y=0.0, z=0.0)
    #well_plate.set_offset(x=0.0, y=0.0, z=0.0)



    # Load pipette
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right')
    p50_multi = protocol.load_instrument('flex_8channel_1000', 'left')
    default_rate = 700#uL/S
    p1000_multi.flow_rate.aspirate = default_rate
    p1000_multi.flow_rate.dispense = default_rate
    # Configure for single tip pickup using overhang (SINGLE nozzle configuration)
    # Using A1 (front nozzle) for better deck access
    p1000_multi.configure_nozzle_layout(
        style=SINGLE,
        start='A1',
        tip_racks=[tiprack_1000]
    )
    
    # Protocol steps
    # Step 1: Pick up a single tip
    p1000_multi.pick_up_tip()
    
    # Step 2: Move to the first tube in the tube rack (A1)

    p1000_multi.move_to(tube_rack['A1'].top())
    #protocol.comment("Pause.")
    # Step 3: Move to the first well in the well plate (A1)
    p1000_multi.move_to(chip['A1'].top())
    protocol.comment("Pause.")
    # Step 4: Drop the tip in the trash (return_tip() not supported with partial tip configuration)
    p1000_multi.drop_tip()