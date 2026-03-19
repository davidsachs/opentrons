from opentrons import protocol_api
from opentrons.protocol_api import ALL

metadata = {
    'protocolName': 'Simple Spheroid Media Change',
    'author': 'David Sachs',
    'description': 'Wash spheroids and transfer fresh media with gentle pipetting',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.21'
}

# =============================================================================
# CONFIGURATION
# =============================================================================

# Number of columns to process
NUM_COLUMNS = 1

# Starting column on spheroid plate (1-12)
SPHEROID_START_COLUMN = 1

# Starting column on new media plate (1-12)
NEW_MEDIA_START_COLUMN = 1

# Number of wash cycles before final media transfer
NUM_WASHES = 1#2

# Tip rack offset: skip this many columns from the left
TIPRACK_OFFSET = 0

# Tip handling: True = return tips to rack for reuse, False = drop tips in trash
RETURN_TIPS = True

# Spheroid plate position offset (mm)
SPHEROID_PLATE_X_OFFSET = 42.25
SPHEROID_PLATE_Y_OFFSET = 0.0
SPHEROID_PLATE_Z_OFFSET = 0.0

# =============================================================================
# FLOW RATES (uL/s) - Tune these for gentle spheroid handling
# =============================================================================
VERY_SLOW_FLOW_RATE = 20   # Extra gentle for spheroid wells
SLOW_FLOW_RATE = 50        # Gentle for spheroid wells
DEFAULT_FLOW_RATE = 160    # Normal operations

# =============================================================================
# SPHEROID WELL PIPETTING PARAMETERS
# These control how carefully we pipette in spheroid wells
# =============================================================================

# Height above well bottom for aspirating FROM spheroid wells (mm)
# Higher = safer but may not remove all liquid
# Lower = removes more liquid but risks disturbing spheroid
SPHEROID_ASPIRATE_HEIGHT = 3.0  # mm above bottom

# Height above well bottom for dispensing INTO spheroid wells (mm)
# Higher = gentler, liquid falls from above
# Lower = more precise but may disturb spheroid
SPHEROID_DISPENSE_HEIGHT = 20#8.0  # mm above bottom (dispense from high up)

# Whether to touch tip to side of well after aspirating (removes droplets)
TOUCH_TIP_AFTER_ASPIRATE = False

# Delay after dispensing to let liquid settle (seconds)
DISPENSE_DELAY = 0.5

# =============================================================================
# VOLUMES
# =============================================================================
WASH_VOLUME = 100          # uL for each wash cycle (aspirate and dispense)
TRANSFER_VOLUME = 100      # uL of fresh media to add from new media plate

# Mixing parameters for fresh media plate
MIX_REPS = 3
MIX_VOLUME = 80

