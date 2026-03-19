"""
96 well spheroid media change protocol.

Uses 8-channel 200uL pipette to perform a media change on columns 1-4:
1. Pick up tips from B2 and prime with 3x aspirate/dispense cycles from fresh media (A1)
2. For each column: aspirate 166uL of old media → dispense + blowout at top of waste well (A2) → aspirate 166uL fresh media (A1) → dispense + blowout to plate column
3. Discard tips into trash bin at A3 and home

Deck layout:
- A3: Trash bin
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

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

# =============================================================================
# LABWARE GEOMETRY
# All measurements in mm from the FRONT-LEFT corner of the labware footprint
# =============================================================================
LABWARE_X_DIMENSION = 127.76
LABWARE_Y_DIMENSION = 85.47
LABWARE_Z_DIMENSION = 44.0

WELL_1_X = 40
WELL_1_Y = 55
WELL_2_X = 90.76
WELL_2_Y = 55

WELL_DEPTH = 40.0
WELL_BOTTOM_Z = 25
WELL_X_DIMENSION = 55.0
WELL_Y_DIMENSION = 70.0

# =============================================================================
# PIPETTING PARAMETERS (mm from well bottom unless noted)
# =============================================================================
ASPIRATE_HEIGHT  = 0.0    # reservoir aspirate
DISPENSE_HEIGHT  = -1.0   # reservoir dispense
BLOWOUT_HEIGHT   = 10     # mm above well top
PLATE_X_OFFSET   = -1.3   # mm (negative = left)
PLATE_Z_OFFSET   = 5.0    # mm above well bottom
ASPIRATE_RATE    = 50     # uL/s
DISPENSE_RATE    = 20     # uL/s

RESERVOIR_1_X_OFFSET = 0.0
RESERVOIR_2_X_OFFSET = 0.0
RESERVOIR_Y_OFFSET   = 0.0
RESERVOIR_Z_OFFSET   = 0.0

# =============================================================================
# CUSTOM LABWARE DEFINITION
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
            "depth": WELL_DEPTH, "totalLiquidVolume": 50000, "shape": "rectangular",
            "xDimension": WELL_X_DIMENSION, "yDimension": WELL_Y_DIMENSION,
            "x": WELL_1_X, "y": WELL_1_Y, "z": WELL_BOTTOM_Z
        },
        "A2": {
            "depth": WELL_DEPTH, "totalLiquidVolume": 50000, "shape": "rectangular",
            "xDimension": WELL_X_DIMENSION, "yDimension": WELL_Y_DIMENSION,
            "x": WELL_2_X, "y": WELL_2_Y, "z": WELL_BOTTOM_Z
        }
    },
    "groups": [{"metadata": {"wellBottomShape": "flat"}, "wells": ["A1", "A2"]}],
    "parameters": {
        "format": "irregular", "quirks": [],
        "isTiprack": False, "isMagneticModuleCompatible": False,
        "loadName": "custom_2_reservoir_50ml"
    },
    "namespace": "custom_labware",
    "version": 1,
    "schemaVersion": 2,
    "cornerOffsetFromSlot": {"x": 0, "y": 0, "z": 0}
}


def run(protocol: protocol_api.ProtocolContext):
    # --- Load labware ---
    trash       = protocol.load_trash_bin('A3')
    tiprack_200 = protocol.load_labware('opentrons_flex_96_filtertiprack_200ul', 'B2', label='200uL Tips')
    reservoir   = protocol.load_labware_from_definition(CUSTOM_2_RESERVOIR_DEF, 'C1', label='Custom 2-Reservoir')
    plate_96    = protocol.load_labware('corning_96_wellplate_360ul_flat', 'D3', label='96 Well Plate')

    # --- Load pipette ---
    p200_multi = protocol.load_instrument('flex_8channel_1000', 'right', tip_racks=[tiprack_200])
    p200_multi.flow_rate.aspirate = ASPIRATE_RATE
    p200_multi.flow_rate.dispense = DISPENSE_RATE

    # --- Define reusable locations ---
    media_location = reservoir['A1'].bottom(ASPIRATE_HEIGHT + RESERVOIR_Z_OFFSET).move(
        types.Point(x=RESERVOIR_1_X_OFFSET, y=RESERVOIR_Y_OFFSET, z=0)
    )
    waste_location = reservoir['A2'].bottom(DISPENSE_HEIGHT + RESERVOIR_Z_OFFSET).move(
        types.Point(x=RESERVOIR_2_X_OFFSET, y=RESERVOIR_Y_OFFSET, z=0)
    )
    blowout_location = reservoir['A2'].top(BLOWOUT_HEIGHT)

    protocol.comment("=== 96 Well Media Change Protocol ===")
    protocol.comment(f"Transfer volume: 166uL | Aspirate height: {ASPIRATE_HEIGHT}mm | Dispense height: {DISPENSE_HEIGHT}mm")

    # --- Pick up tips and prime ---
    p200_multi.pick_up_tip()
    p200_multi.mix(3, 160, media_location)

    # --- Media change: columns 1-4 ---
    for col in ['A1', 'A2', 'A3', 'A4']:
        protocol.comment(f"Media change: column {col}...")

        p200_multi.aspirate(166, plate_96[col].bottom(ASPIRATE_HEIGHT + PLATE_Z_OFFSET).move(types.Point(x=PLATE_X_OFFSET, y=0, z=0)))
        protocol.delay(seconds=1)

        p200_multi.dispense(166, blowout_location)
        p200_multi.blow_out(blowout_location)
        protocol.delay(seconds=1)

        p200_multi.aspirate(166, media_location)
        protocol.delay(seconds=1)

        p200_multi.dispense(166, plate_96[col].bottom(DISPENSE_HEIGHT + PLATE_Z_OFFSET).move(types.Point(x=PLATE_X_OFFSET, y=0, z=0)))
        p200_multi.blow_out(blowout_location)

    # --- Drop tips and home ---
    p200_multi.drop_tip(trash)
    protocol.home()
    protocol.comment("=== Protocol complete! ===")
