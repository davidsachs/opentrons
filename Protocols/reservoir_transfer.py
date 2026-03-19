"""
Simple protocol to transfer liquid between two reservoirs in custom labware.

Uses 8-channel 1000uL pipette to:
1. Pick up 8 tips from A2
2. Aspirate 1mL from reservoir 1 (A1)
3. Dispense into reservoir 2 (A2)
4. Return tips to tip box

Tunable parameters to calibrate custom labware position.
"""

from opentrons import protocol_api, types

metadata = {
    'protocolName': 'Reservoir Transfer Test',
    'author': 'David Sachs',
    'description': 'Transfer 1mL between custom 2-reservoir labware with tunable offsets',
}

requirements = {"robotType": "Flex", "apiLevel": "2.19"}

# =============================================================================
# LABWARE GEOMETRY - Measure your physical reservoir and enter values here
# All measurements in mm from the FRONT-LEFT corner of the labware footprint
# =============================================================================

# Labware footprint (should match a standard Opentrons deck slot)
LABWARE_X_DIMENSION = 127.76  # mm (left to right)
LABWARE_Y_DIMENSION = 85.47   # mm (front to back)
LABWARE_Z_DIMENSION = 44.0    # mm (total height)

# Well 1 (A1) center position - measure from front-left corner of labware
WELL_1_X = 40    # mm from left edge to well center
WELL_1_Y = 55  # mm from front edge to well center  <-- ADJUST THIS!

# Well 2 (A2) center position - measure from front-left corner of labware
WELL_2_X = 90.76   # mm from left edge to well center
WELL_2_Y = 55#42.735  # mm from front edge to well center  <-- ADJUST THIS!

# Well dimensions (same for both wells)
WELL_DEPTH = 40.0           # mm
WELL_BOTTOM_Z = 25#40.0         # mm from labware bottom to well bottom
WELL_X_DIMENSION = 55.0     # mm (well width)
WELL_Y_DIMENSION = 70.0     # mm (well length front-to-back)

# =============================================================================
# PIPETTING PARAMETERS
# =============================================================================

# Aspiration height from bottom of well (mm)
ASPIRATE_HEIGHT = 0.0  # mm from well bottom

# Dispense height from bottom of well (mm)
DISPENSE_HEIGHT = 10.0  # mm from well bottom

# Blowout height from top of well (mm) - negative = below top surface
BLOWOUT_HEIGHT = 10#-5.0  # mm from top (negative means below the rim)

# =============================================================================
# FINE-TUNING OFFSETS (relative to well centers defined above)
# Use these for small adjustments without changing the geometry
# =============================================================================

# X offset for reservoir 1 (A1): positive = toward A2, negative = toward edge
RESERVOIR_1_X_OFFSET = 0.0  # mm

# X offset for reservoir 2 (A2): positive = toward edge, negative = toward A1
RESERVOIR_2_X_OFFSET = 0.0  # mm

# Y offset (same for both wells): positive = toward back, negative = toward front
RESERVOIR_Y_OFFSET = 0.0  # mm

# Z offset: additional height adjustment (positive = higher)
RESERVOIR_Z_OFFSET = 0.0  # mm

# =============================================================================
# CUSTOM LABWARE DEFINITION (built from parameters above)
# =============================================================================
CUSTOM_2_RESERVOIR_DEF = {
    "ordering": [["A1"], ["A2"]],
    "brand": {"brand": "Custom", "brandId": ["custom-2-reservoir"]},
    "metadata": {
        "displayName": "Custom 2-Well Reservoir",
        "displayCategory": "reservoir",
        "displayVolumeUnits": "mL",
        "tags": []
    },
    "dimensions": {
        "xDimension": LABWARE_X_DIMENSION,
        "yDimension": LABWARE_Y_DIMENSION,
        "zDimension": LABWARE_Z_DIMENSION
    },
    "wells": {
        "A1": {
            "depth": WELL_DEPTH,
            "totalLiquidVolume": 50000,
            "shape": "rectangular",
            "xDimension": WELL_X_DIMENSION,
            "yDimension": WELL_Y_DIMENSION,
            "x": WELL_1_X,
            "y": WELL_1_Y,
            "z": WELL_BOTTOM_Z
        },
        "A2": {
            "depth": WELL_DEPTH,
            "totalLiquidVolume": 50000,
            "shape": "rectangular",
            "xDimension": WELL_X_DIMENSION,
            "yDimension": WELL_Y_DIMENSION,
            "x": WELL_2_X,
            "y": WELL_2_Y,
            "z": WELL_BOTTOM_Z
        }
    },
    "groups": [{"metadata": {"wellBottomShape": "flat"}, "wells": ["A1", "A2"]}],
    "parameters": {
        "format": "irregular",
        "quirks": [],
        "isTiprack": False,
        "isMagneticModuleCompatible": False,
        "loadName": "custom_2_reservoir_50ml"
    },
    "namespace": "custom_labware",
    "version": 1,
    "schemaVersion": 2,
    "cornerOffsetFromSlot": {"x": 0, "y": 0, "z": 0}
}


