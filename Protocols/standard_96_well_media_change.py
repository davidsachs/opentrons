"""
96 well spheroid media change protocol.

Uses 8-channel 200uL pipette to:
1. Pick up 8 tips from B2
2. Aspirate 166uL from 96 well plate (D3) first column
3. Dispense into custom reservoir A2 (waste)
4. Aspirate 166uL from custom reservoir A1 (fresh media)
5. Dispense into 96 well plate first column
6. Blowout
7. Return tips to tip rack

Deck layout:
- B2: 200uL tip rack
- C1: Custom 2-reservoir labware
- D3: 96 well plate
"""

from opentrons import protocol_api, types

metadata = {
    'protocolName': '96 well spheroid media change',
    'author': 'Riley',
    'description': 'Standard media change for current 96 well format, 32 spheroids',
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

    # Load 200uL tip rack in B2
    tiprack_200 = protocol.load_labware(
        'opentrons_flex_96_filtertiprack_200ul',
        'B2',
        label='200uL Tips'
    )

    # Load custom 2-reservoir labware from embedded definition in C1
    reservoir = protocol.load_labware_from_definition(
        CUSTOM_2_RESERVOIR_DEF,
        'C1',
        label='Custom 2-Reservoir'
    )

    # Load 96 well plate in D3
    plate_96 = protocol.load_labware(
        'corning_96_wellplate_360ul_flat',
        'D3',
        label='96 Well Plate'
    )

    # Load 8-channel 1000uL pipette on right mount (using 200uL tips)
    p200_multi = protocol.load_instrument(
        'flex_8channel_1000',
        'right',
        tip_racks=[tiprack_200]
    )

    # Display configuration
    protocol.comment("=== 96 Well Media Change Protocol ===")
    protocol.comment(f"Transfer volume: 166uL")
    protocol.comment(f"Aspirate height: {ASPIRATE_HEIGHT} mm from bottom")
    protocol.comment(f"Dispense height: {DISPENSE_HEIGHT} mm from bottom")

    # Step 1: Pick up tips from B2
    protocol.comment("Step 1: Picking up tips...")
    p200_multi.pick_up_tip()

    # Step 2: Aspirate 166uL from 96 well plate first column (A1)
    protocol.comment("Step 2: Aspirating 166uL from 96 well plate column 1...")
    p200_multi.aspirate(166, plate_96['A1'].bottom(ASPIRATE_HEIGHT))

    # Brief pause to let liquid settle
    protocol.delay(seconds=1)

    # Step 3: Dispense to custom labware A2 (waste)
    protocol.comment("Step 3: Dispensing to reservoir A2 (waste)...")
    waste_location = reservoir['A2'].bottom(DISPENSE_HEIGHT + RESERVOIR_Z_OFFSET).move(
        types.Point(x=RESERVOIR_2_X_OFFSET, y=RESERVOIR_Y_OFFSET, z=0)
    )
    p200_multi.dispense(166, waste_location)

    # Brief pause
    protocol.delay(seconds=1)

    # Step 4: Aspirate from custom labware A1 (fresh media)
    protocol.comment("Step 4: Aspirating 166uL from reservoir A1 (fresh media)...")
    media_location = reservoir['A1'].bottom(ASPIRATE_HEIGHT + RESERVOIR_Z_OFFSET).move(
        types.Point(x=RESERVOIR_1_X_OFFSET, y=RESERVOIR_Y_OFFSET, z=0)
    )
    p200_multi.aspirate(166, media_location)

    # Brief pause to let liquid settle
    protocol.delay(seconds=1)

    # Step 5: Dispense 166uL into 96 well plate
    protocol.comment("Step 5: Dispensing 166uL to 96 well plate column 1...")
    p200_multi.dispense(166, plate_96['A1'].bottom(DISPENSE_HEIGHT))

    # Step 6: Blowout
    protocol.comment("Step 6: Blowout...")
    p200_multi.blow_out(plate_96['A1'].top())

    # Step 7: Return tips to tip rack
    protocol.comment("Step 7: Returning tips...")
    p200_multi.return_tip()

    protocol.comment("=== Protocol complete! ===")
