from opentrons import protocol_api
from opentrons.protocol_api import SINGLE, ALL

metadata = {
    'protocolName': 'Spheroid Media Change from CSV',
    'author': 'David Sachs',
    'description': 'Automated media change protocol that reads reagent layout from CSV',
}

requirements = {
    'robotType': 'Flex',
    'apiLevel': '2.21'
}

# =============================================================================
# LABWARE OFFSETS
# Adjust these if some tips/wells have been used or labware is offset
#
# 96-well plate/tiprack orientation:
#   - COLUMNS (1-12): 12 positions, left-to-right
#   - ROWS (A-H): 8 positions, back-to-front
#   - 8-channel ALL mode: picks up full COLUMN (8 tips) - use column offset
#   - 8-channel SINGLE mode: picks individual tips - use both column and row offset
# =============================================================================

# Tip rack offsets: (columns_to_skip, rows_to_skip)
# Column offset: skip entire columns
# Row offset: skip rows within a column
#
# IMPORTANT for SINGLE tip mode (p50):
#   - Uses start='H1' (front nozzle) so tips must be picked from ROW H only
#   - Tiprack is in slot A1 (back of deck), so pipette approaches from front
#   - Row offset is ignored for SINGLE mode - only column offset applies
#   - Each reagent uses one tip from row H of consecutive columns
#
# For ALL mode (p1000): picks full column of 8 tips, row offset ignored
#
TIPRACK_50_OFFSET = (6,0)  # (columns, rows) for 50uL tips - row ignored in SINGLE mode
TIPRACK_1000_OFFSET = (0, 0)  # (columns, rows) for 1000uL tips (used in ALL mode)

# Plate offsets - skip columns if some have been used
NEW_MEDIA_PLATE_COLUMN_OFFSET = 0      # Skip this many columns from the left
SPHEROID_PLATE_COLUMN_OFFSET = 0       # Skip this many columns from the left

# Tube rack offset - which tube position to start from (if some tubes used)
# Format: (columns_to_skip, rows_to_skip) - 24-tube rack is 6 cols x 4 rows
TUBE_RACK_OFFSET = (0, 0)  # (columns, rows) - e.g., (1, 0) starts at column 2
TUBE_RACK_NOTES = "All tubes in use"   # For your reference

# =============================================================================
# SPHEROID PLATE SLOT OFFSET
# Adjust these to fine-tune the spheroid plate position in slot C3
# Uses set_offset() on standard labware - no custom definition needed
# All values are in mm
# =============================================================================

SPHEROID_PLATE_X_OFFSET = 42.25   # mm: positive = right, negative = left
SPHEROID_PLATE_Y_OFFSET = 0.0   # mm: positive = back, negative = front
SPHEROID_PLATE_Z_OFFSET = 0.0   # mm: positive = up, negative = down

# =============================================================================
# CUSTOM LABWARE DEFINITION - 2-Well Reservoir
# A1 = New media source, A2 = Waste
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

# =============================================================================
# EMBEDDED CSV DATA
# To use a different layout, modify these dictionaries directly
# =============================================================================

# Reagent tube locations in the 24-tube rack
# Format: reagent_name -> tube well
REAGENT_LOCATIONS = {
    'activin_a': 'A1',
    'bmp4': 'A2',
    'fgf': 'A3',
    'chir': 'A4',
    'ascorbic_acid': 'A5',
}

