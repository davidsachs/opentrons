from opentrons import protocol_api
from opentrons.protocol_api import SINGLE

metadata = {
    'protocolName': 'Spheroid Pickup Test',
    'author': 'David Sachs',
    'description': 'Test parameters for picking up / unsticking spheroids from 96 well plate',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

# =============================================================================
# CONFIGURATION - tweak these to test pickup
# =============================================================================

# Pipetting parameters for spheroid handling
UNSTICK_RATE = 3       # Flow rate for initial dislodge (uL/s)
PICKUP_RATE = 15       # Flow rate for spheroid pickup (uL/s)
DISPENSE_RATE = 3      # Flow rate for dispensing back to dislodge

# Volumes
UNSTICK_VOLUME = 15    # Volume to aspirate for dislodging
DISPENSE_BACK = 15     # Volume to dispense back to dislodge
PICKUP_VOLUME = 30     # Volume to aspirate with spheroid

# Heights above well bottom (mm)
UNSTICK_HEIGHT = 2
SPHEROID_HEIGHT = 1.3

# Starting well
START_WELL = "A1"

def run(protocol: protocol_api.ProtocolContext):
    # Load trash bin
    trash = protocol.load_trash_bin('A3')

    # Load labware
    tiprack_1000 = protocol.load_labware('opentrons_flex_96_filtertiprack_1000ul', 'B2')
    spheroid_plate = protocol.load_labware(
        "corning_96_wellplate_360ul_flat",
        location="D3",
        namespace="opentrons",
        version=4,
        label="Spheroid Source Plate"
    )

    # Load pipette
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right')

    # Configure for single tip pickup
    p1000_multi.configure_nozzle_layout(
        style=SINGLE,
        start='H1',
        tip_racks=[tiprack_1000]
    )

    # Pick up a single tip
    protocol.comment("Picking up tip...")
    p1000_multi.pick_up_tip()

    # Move to well and attempt unstick + pickup
    protocol.comment("Moving to well and testing pickup...")
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

    # Pause so you can inspect whether the spheroid was picked up
    protocol.comment("Pause - check if spheroid was picked up")

    # Blow out back into the well
    protocol.comment("Blowing out...")
    p1000_multi.blow_out(spheroid_plate[START_WELL])

    # Drop the tip
    p1000_multi.drop_tip()

    protocol.comment("=== Pickup test complete ===")
