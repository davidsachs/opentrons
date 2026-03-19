from opentrons import protocol_api, types
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Washing out hydrogel (microscope follows, 50uL tips)',
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
    tiprack_1000 = protocol.load_labware('opentrons_flex_96_filtertiprack_50ul', 'B1')
    # Load pipettes (only using p1000)
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right')

    # Configure for single tip pickup using overhang (SINGLE nozzle configuration)
    p1000_multi.configure_nozzle_layout(
        style=SINGLE,
        start='H1',
        tip_racks=[tiprack_1000]
    )

    # Tube rack in D2
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

    # Return microscope to starting well position (undo cumulative movement)
    def return_microscope_to_start():
        """Send microscope back to the position of well 0.
        After visiting all 6 positions, the cumulative offset is (0, -4.5).
        So we need to move Y+4.5 to get back to start."""
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

    def return_to_well(i):
        """Move pipette directly to well i using SET0 as origin.
        Microscope SR is a relative move from the previous well (i-1)."""
        if i > 0:
            rel_dx = x_locs[i - 1]
            rel_dy = y_locs[i - 1]
            protocol.comment(f"SR X{rel_dx} Y{rel_dy}")
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
        protocol.comment("MR Z-1")
        protocol.comment("F0")

    def lift_out():
        protocol.comment("F0.5")
        protocol.comment("MR Z1")
        protocol.comment("F0")

    # =========================================================================
    # INTERACTIVE LOOP
    # Click on a well in the UI to change source, press 'E' to exit
    # =========================================================================

    protocol.comment("CLEAR")
    protocol.comment("Moving above chip...")
    p1000_multi.move_to(above_chip_location)
    protocol.comment("LOOP_START")
    protocol.comment("G0 Z5")
    protocol.comment("Pause - Move to the top of the hole, touching the liquid")
    protocol.comment("SET0")

    aspirate_rate = 5
    dispense_rate = 10
    mix_volume = 25

    # === Initial aspirate: collect waste from each well, shuttle to waste tube ===
    protocol.comment("=== Aspirate waste ===")
    for i in range(6):
        return_to_well(i)
        protocol.comment(f"Aspirating at position {i+1}...")
        p1000_multi.aspirate(mix_volume, flow_rate=aspirate_rate)
        lift_out()
        p1000_multi.blow_out(tube_rack["A2"])
    return_microscope_to_start()

    # === Wash cycles ===
    for wash_cycle in range(2):
        protocol.comment(f"=== Wash cycle {wash_cycle + 1} of 2 ===")

        # Dispense wash liquid into each well (shuttle from tube rack)
        for i in range(6):
            p1000_multi.aspirate(mix_volume, tube_rack["A1"])
            return_to_well(i)
            protocol.comment(f"Dispensing at position {i+1}...")
            p1000_multi.dispense(mix_volume, flow_rate=dispense_rate)
            lift_out()
        return_microscope_to_start()
        #p1000_multi.blow_out(tube_rack["A2"])

        # Mix and aspirate waste from each well
        for i in range(6):
            return_to_well(i)
            protocol.comment(f"Mixing at position {i+1}...")
            for j in range(2):
                p1000_multi.aspirate(mix_volume, flow_rate=aspirate_rate)
                p1000_multi.dispense(mix_volume, flow_rate=dispense_rate)
            #p1000_multi.aspirate(mix_volume, flow_rate=aspirate_rate)
            lift_out()
            p1000_multi.blow_out(tube_rack["A2"])
        return_microscope_to_start()

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
    #p1000_multi.blow_out(tube_rack["A2"])

    # Drop the tip in the trash
    p1000_multi.drop_tip()
