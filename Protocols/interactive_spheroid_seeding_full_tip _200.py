from opentrons import protocol_api, types
from opentrons.legacy_commands.commands import move_to
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Interactive Spheroid Seeding',
    'author': 'David Sachs',
    'description': 'Interactive spheroid seeding - click wells to change source, press E to exit',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

# =============================================================================
# CONFIGURATION
# =============================================================================

# "Above chip" position (absolute coordinates) - fixed safe reference point
# This position is used for approach/retreat and never changes
ABOVE_CHIP_X = 400
ABOVE_CHIP_Y = 140
ABOVE_CHIP_Z = 50  # High enough to be safely above the chip

# Pipetting parameters for spheroid handling
UNSTICK_RATE = 3       # Flow rate for initial dislodge (uL/s)
PICKUP_RATE = 15        # Flow rate for spheroid pickup (uL/s)
DISPENSE_RATE = 3
      # Flow rate for spheroid dispensing (uL/s)

# Volumes
UNSTICK_VOLUME = 15     # Volume to aspirate for dislodging
DISPENSE_BACK = 15      # Volume to dispense back to dislodge
PICKUP_VOLUME = 60     # Volume to aspirate with spheroid
SPHEROID_HEIGHT = 1.3
UNSTICK_HEIGHT = 2
# Starting well (will be updated by UI clicks)
START_WELL = "A1"

def run(protocol: protocol_api.ProtocolContext):
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
        protocol.comment("G0")
        protocol.comment("F0.5")
        #protocol.comment("MR X-0.5")
        #protocol.comment("F0")
    # Load trash bin
    trash = protocol.load_trash_bin('A3')
    
    # Load labware
    tiprack_200 = protocol.load_labware('opentrons_flex_96_filtertiprack_200ul', 'B2')
    spheroid_plate = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="D3",
        namespace="opentrons",
        version=4,
        label="Spheroid Source Plate"
    )
    # Tube rack in B1
    tube_rack = protocol.load_labware(
        'opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap',
        'D2',
        label='Reagent Tubes'
    )
    tube_rack.set_offset(x=0, y=0, z=1)

    # Load pipette
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right')
    
    # Configure for single tip pickup using overhang (SINGLE nozzle configuration)
    p1000_multi.configure_nozzle_layout(
        style=SINGLE,
        start='H1',
        tip_racks=[tiprack_200]
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

    p1000_multi.aspirate(100, tube_rack["A1"])
    protocol.comment("Moving above chip...")
    p1000_multi.move_to(above_chip_location)
    
    protocol.comment("G0 Z5")

    

    protocol.comment("Pause - Move to the top of the hole, touching the liquid")
    #set_up_locations()
    protocol.comment("SET0")

    protocol.comment("Pause - Move into chip and select spheroid well, then Tab to save")

    # Move to "above chip" position first (fixed reference point)
    # Save the "in chip" position as location 0 (user adjusts with X/Y/Z commands)
    #set_up_locations()

    # Get the spheroid from the current source well
    # Note: The well used here (A1) will be replaced at runtime by the GUI
    # based on which well the user clicked on (plate offset override)
    protocol.comment("Picking up spheroid from selected well...")
    # Move to position first and pause to let tip submerge before aspirating
    p1000_multi.move_to(spheroid_plate[START_WELL].bottom(z=UNSTICK_HEIGHT))
    p1000_multi.aspirate(UNSTICK_VOLUME, rate=UNSTICK_RATE)
    protocol.delay(seconds=1)
    p1000_multi.dispense(DISPENSE_BACK, rate=DISPENSE_RATE)
    protocol.delay(seconds=1)
    p1000_multi.aspirate(UNSTICK_VOLUME, rate=UNSTICK_RATE)
    protocol.delay(seconds=1)
    p1000_multi.dispense(DISPENSE_BACK, rate=DISPENSE_RATE)
    protocol.delay(seconds=1)
    p1000_multi.move_to(spheroid_plate[START_WELL].bottom(z=SPHEROID_HEIGHT))
    protocol.delay(seconds=3)
    p1000_multi.aspirate(PICKUP_VOLUME, rate=PICKUP_RATE)

    # Move to "in chip" position (saved location 0)
    protocol.comment("Moving into chip with spheroid...")
    move_to_chip()
    #protocol.comment("F0")
    #protocol.comment("G1")
    #X=417.2, Y=155.5, Z=6.0

    # Pause for manual seeding - user can fine-tune position if needed
    protocol.comment("Pause - Seed spheroid, adjust if needed")
    #p1000_multi.dispense(6, rate=1)
    # Blow out remaining liquid back into the source well
    protocol.comment("Blowing out in waste tube...")
    p1000_multi.blow_out(tube_rack["A1"])
    
    #p1000_multi.move_to(spheroid_plate["A1"].bottom(z=UNSTICK_HEIGHT))
    #p1000_multi.blow_out(spheroid_plate["A1"])

    protocol.comment("Pause - E to exit, or do another seeding")
    
    # Loop back
    # Check if user wants to exit
    protocol.comment("CHECK_EXIT")
    protocol.comment("LOOP_END")

    # =========================================================================
    # EXIT POINT - reached when user presses 'E'
    # =========================================================================
    protocol.comment("EXIT_LOOP")
    protocol.comment("Exiting loop - dropping tip")

    # Drop the tip in trash
    p1000_multi.drop_tip()

    protocol.comment("=== Interactive seeding complete! ===")
