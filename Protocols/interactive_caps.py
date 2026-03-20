from opentrons import protocol_api, types
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Filling (microscope follows)',
    'author': 'David Sachs',
    'description': 'Filling - microscope tracks the active well in X/Y',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

# "Above chip" position (absolute coordinates) - fixed safe reference point
# This position is used for approach/retreat and never changes
ABOVE_CHIP_X = 389.4
ABOVE_CHIP_Y = 161.7
ABOVE_CHIP_Z = 9  # High enough to be safely above the chip


def run(protocol: protocol_api.ProtocolContext):
    # Load trash bin
    trash = protocol.load_trash_bin('A3')

    # Load labware
    tiprack_1000 = protocol.load_labware('opentrons_flex_96_filtertiprack_50ul', 'B1')
    # Load pipettes (only using p1000)
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right')

    # Configure for single tip pickup using overhang (SINGLE nozzle configuration)
    p1000_multi.configure_nozzle_layout(
        style=SINGLE,
        start='H1',
        tip_racks=[tiprack_1000]
    )

    gel_plate = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="C2",
        namespace="opentrons",
        version=4,
        label="Spheroid Source Plate"
    )
    #z=54
    gel_plate.set_offset(x=-0.5, y=0.5, z=49.5)
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
    #def set_up_locations():
    #    protocol.comment("SET0")
    #    protocol.comment("F0.5")
    #    protocol.comment("MR Z1")
    #    protocol.comment("SET1")
    #    protocol.comment("F0")
    #    protocol.comment("MR Z4")
    #    protocol.comment("SET2")

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
    
    # Cumulative XY offsets of each well from well 0 (= SET0 origin)
    # Derived from x_locs/y_locs deltas used in move_to_next_well
    well_offsets = [
        (0,    0),     # well 0 — SET0 position
        (4.5,  0),     # well 1
        (4.5, -4.5),   # well 2
        (4.5, -9.0),   # well 3
        (0,   -9.0),   # well 4
        (0,   -4.5),   # well 5
    ]

    def return_to_well(i, move_microscope=True, corner=False):
        """Move pipette directly to well i using SET0 as origin.
        Microscope SR is a relative move from the previous well (i-1), which is where
        the microscope sits after the previous return_to_well call (or well 0 after exit_chip)."""
        # SR: relative delta from well i-1 to well i (= x_locs[i-1], y_locs[i-1])
        if move_microscope:
            if i > 0:
                rel_dx = x_locs[i - 1]
                rel_dy = y_locs[i - 1]
                protocol.comment(f"SR X{rel_dx} Y{rel_dy}")
        # Gantry: G0 + absolute XY offset from SET0
        dx, dy = well_offsets[i]
        protocol.comment("F0")
        g_cmd = "G0"
        if dx != 0:
            g_cmd += f" X{dx}"
        if dy != 0:
            g_cmd += f" Y{dy}"
        g_cmd += " Z1"
        protocol.comment(g_cmd)
        protocol.comment("F0.5")
        if corner:
            protocol.comment("MR X0.8 Y0.8 Z-1")
        else:
            protocol.comment("MR Z-1")
        protocol.comment("F0")
        
    #def move_to_chip():
    #    protocol.comment("Moving into chip...")
    #    protocol.comment("F0")
    #    protocol.comment("G0")# Z1")
    #    #protocol.comment("F0.5")
    #    #protocol.comment("MR Z-1")
    #    protocol.comment("F0")
    
    #def exit_chip():
    #    protocol.comment("F0.5")
    #    protocol.comment("MR Z1")
    #    protocol.comment("F0")
    #    protocol.comment("MR Z4")
    #    protocol.comment("MR Y4.5")
    #    return_microscope_to_start()
    def lift_out(corner=False):
        protocol.comment("F0.5")
        if corner:
            protocol.comment("MR X-0.8 Y-0.8 Z1")
        else:
            protocol.comment("MR Z1")
        protocol.comment("F0")
        #protocol.comment("MR Z4")

    # =========================================================================
    # INTERACTIVE LOOP
    # Click on a well in the UI to change source, press 'E' to exit
    # =========================================================================
    
    #protocol.comment("CLEAR")
    protocol.comment("Moving above chip...")
    p1000_multi.move_to(above_chip_location)
    protocol.comment("LOOP_START")
    protocol.comment("G0 Z5")
    protocol.comment("Pause - Move to the top of the hole, touching the liquid")
    #set_up_locations()
    protocol.comment("SET0")

    

    # Aspirate 25 from each reservoir
    # Position 1: Start (upper left)
    aspirate_rate = 2
    dispense_rate = 5#2#6

    """
    protocol.comment("Aspirating at position 1...")
    p1000_multi.aspirate(25, flow_rate=aspirate_rate)
    # Positions 2-6: Move and aspirate
    for i in range(5):
        move_to_next_well(i)
        protocol.comment(f"Aspirating at position {i+2}...")
        p1000_multi.aspirate(25, flow_rate=aspirate_rate)
    
    # Return microscope to well 0 before leaving chip
    return_microscope_to_start()
    """

    protocol.comment(f"=== Dispense ===")
    lift_out(corner=False)
    fill_volume = 20#30#35
    remove_volume = 20
    second_well = "A1"
    # Collect 150 liquid
    # for i in range(1):#6
    #     if i==0:
    #         p1000_multi.aspirate(fill_volume+1, tube_rack["A1"])
    #         p1000_multi.dispense(fill_volume, tube_rack["A1"])
    #         p1000_multi.aspirate(fill_volume, tube_rack["A1"])
    #         p1000_multi.dispense(fill_volume, tube_rack["A1"])
    #         p1000_multi.aspirate(fill_volume, tube_rack["A1"])
    #         p1000_multi.dispense(fill_volume, tube_rack["A1"])
    #         p1000_multi.aspirate(fill_volume, tube_rack["A1"])
    #         p1000_multi.dispense(fill_volume, tube_rack["A1"])
    #         p1000_multi.aspirate(fill_volume, tube_rack["A1"])
    #     else:
    #         p1000_multi.aspirate(fill_volume, tube_rack["A1"])
    #     protocol.delay(seconds=2)
    #     return_to_well(i, corner=True)
    #     p1000_multi.dispense(fill_volume, flow_rate=dispense_rate)
    #     p1000_multi.aspirate(remove_volume, flow_rate=aspirate_rate)
    #     lift_out(corner=True)
    #     protocol.comment("SR PROJI30")

    for i in range(1):#6
        if i==0:
            p1000_multi.aspirate(fill_volume+1, gel_plate["A1"])
            #protocol.delay(seconds=2)
            p1000_multi.dispense(fill_volume, gel_plate[second_well])
            p1000_multi.aspirate(fill_volume, gel_plate[second_well])
            p1000_multi.dispense(fill_volume, gel_plate[second_well])
            p1000_multi.aspirate(fill_volume, gel_plate[second_well])
            p1000_multi.dispense(fill_volume, gel_plate[second_well])
            p1000_multi.aspirate(fill_volume, gel_plate[second_well])
            p1000_multi.dispense(fill_volume, gel_plate[second_well])
            p1000_multi.aspirate(fill_volume, gel_plate[second_well])
        else:
            p1000_multi.aspirate(fill_volume, gel_plate[second_well])
        protocol.delay(seconds=2)
        return_to_well(i, corner=True)
        p1000_multi.dispense(fill_volume, flow_rate=dispense_rate)
        p1000_multi.aspirate(remove_volume, flow_rate=aspirate_rate)
        lift_out(corner=True)
        protocol.comment("SR PROJI30")
    #return_microscope_to_start()
    p1000_multi.blow_out(tube_rack["A2"])
    
    
     # Check if user wants to exit
    protocol.comment("Pause - E to exit, or tab to continue")
    protocol.comment("CHECK_EXIT")
    protocol.comment("LOOP_END")

    # =========================================================================
    # EXIT POINT - reached when user presses 'E'
    # =========================================================================
    # Blow out collected liquid
    
    protocol.comment("EXIT_LOOP")
    protocol.comment("Exiting loop")# - dropping tip")
    
    # Step 4: Drop the tip in the trash
    #p1000_multi.blow_out(tube_rack["A2"])
    #p1000_multi.drop_tip()