def run(protocol: protocol_api.ProtocolContext):
    """Main protocol execution."""

    # Load tip rack in A2
    tiprack_1000 = protocol.load_labware(
        'opentrons_flex_96_filtertiprack_1000ul',
        'B2',
        label='1000uL Tips'
    )

    # Load custom 2-reservoir labware from embedded definition
    reservoir = protocol.load_labware_from_definition(
        CUSTOM_2_RESERVOIR_DEF,
        'C1',
        label='Custom 2-Reservoir'
    )

    # Load 8-channel 1000uL pipette on right mount
    p1000_multi = protocol.load_instrument(
        'flex_8channel_1000',
        'right',
        tip_racks=[tiprack_1000]
    )

    # Display configuration
    protocol.comment("=== Reservoir Transfer Protocol ===")
    protocol.comment(f"Well 1 position: X={WELL_1_X}, Y={WELL_1_Y}")
    protocol.comment(f"Well 2 position: X={WELL_2_X}, Y={WELL_2_Y}")
    protocol.comment(f"Aspirate height: {ASPIRATE_HEIGHT} mm from bottom")
    protocol.comment(f"Dispense height: {DISPENSE_HEIGHT} mm from bottom")

    # Pick up 8 tips (full column)
    protocol.comment("Picking up tips...")
    p1000_multi.pick_up_tip()

    # Calculate offset-adjusted positions (all offsets relative to well center)
    # Reservoir 1 (A1) - aspirate position
    aspirate_location = reservoir['A1'].bottom(ASPIRATE_HEIGHT + RESERVOIR_Z_OFFSET).move(
        types.Point(x=RESERVOIR_1_X_OFFSET, y=RESERVOIR_Y_OFFSET, z=0)
    )

    # Reservoir 2 (A2) - dispense position
    dispense_location = reservoir['A2'].bottom(DISPENSE_HEIGHT + RESERVOIR_Z_OFFSET).move(
        types.Point(x=RESERVOIR_2_X_OFFSET, y=RESERVOIR_Y_OFFSET, z=0)
    )

    # Reservoir 2 (A2) - blowout position (from top, with same X/Y offsets)
    blowout_location = reservoir['A2'].top(BLOWOUT_HEIGHT).move(
        types.Point(x=RESERVOIR_2_X_OFFSET, y=RESERVOIR_Y_OFFSET, z=0)
    )

    # Move to aspirate position first (pause to verify alignment)
    protocol.comment("Pause. Moving to aspirate position (A1)...")
    p1000_multi.move_to(aspirate_location)

    # Aspirate in place
    protocol.comment("Aspirating 1000uL in place...")
    p1000_multi.aspirate(1000)

    # Brief pause to let liquid settle
    protocol.delay(seconds=1)

    # Move to dispense position (pause to verify alignment)
    protocol.comment("Pause. Moving to dispense position (A2)...")
    p1000_multi.move_to(dispense_location)

    # Dispense in place
    protocol.comment("Dispensing 1000uL in place...")
    p1000_multi.dispense(1000)

    # Blow out to ensure complete dispensing
    p1000_multi.move_to(blowout_location)
    p1000_multi.blow_out()

    # Return tips to tip rack
    protocol.comment("Returning tips...")
    p1000_multi.return_tip()

    protocol.comment("=== Protocol complete! ===")