# Plate layout: which reagents and volumes go in each well
# Format: well -> [(reagent_name, volume_uL), ...]
PLATE_LAYOUT = {
    'A1': [('activin_a', 1), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'B1': [('activin_a', 1), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'C1': [('activin_a', 2), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'D1': [('activin_a', 2), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'E1': [('activin_a', 3), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'F1': [('activin_a', 3), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'G1': [('activin_a', 4), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'H1': [('activin_a', 4), ('bmp4', 1), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'A2': [('activin_a', 1), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'B2': [('activin_a', 1), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'C2': [('activin_a', 2), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'D2': [('activin_a', 2), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'E2': [('activin_a', 3), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'F2': [('activin_a', 3), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'G2': [('activin_a', 4), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'H2': [('activin_a', 4), ('bmp4', 2), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'A3': [('activin_a', 1), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'B3': [('activin_a', 1), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'C3': [('activin_a', 2), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'D3': [('activin_a', 2), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'E3': [('activin_a', 3), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'F3': [('activin_a', 3), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'G3': [('activin_a', 4), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
    'H3': [('activin_a', 4), ('bmp4', 3), ('chir', 1), ('ascorbic_acid', 1), ('fgf', 1)],
}

# Columns used (derived from PLATE_LAYOUT)
COLUMNS_USED = sorted(set(int(''.join(filter(str.isdigit, well))) for well in PLATE_LAYOUT.keys()))

# =============================================================================
# Protocol Parameters
# =============================================================================

# Flow rates (uL/s)
SLOW_FLOW_RATE = 50  # For spheroid wells - gentle to avoid disturbing spheroids
DEFAULT_FLOW_RATE = 160  # For non-spheroid operations

# Volumes
BASE_MEDIA_VOLUME = 150  # uL per well in new media plate
WASH_VOLUME = 100  # uL for wash step
TRANSFER_VOLUME = 100  # uL for final media transfer

# Disposal volume for accuracy - extra liquid aspirated to ensure accurate dispenses
# This liquid is blown out after dispensing. Default is pipette minimum volume.
# Using 10-20uL improves accuracy without excessive waste.
DISPOSAL_VOLUME_P1000 = 20  # uL for p1000 operations
DISPOSAL_VOLUME_P50 = 5     # uL for p50 operations (smaller due to lower volumes)

# Mixing parameters
REAGENT_MIX_REPS = 3  # Number of mix cycles for reagent tubes
REAGENT_MIX_VOLUME = 100  # uL to mix in reagent tubes
MEDIA_MIX_REPS = 3  # Number of mix cycles for assembled media
MEDIA_MIX_VOLUME = 100  # uL to mix in media wells


def run(protocol: protocol_api.ProtocolContext):
    # Use embedded data
    reagent_locations = REAGENT_LOCATIONS
    plate_layout = PLATE_LAYOUT
    columns_used = COLUMNS_USED

    protocol.comment(f"Layout: {len(reagent_locations)} reagents, {len(plate_layout)} wells, columns {columns_used}")
    protocol.comment(f"Using custom 2-well reservoir: A1=media, A2=waste")
    if SPHEROID_PLATE_X_OFFSET != 0 or SPHEROID_PLATE_Y_OFFSET != 0 or SPHEROID_PLATE_Z_OFFSET != 0:
        protocol.comment(f"Spheroid plate offset: X={SPHEROID_PLATE_X_OFFSET}, Y={SPHEROID_PLATE_Y_OFFSET}, Z={SPHEROID_PLATE_Z_OFFSET}")

    # Load trash bin
    trash = protocol.load_trash_bin('A3')

    # ==========================================================================
    # DECK LAYOUT:
    # For A1 nozzle partial tip pickup:
    #   - Pipette body extends toward D-row (front)
    #   - Tip rack in A-row for A1 nozzle pickup
    #   - Labware for partial tip work in C-row (no conflict with A-row pickup)
    #
    #   A1: 50uL filter tips (for partial tip pickup with A1 nozzle)
    #   A3: Trash
    #   B1: Reagent Tubes (24-tube rack)
    #   B3: 1000uL filter tips (for bulk operations with right pipette)
    #   C2: New Media Assembly Plate
    #   C3: Spheroid Plate (standard labware with slot offset)
    #   D1: Custom 2-Well Reservoir (A1=media, A2=waste)
    # ==========================================================================

    # Load labware
    # 50uL tips in A1 for A1 single-nozzle pickup
    tiprack_50 = protocol.load_labware('opentrons_flex_96_filtertiprack_50ul', 'B1',
                                        label='50uL Tips (Reagents)')
    tiprack_1000 = protocol.load_labware('opentrons_flex_96_filtertiprack_1000ul', 'B2',
                                          label='1000uL Tips (Bulk)')

    # Tube rack in B1
    tube_rack = protocol.load_labware(
        'opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap',
        'D2',
        label='Reagent Tubes'
    )

    # Custom 2-well reservoir in D1: A1=new media, A2=waste
    reservoir = protocol.load_labware_from_definition(
        CUSTOM_2_RESERVOIR_DEF,
        'C1',
        label='Media/Waste Reservoir'
    )

    # Standard spheroid plate with slot offset applied
    spheroid_plate = protocol.load_labware(
        'corning_96_wellplate_360ul_flat',
        'C3',
        label='Spheroid Plate'
    )
    # Apply offset to adjust plate position in slot
    spheroid_plate.set_offset(
        x=SPHEROID_PLATE_X_OFFSET,
        y=SPHEROID_PLATE_Y_OFFSET,
        z=SPHEROID_PLATE_Z_OFFSET
    )

    # New media plate (standard labware)
    new_media_plate = protocol.load_labware(
        'corning_96_wellplate_360ul_flat',
        'D3',
        label='New Media Plate'
    )

    # Load pipettes
    # Right mount: 8-channel 1000uL for bulk media operations
    p1000_multi = protocol.load_instrument('flex_8channel_1000', 'right', tip_racks=[tiprack_1000])
    # Left mount: 8-channel 50uL for precise reagent dispensing
    p50_multi = protocol.load_instrument('flex_8channel_50', 'left', tip_racks=[tiprack_50])

    # Apply tip rack offsets - tell pipettes where to start picking up tips
    # For 1000uL tips (ALL mode): use starting_tip
    if TIPRACK_1000_OFFSET[0] > 0:
        start_col_1000 = TIPRACK_1000_OFFSET[0] + 1  # Convert to 1-indexed
        p1000_multi.starting_tip = tiprack_1000[f'A{start_col_1000}']
        protocol.comment(f"1000uL tips starting at column {start_col_1000}")

    # For 50uL tips (SINGLE mode with start='A1'): track tip position manually
    tip_50_start_col = TIPRACK_50_OFFSET[0]
    tip_50_current_col = tip_50_start_col

    def get_next_50ul_tip():
        """Get the next available 50uL tip well from row A and increment counter."""
        nonlocal tip_50_current_col
        col = tip_50_current_col + 1  # 1-indexed column
        tip_50_current_col += 1
        return f'A{col}'  # Always row A for SINGLE mode with start='A1'

    if tip_50_start_col > 0:
        protocol.comment(f"50uL tips starting at column {tip_50_start_col + 1} (A{tip_50_start_col + 1})")

    # =========================================================================
    # STEP 1: Assemble new media in the empty plate
    # =========================================================================
    protocol.comment("=== STEP 1: Assembling new media ===")

    # -------------------------------------------------------------------------
    # Step 1a: Add base media to all columns using 8-channel p1000 (PARALLEL)
    # Uses distribute() with disposal_volume for accuracy and efficiency
    # -------------------------------------------------------------------------
    protocol.comment("Adding base media to all columns (8-channel p1000)...")

    # Configure p1000 for 8-channel mode for base media
    p1000_multi.configure_nozzle_layout(
        style=ALL,
        tip_racks=[tiprack_1000]
    )

    # Build destination list for distribute (column A wells)
    base_media_destinations = [new_media_plate[f'A{col}'] for col in columns_used]

    # Use distribute() for efficient multi-dispense with single aspirate
    # disposal_volume ensures accurate dispenses; blowout goes to source to conserve media
    # trash=False returns tip to rack instead of dropping in trash
    p1000_multi.distribute(
        volume=BASE_MEDIA_VOLUME,
        source=reservoir['A1'],
        dest=base_media_destinations,
        disposal_volume=DISPOSAL_VOLUME_P1000,
        blow_out=True,
        blowout_location='source well',  # Return disposal volume to reservoir
        new_tip='once',  # Single tip for all dispenses
        trash=False  # Return tip to rack instead of trash
    )

    # -------------------------------------------------------------------------
    # Step 1b: Add reagents using p50 SINGLE tip mode with distribute()
    # Uses distribute() with disposal_volume for accuracy; one tip per reagent
    # -------------------------------------------------------------------------
    protocol.comment("Adding reagents to wells (p50 single tip, distribute)...")

    # Configure p50 for single tip mode
    p50_multi.configure_nozzle_layout(
        style=SINGLE,
        start='H1',
        tip_racks=[tiprack_50]
    )

    # Get unique reagents
    all_reagents = set()
    for well, reagents in plate_layout.items():
        for reagent_name, volume in reagents:
            all_reagents.add(reagent_name)

    for reagent_name in sorted(all_reagents):
        if reagent_name not in reagent_locations:
            protocol.comment(f"WARNING: Reagent {reagent_name} not found in tube rack!")
            continue

        tube_well = reagent_locations[reagent_name]
        protocol.comment(f"Distributing {reagent_name} from tube {tube_well}")

        # Pick up tip manually so we can mix first
        tip_well = get_next_50ul_tip()
        p50_multi.pick_up_tip(tiprack_50[tip_well])

        # Mix the reagent tube first to ensure homogeneity
        p50_multi.mix(REAGENT_MIX_REPS, 30, tube_rack[tube_well])

        # Build list of (well, volume) for this reagent, grouped by volume
        # distribute() works best when all dispenses are the same volume,
        # so we group by volume and do multiple distribute calls if needed
        volume_groups = {}
        for well, reagents in plate_layout.items():
            for r_name, volume in reagents:
                if r_name == reagent_name and volume > 0:
                    if volume not in volume_groups:
                        volume_groups[volume] = []
                    volume_groups[volume].append(well)

        # Sort wells within each group for efficient movement
        def well_sort_key(well):
            row = well[0]
            col = int(well[1:])
            return (col, row)

        for volume, wells in sorted(volume_groups.items()):
            wells.sort(key=well_sort_key)
            destinations = [new_media_plate[w] for w in wells]

            # Use distribute() - aspirates once, dispenses multiple times
            # Disposal volume blown back to source tube to conserve reagent
            p50_multi.distribute(
                volume=volume,
                source=tube_rack[tube_well],
                dest=destinations,
                disposal_volume=DISPOSAL_VOLUME_P50,
                blow_out=True,
                blowout_location='source well',  # Return to tube to conserve reagent
                new_tip='never'  # Already have tip
            )

        p50_multi.drop_tip()  # Cannot return tips in SINGLE/partial tip mode

    # =========================================================================
    # STEP 2: Wash spheroids with base media (8-channel p1000)
    # Uses slow flow rate to avoid disturbing spheroids
    # =========================================================================
    protocol.comment("=== STEP 2: Washing spheroids with base media ===")

    # Configure p1000 for 8-channel mode
    p1000_multi.configure_nozzle_layout(
        style=ALL,
        tip_racks=[tiprack_1000]
    )

    # Build source/dest lists for consolidate/distribute
    spheroid_sources = [spheroid_plate[f'A{col}'] for col in columns_used]

    # Step 2a: Remove old media from all columns -> waste (A2)
    # Using consolidate() with slow aspirate rate
    protocol.comment("Removing old media from spheroid plate...")

    # Set slow flow rate for aspirating from spheroid wells
    p1000_multi.flow_rate.aspirate = SLOW_FLOW_RATE

    p1000_multi.consolidate(
        volume=WASH_VOLUME,
        source=spheroid_sources,
        dest=reservoir['A2'],
        disposal_volume=0,  # No disposal needed for waste consolidation
        blow_out=True,
        blowout_location='destination well',
        new_tip='once',
        trash=False  # Return tip to rack
    )

    # Step 2b: Add fresh base media from A1 to all columns
    # Using distribute() with slow dispense rate
    protocol.comment("Adding fresh base media to spheroid plate...")

    # Set flow rates: normal aspirate, slow dispense for spheroids
    p1000_multi.flow_rate.aspirate = DEFAULT_FLOW_RATE
    p1000_multi.flow_rate.dispense = SLOW_FLOW_RATE

    p1000_multi.distribute(
        volume=WASH_VOLUME,
        source=reservoir['A1'],
        dest=spheroid_sources,
        disposal_volume=DISPOSAL_VOLUME_P1000,
        blow_out=True,
        blowout_location='source well',  # Conserve media
        new_tip='once',
        trash=False  # Return tip to rack
    )

    # Reset flow rates
    p1000_multi.flow_rate.aspirate = DEFAULT_FLOW_RATE
    p1000_multi.flow_rate.dispense = DEFAULT_FLOW_RATE

    # =========================================================================
    # STEP 3: Transfer assembled media to spheroids (8-channel mode)
    # Uses slow flow rates when interacting with spheroid wells
    # =========================================================================
    protocol.comment("=== STEP 3: Transferring assembled media to spheroids ===")

    # Step 3a: Remove wash media from all columns -> waste (A2)
    # Using consolidate() with slow aspirate rate
    protocol.comment("Removing wash media from spheroid plate...")

    # Set slow flow rate for aspirating from spheroid wells
    p1000_multi.flow_rate.aspirate = SLOW_FLOW_RATE

    p1000_multi.consolidate(
        volume=TRANSFER_VOLUME,
        source=spheroid_sources,
        dest=reservoir['A2'],
        disposal_volume=0,  # No disposal needed for waste consolidation
        blow_out=True,
        blowout_location='destination well',
        new_tip='once',
        trash=False  # Return tip to rack
    )

    # Reset aspirate rate for mixing
    p1000_multi.flow_rate.aspirate = DEFAULT_FLOW_RATE

    # Step 3b: Mix and transfer assembled media to spheroids
    # Using transfer() with mix_before for each well
    protocol.comment("Transferring assembled media to spheroid plate...")

    # Set slow dispense rate for spheroid wells
    p1000_multi.flow_rate.dispense = SLOW_FLOW_RATE

    # Build paired source/dest lists    
    media_sources = [new_media_plate[f'A{col}'] for col in columns_used]

    p1000_multi.transfer(
        volume=TRANSFER_VOLUME,
        source=media_sources,
        dest=spheroid_sources,
        mix_before=(MEDIA_MIX_REPS, MEDIA_MIX_VOLUME),  # Mix assembled media before aspirating
        disposal_volume=DISPOSAL_VOLUME_P1000,
        blow_out=True,
        blowout_location='source well',  # Return disposal to media plate
        new_tip='once',
        trash=False  # Return tip to rack
    )

    # Reset flow rates
    p1000_multi.flow_rate.aspirate = DEFAULT_FLOW_RATE
    p1000_multi.flow_rate.dispense = DEFAULT_FLOW_RATE

    protocol.comment("=== Protocol complete! ===")
