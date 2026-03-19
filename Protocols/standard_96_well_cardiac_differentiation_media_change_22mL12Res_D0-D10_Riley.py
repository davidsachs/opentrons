"""
96 well spheroid media change protocol (NEST 12-well 22mL reservoir).

Uses 8-channel 200uL pipette to perform a media change on columns 1-4:
1. Pick up tips from B2
2. For each column: aspirate 166uL of old media → dispense + blowout to waste well (A12) → aspirate 166uL fresh media from corresponding reservoir well (A1-A4) → dispense + blowout to plate column
3. Discard tips into trash bin at A3 and home

Reservoir mapping:
- A1  → fresh media for plate column 1
- A2  → fresh media for plate column 2
- A3  → fresh media for plate column 3
- A4  → fresh media for plate column 4
- A12 → waste

Deck layout:
- A3: Trash bin
- B2: 200uL tip rack
- C1: NEST 12-well 22mL reservoir
- D3: 96 well plate
"""

from opentrons import protocol_api, types

metadata = {
    'protocolName': '96 well spheroid media change - 22mL 12-well reservoir',
    'author': 'Riley',
    'description': 'Standard media change for current 96 well format, 32 spheroids',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.25'
}

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
RESERVOIR_Z_OFFSET = 0.0


def run(protocol: protocol_api.ProtocolContext):
    # --- Load labware ---
    trash       = protocol.load_trash_bin('A3')
    tiprack_200 = protocol.load_labware('opentrons_flex_96_filtertiprack_200ul', 'B2', label='200uL Tips')
    reservoir   = protocol.load_labware('nest_12_reservoir_22ml', 'C1', label='22mL 12-Well Reservoir')
    plate_96    = protocol.load_labware('corning_96_wellplate_360ul_flat', 'D3', label='96 Well Plate')

    # --- Load pipette ---
    p200_multi = protocol.load_instrument('flex_8channel_1000', 'right', tip_racks=[tiprack_200])
    p200_multi.flow_rate.aspirate = ASPIRATE_RATE
    p200_multi.flow_rate.dispense = DISPENSE_RATE

    waste_location   = reservoir['A12'].bottom(DISPENSE_HEIGHT + RESERVOIR_Z_OFFSET)
    blowout_location = reservoir['A12'].top(BLOWOUT_HEIGHT)

    protocol.comment("=== 96 Well Media Change Protocol ===")
    protocol.comment(f"Transfer volume: 166uL | Aspirate height: {ASPIRATE_HEIGHT}mm | Dispense height: {DISPENSE_HEIGHT}mm")

    # --- Pick up tips ---
    p200_multi.pick_up_tip()

    # --- Media change: plate columns 1-4, reservoir wells A1-A4 ---
    for plate_col, res_well in zip(['A1', 'A2', 'A3', 'A4'], ['A1', 'A2', 'A3', 'A4']):
        protocol.comment(f"Media change: plate column {plate_col}, fresh media from reservoir {res_well}...")

        p200_multi.aspirate(166, plate_96[plate_col].bottom(ASPIRATE_HEIGHT + PLATE_Z_OFFSET).move(types.Point(x=PLATE_X_OFFSET, y=0, z=0)))
        protocol.delay(seconds=1)

        p200_multi.dispense(166, blowout_location_location)
        p200_multi.blow_out(blowout_location)
        protocol.delay(seconds=1)

        p200_multi.aspirate(166, reservoir[res_well].bottom(ASPIRATE_HEIGHT + RESERVOIR_Z_OFFSET))
        protocol.delay(seconds=1)

        p200_multi.dispense(166, plate_96[plate_col].bottom(DISPENSE_HEIGHT + PLATE_Z_OFFSET).move(types.Point(x=PLATE_X_OFFSET, y=0, z=0)))
        p200_multi.blow_out(blowout_location)

    # --- Drop tips and home ---
    p200_multi.drop_tip(trash)
    protocol.home()
    protocol.comment("=== Protocol complete! ===")
