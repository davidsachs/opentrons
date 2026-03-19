from opentrons import protocol_api, types
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Old protocol for washing out hydrogel',
    'author': 'David Sachs',
    'description': 'Old protocol for washing out hydrogel',
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
    
    # =========================================================================
    # INTERACTIVE LOOP
    # Click on a well in the UI to change source, press 'E' to exit
    # =========================================================================
    protocol.comment("LOOP_START")
    
    protocol.comment("Moving above chip...")
    p1000_multi.move_to(above_chip_location)
    protocol.comment("Pause - Move to starting position in chip, then resume")


    # Save starting position (user sets this during pause)
        # Position should have pipette in the chip, not above
    protocol.comment("SET0")

    # Aspirate 25 from each reservoir
    # Position 1: Start (upper left)
    protocol.comment("Aspirating at position 1...")
    p1000_multi.aspirate(25)
    # Position 2: Move x +4.5
    protocol.comment("Pause")
    protocol.comment("Aspirating at position 2...")
    p1000_multi.aspirate(25)
    # Position 3: Move y -4.5
    protocol.comment("Pause")
    protocol.comment("Aspirating at position 3...")
    p1000_multi.aspirate(25)
    # Position 4: Move y -4.5
    protocol.comment("Pause")
    protocol.comment("Aspirating at position 4...")
    p1000_multi.aspirate(25)
    # Position 5: Move x -4.5
    protocol.comment("Pause")
    protocol.comment("Aspirating at position 5...")
    p1000_multi.aspirate(25)
    # Position 6: Move y +4.5
    protocol.comment("Pause")
    protocol.comment("Aspirating at position 6...")
    p1000_multi.aspirate(25)
    protocol.comment("Pause")

    # Repeat wash cycle 3 times
    for wash_cycle in range(3):
        protocol.comment(f"=== Wash cycle {wash_cycle + 1} of 3 ===")

        # Blow out collected liquid
        p1000_multi.blow_out(tube_rack["A2"])

        # Collect 150 liquid
        p1000_multi.aspirate(150, tube_rack["A1"])

        # Move to "in chip" position (saved location 0)
        protocol.comment("Moving into chip...")
        protocol.comment("F0")
        protocol.comment("G0")

        # Dispense 25 in each reservoir
        # Position 1: Start (upper left)
        protocol.comment("Dispensing at position 1...")
        p1000_multi.dispense(25)
        # Position 2: Move x +4.5
        protocol.comment("Pause")
        protocol.comment("Dispensing at position 2...")
        p1000_multi.dispense(25)
        # Position 3: Move y -4.5
        protocol.comment("Pause")
        protocol.comment("Dispensing at position 3...")
        p1000_multi.dispense(25)
        # Position 4: Move y -4.5
        protocol.comment("Pause")
        protocol.comment("Dispensing at position 4...")
        p1000_multi.dispense(25)
        # Position 5: Move x -4.5
        protocol.comment("Pause")
        protocol.comment("Dispensing at position 5...")
        p1000_multi.dispense(25)
        # Position 6: Move y +4.5
        protocol.comment("Pause")
        protocol.comment("Dispensing at position 6...")
        p1000_multi.dispense(25)
        protocol.comment("Pause")

        # Set the washing rate to 3ul/s
        washing_rate = 300

        # Mix in each reservoir: up and down twice then aspirate
        # Position 1: Move y +4.5 (back to start)
        protocol.comment("Pause")
        protocol.comment("Mixing at position 1...")
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(25)
        # Position 2: Move x +4.5
        protocol.comment("Pause")
        protocol.comment("Mixing at position 2...")
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(25)
        # Position 3: Move y -4.5
        protocol.comment("Pause")
        protocol.comment("Mixing at position 3...")
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(25)
        # Position 4: Move y -4.5
        protocol.comment("Pause")
        protocol.comment("Mixing at position 4...")
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(25)
        # Position 5: Move x -4.5
        protocol.comment("Pause")
        protocol.comment("Mixing at position 5...")
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(25)
        # Position 6: Move y +4.5
        protocol.comment("Pause")
        protocol.comment("Mixing at position 6...")
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(20)
        p1000_multi.dispense(20)
        p1000_multi.aspirate(25)
        protocol.comment("Pause")
        # Back to start of loop for blow out

    # Could add protocol to fill reservoirs back up? Not sure if needed

    # Check if user wants to exit
    protocol.comment("CHECK_EXIT")
    protocol.comment("LOOP_END")

    # =========================================================================
    # EXIT POINT - reached when user presses 'E'
    # =========================================================================
    # Blow out collected liquid
    p1000_multi.blow_out(tube_rack["A2"])
    protocol.comment("EXIT_LOOP")
    protocol.comment("Exiting loop - dropping tip")
    
    # Step 4: Drop the tip in the trash
    p1000_multi.drop_tip()