# =============================================================================
# CUSTOM LABWARE - 2-Well Reservoir (A1=Media source, A2=Waste)
# =============================================================================
CUSTOM_2_RESERVOIR_DEF = {
    "ordering": [["A1"], ["A2"]],
    "brand": {"brand": "Custom", "brandId": ["custom-2-reservoir"]},
    "metadata": {
        "displayName": "Custom 2-Well Reservoir 50mL",
        "displayCategory": "reservoir",
        "displayVolumeUnits": "mL",
        "tags": []
    },
    "dimensions": {
        "xDimension": 127.76,
        "yDimension": 85.47,
        "zDimension": 64.0
    },
    "wells": {
        "A1": {
            "depth": 40.0,
            "totalLiquidVolume": 50000,
            "shape": "rectangular",
            "xDimension": 55.0,
            "yDimension": 70.0,
            "x": 40.0,
            "y": 55.0,
            "z": 22.0
        },
        "A2": {
            "depth": 40.0,
            "totalLiquidVolume": 50000,
            "shape": "rectangular",
            "xDimension": 55.0,
            "yDimension": 70.0,
            "x": 90.76,
            "y": 55.0,
            "z": 22.0
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
    # Build column lists from config
    spheroid_columns = list(range(SPHEROID_START_COLUMN, SPHEROID_START_COLUMN + NUM_COLUMNS))
    new_media_columns = list(range(NEW_MEDIA_START_COLUMN, NEW_MEDIA_START_COLUMN + NUM_COLUMNS))

    protocol.comment(f"Processing {NUM_COLUMNS} column(s)")
    protocol.comment(f"Spheroid plate columns: {spheroid_columns}, New media plate columns: {new_media_columns}")
    protocol.comment(f"Spheroid aspirate height: {SPHEROID_ASPIRATE_HEIGHT}mm, dispense height: {SPHEROID_DISPENSE_HEIGHT}mm")

    # Load trash
    trash = protocol.load_trash_bin('A3')

    # ==========================================================================
    # DECK LAYOUT:
    #   B2: 1000uL filter tips
    #   C1: 2-Well Reservoir (A1=wash media, A2=waste)
    #   C3: Spheroid Plate (with offset)
    #   D3: New Media Plate (pre-assembled fresh media)
    # ==========================================================================

    tiprack = protocol.load_labware('opentrons_flex_96_filtertiprack_1000ul', 'B2',
                                    label='1000uL Tips')

    reservoir = protocol.load_labware_from_definition(
        CUSTOM_2_RESERVOIR_DEF,
        'C1',
        label='Media/Waste Reservoir'
    )

    spheroid_plate = protocol.load_labware(
        'corning_96_wellplate_360ul_flat',
        'C3',
        label='Spheroid Plate'
    )
    spheroid_plate.set_offset(
        x=SPHEROID_PLATE_X_OFFSET,
        y=SPHEROID_PLATE_Y_OFFSET,
        z=SPHEROID_PLATE_Z_OFFSET
    )

    new_media_plate = protocol.load_labware(
        'corning_96_wellplate_360ul_flat',
        'D3',
        label='New Media Plate'
    )

    # Load pipette
    p1000 = protocol.load_instrument('flex_8channel_1000', 'right', tip_racks=[tiprack])

    # Apply tip rack offset
    if TIPRACK_OFFSET > 0:
        start_col = TIPRACK_OFFSET + 1
        p1000.starting_tip = tiprack[f'A{start_col}']
        protocol.comment(f"Tips starting at column {start_col}")

    # Configure for 8-channel mode
    p1000.configure_nozzle_layout(style=ALL, tip_racks=[tiprack])

    # Tip column tracking for wash tips and transfer tips
    wash_tip_column = TIPRACK_OFFSET + 1
    transfer_tip_column = TIPRACK_OFFSET + 2  # Use next column for transfer if not returning tips

    # Get the actual well references for explicit tip handling
    wash_tip_well = tiprack[f'A{wash_tip_column}']
    transfer_tip_well = tiprack[f'A{transfer_tip_column}'] if not RETURN_TIPS else wash_tip_well

    # Helper function for gentle aspiration from spheroid wells
    def aspirate_from_spheroid(well, volume):
        """Aspirate gently from spheroid well at specified height."""
        p1000.flow_rate.aspirate = VERY_SLOW_FLOW_RATE
        p1000.aspirate(volume, well.bottom(z=SPHEROID_ASPIRATE_HEIGHT))
        if TOUCH_TIP_AFTER_ASPIRATE:
            p1000.touch_tip(well, v_offset=-2)
        p1000.flow_rate.aspirate = DEFAULT_FLOW_RATE

    # Helper function for gentle dispensing into spheroid wells
    def dispense_to_spheroid(well, volume):
        """Dispense gently into spheroid well from high up."""
        p1000.flow_rate.dispense = VERY_SLOW_FLOW_RATE
        p1000.dispense(volume, well.bottom(z=SPHEROID_DISPENSE_HEIGHT))
        if DISPENSE_DELAY > 0:
            protocol.delay(seconds=DISPENSE_DELAY)
        p1000.flow_rate.dispense = DEFAULT_FLOW_RATE

    # =========================================================================
    # WASH CYCLES: Aspirate from spheroids -> waste, then dispense fresh -> spheroids
    # =========================================================================
    p1000.pick_up_tip(wash_tip_well)
    protocol.comment(f"Picked up wash tip from column {wash_tip_column}")

    for wash_num in range(NUM_WASHES):
        protocol.comment(f"=== WASH CYCLE {wash_num + 1} of {NUM_WASHES} ===")

        # Aspirate from all spheroid columns -> waste
        protocol.comment("Aspirating from spheroids...")
        for col in spheroid_columns:
            well = spheroid_plate[f'A{col}']
            aspirate_from_spheroid(well, WASH_VOLUME)
            p1000.dispense(WASH_VOLUME, reservoir['A2'].top(z=-5))
            p1000.blow_out(reservoir['A2'].top(z=-2))

        # Dispense fresh media from reservoir -> all spheroid columns
        protocol.comment("Dispensing fresh media from reservoir...")
        for col in spheroid_columns:
            well = spheroid_plate[f'A{col}']
            p1000.aspirate(WASH_VOLUME, reservoir['A1'])
            dispense_to_spheroid(well, WASH_VOLUME)
            p1000.blow_out(reservoir['A2'].top(z=-2))

    # =========================================================================
    # FINAL TRANSFER: Aspirate from spheroids, then transfer from new media plate
    # =========================================================================
    protocol.comment("=== FINAL TRANSFER ===")

    # Final aspirate from all spheroid columns -> waste
    protocol.comment("Final aspirate from spheroids...")
    for col in spheroid_columns:
        well = spheroid_plate[f'A{col}']
        aspirate_from_spheroid(well, TRANSFER_VOLUME)
        p1000.dispense(TRANSFER_VOLUME, reservoir['A2'].top(z=-5))
        p1000.blow_out(reservoir['A2'].top(z=-2))

    # Return or drop wash tip, pick up transfer tip
    if RETURN_TIPS:
        p1000.return_tip()
        protocol.comment(f"Returned wash tip to column {wash_tip_column}")
        p1000.pick_up_tip(wash_tip_well)  # Re-use same tip
        protocol.comment(f"Picked up tip again from column {wash_tip_column}")
    else:
        p1000.drop_tip()
        protocol.comment("Dropped wash tip")
        p1000.pick_up_tip(transfer_tip_well)
        protocol.comment(f"Picked up transfer tip from column {transfer_tip_column}")

    # Transfer fresh media from new media plate -> spheroid columns
    protocol.comment("Transferring from new media plate...")
    for i, spheroid_col in enumerate(spheroid_columns):
        media_col = new_media_columns[i]
        source_well = new_media_plate[f'A{media_col}']
        dest_well = spheroid_plate[f'A{spheroid_col}']

        # Mix fresh media before aspirating
        p1000.flow_rate.aspirate = DEFAULT_FLOW_RATE
        p1000.flow_rate.dispense = DEFAULT_FLOW_RATE
        p1000.mix(MIX_REPS, MIX_VOLUME, source_well)

        # Aspirate fresh media
        p1000.aspirate(TRANSFER_VOLUME, source_well)

        # Dispense gently into spheroid well
        dispense_to_spheroid(dest_well, TRANSFER_VOLUME)
        p1000.blow_out(dest_well.top(z=-2))

    # Final tip handling
    if RETURN_TIPS:
        p1000.return_tip()
        protocol.comment(f"Returned tip to column {wash_tip_column}")
    else:
        p1000.drop_tip()
        protocol.comment("Dropped transfer tip")

    protocol.comment("=== Media change complete! ===")
