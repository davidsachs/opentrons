from opentrons import protocol_api, types
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Washing out hydrogel (microscope follows)',
    'author': 'David Sachs',
    'description': 'Washing out hydrogel - microscope tracks the active well in X/Y',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

# "Above chip" position (absolute coordinates) - fixed safe reference point
# This position is used for approach/retreat and never changes
ABOVE_CHIP_X = 400
ABOVE_CHIP_Y = 140
ABOVE_CHIP_Z = 50  # High enough to be safely above the chip

def run(protocol: protocol_api.ProtocolContext):
    # Load trash bin
    trash = protocol.load_trash_bin('A3')

    # Load labware
    tiprack_1000 = protocol.load_labware('opentrons_flex_96_filtertiprack_1000ul', 'B2')
    # Load pipettes (only using p1000)
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right')

    # Configure for single tip pickup using overhang (SINGLE nozzle configuration)
    p1000_multi.configure_nozzle_layout(
        style=SINGLE,
        start='H1',
        tip_racks=[tiprack_1000]
    )

    # Tube rack in B1
    tube_rack = protocol.load_labware(
        'opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap',
        'D2',
        label='Reagent Tubes'
    )
    # Define "above chip" location - fixed safe reference point for approach/retreat
    above_chip_point = types.Point(x=ABOVE_CHIP_X, y=ABOVE_CHIP_Y, z=ABOVE_CHIP_Z)
    above_chip_location = types.Location(point=above_chip_point, labware=None)

    # Pick up a single tip
    protocol.comment("Picking up tip...")
    p1000_multi.pick_up_tip()

    # Well movement pattern (relative, in mm)
    x_locs = [4.5, 0,    0,    -4.5, 0]
    y_locs = [0,   -4.5, -4.5, 0,    4.5]

    # Helper: move pipette relative to current position.
    # .position is only available at runtime (not during analysis/simulation),
    # so we catch AttributeError to let the protocol pass analysis.
    def move_relative(pip, point):
        if 1:#try:
            pip.move_to(above_chip_location)#pip.position.move(point))
        #except AttributeError:
        #    pass



    # Helper: move pipette to next well position (raise Z, move XY, lower Z)
    # and send matching XY movement to the microscope via SR command
    def move_to_next_well(i):
        """Move pipette and microscope to well position i (0-4)."""
        dx = x_locs[i]
        dy = y_locs[i]
        protocol.comment(f"SR X{dx} Y{dy}")
        protocol.comment("F0.5")
        protocol.comment("MR Z1")

        protocol.comment("F0")
        protocol.comment(f"MR Z4")
        protocol.comment(f"MR X{dx} Y{dy}")
        protocol.comment(f"MR Z-4")
        
        protocol.comment("F0.5")
        protocol.comment("MR Z-1")

        #move_relative(p1000_multi, types.Point(z=5))
        #move_relative(p1000_multi, types.Point(x=dx, y=dy))
        #move_relative(p1000_multi, types.Point(z=-5))

    
    # Return microscope to starting well position (undo cumulative movement)
    def return_microscope_to_start():
        """Send microscope back to the position of well 0.
        After visiting all 6 positions, the cumulative offset is (0, -4.5).
        So we need to move Y+4.5 to get back to start."""
        # Cumulative: pos0=(0,0), +x4.5, +y-4.5, +y-4.5, +x-4.5, +y4.5 = (0, -4.5)
        protocol.comment("SR Y4.5")
    def set_up_locations():
        protocol.comment("SET0")
        protocol.comment("F0.5")
        protocol.comment("MR Z1")
        protocol.comment("SET1")
        protocol.comment("F0")
        protocol.comment("MR Z4")
        protocol.comment("SET2")
    def move_to_chip():
        protocol.comment("Moving into chip...")
        protocol.comment("F0")
        protocol.comment("G1")
        protocol.comment("F0.5")
        protocol.comment("MR Z-1")
    
    def exit_chip():
        protocol.comment("F0.5")
        protocol.comment("MR Z1")
        protocol.comment("F0")
        protocol.comment("MR Z4")
        protocol.comment("MR Y4.5")
        return_microscope_to_start()
    # =========================================================================
    # INTERACTIVE LOOP
    # Click on a well in the UI to change source, press 'E' to exit
    # =========================================================================
    protocol.comment("CLEAR")
    protocol.comment("F0")
    protocol.comment("Moving above chip...")
    p1000_multi.move_to(above_chip_location)
    protocol.comment("LOOP_START")
    
    protocol.comment("Pause - Move to the top of the hole, touching the liquid")
    set_up_locations()

    # Aspirate 25 from each reservoir
    # Position 1: Start (upper left)
    aspirate_rate = 5
    dispense_rate = 10


    move_to_chip()

    protocol.comment("Aspirating at position 1...")
    p1000_multi.aspirate(25, flow_rate=aspirate_rate)
    # Positions 2-6: Move and aspirate
    for i in range(5):
        move_to_next_well(i)
        protocol.comment(f"Aspirating at position {i+2}...")
        p1000_multi.aspirate(25, flow_rate=aspirate_rate)

    # Return microscope to well 0 before leaving chip
    exit_chip()

    # Repeat wash cycle 3 times
    for wash_cycle in range(2):
        protocol.comment(f"=== Wash cycle {wash_cycle + 1} of 3 ===")

        # Blow out collected liquid
        p1000_multi.blow_out(tube_rack["A2"])

        # Collect 150 liquid
        p1000_multi.aspirate(160, tube_rack["A1"])

        # Move to "in chip" position (saved location 0)
        protocol.comment("Moving into chip...")
        move_to_chip()

        p1000_multi.dispense(25, flow_rate=dispense_rate)
        for i in range(5):
            move_to_next_well(i)
            protocol.comment(f"Dispensing at position {i+2}...")
            p1000_multi.dispense(25, flow_rate=dispense_rate)

        # Return microscope to well 0
        exit_chip()
        # Mixing
        mix_volume = 25

        move_to_chip()

        protocol.comment("Mixing at position 1...")
        for i in range(2):
            p1000_multi.aspirate(mix_volume, flow_rate=aspirate_rate)
            p1000_multi.dispense(mix_volume, flow_rate=dispense_rate)
        p1000_multi.aspirate(mix_volume, flow_rate=aspirate_rate)

        for i in range(5):
            move_to_next_well(i)
            protocol.comment(f"Mixing at position {i+2}...")
            for j in range(2):
                p1000_multi.aspirate(mix_volume, flow_rate=aspirate_rate)
                p1000_multi.dispense(mix_volume, flow_rate=dispense_rate)
            p1000_multi.aspirate(mix_volume, flow_rate=aspirate_rate)

        exit_chip()
        # Back to start of loop for blow out

    # Check if user wants to exit
    protocol.comment("Pause - E to exit, or do another washing")
    protocol.comment("CHECK_EXIT")
    protocol.comment("LOOP_END")

    # =========================================================================
    # EXIT POINT - reached when user presses 'E'
    # =========================================================================
    protocol.comment("EXIT_LOOP")
    protocol.comment("Exiting loop - dropping tip")

    # Blow out collected liquid
    p1000_multi.blow_out(tube_rack["A2"])

    # Step 4: Drop the tip in the trash
    p1000_multi.drop_tip()
