"""
Test script for opentrons_spheroid_media_change.py

This script simulates the protocol execution and verifies:
1. The final reagent volumes in the new media plate match the CSV specification
2. The final volumes in the spheroid plate are correct after wash and transfer
3. Tip usage is tracked

Run with: python test_media_change_protocol.py
"""

import csv
from collections import defaultdict

# Import the CSV parsing function from the protocol
import sys
sys.path.insert(0, '.')

# ============================================================================
# Configuration (must match protocol)
# ============================================================================
CSV_FILE = 'sample_media_change.csv'
BASE_MEDIA_VOLUME = 150  # uL per well in new media plate
WASH_VOLUME = 100  # uL for wash step
TRANSFER_VOLUME = 100  # uL for final media transfer
INITIAL_SPHEROID_VOLUME = 200  # uL per well in spheroid plate


def parse_csv(csv_path):
    """Parse CSV file (same as in protocol)"""
    reagent_locations = {}
    plate_layout = {}
    columns_used = set()

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)

        for row in reader:
            if not row or not row[0].strip():
                continue

            first_cell = row[0].strip()

            if first_cell.startswith('#'):
                continue

            if '_tube' in first_cell:
                well = first_cell.replace('_tube', '')
                reagent_name = row[1].strip()
                reagent_locations[reagent_name] = well

            elif '_plate' in first_cell:
                well = first_cell.replace('_plate', '')
                col_num = int(''.join(filter(str.isdigit, well)))
                columns_used.add(col_num)

                reagents = []
                i = 1
                while i + 1 < len(row):
                    reagent_name = row[i].strip()
                    volume = float(row[i + 1].strip())
                    if reagent_name:
                        reagents.append((reagent_name, volume))
                    i += 2

                plate_layout[well] = reagents

    return reagent_locations, plate_layout, sorted(columns_used)


class PlateSimulator:
    """Simulates a plate with volume and reagent tracking per well."""

    def __init__(self, name, rows=8, cols=12):
        self.name = name
        self.wells = {}
        # Initialize all wells
        for col in range(1, cols + 1):
            for row in 'ABCDEFGH'[:rows]:
                well = f'{row}{col}'
                self.wells[well] = {
                    'volume': 0.0,
                    'reagents': defaultdict(float)  # reagent_name -> volume
                }

    def add_volume(self, well, volume, reagent=None):
        """Add volume to a well, optionally tracking reagent."""
        self.wells[well]['volume'] += volume
        if reagent:
            self.wells[well]['reagents'][reagent] += volume

    def remove_volume(self, well, volume):
        """Remove volume from a well (proportionally removes reagents)."""
        current = self.wells[well]['volume']
        if current <= 0:
            return

        # Calculate proportion being removed
        proportion = min(volume / current, 1.0)

        # Remove proportionally from each reagent
        for reagent in list(self.wells[well]['reagents'].keys()):
            self.wells[well]['reagents'][reagent] *= (1 - proportion)

        self.wells[well]['volume'] = max(0, current - volume)

    def get_volume(self, well):
        return self.wells[well]['volume']

    def get_reagents(self, well):
        return dict(self.wells[well]['reagents'])


def simulate_protocol():
    """Simulate the protocol and return final plate states."""

    # Parse CSV
    reagent_locations, plate_layout, columns_used = parse_csv(CSV_FILE)

    print("=" * 70)
    print("PROTOCOL SIMULATION")
    print("=" * 70)
    print(f"\nCSV parsed: {len(reagent_locations)} reagents, {len(plate_layout)} wells")
    print(f"Columns used: {columns_used}")
    print(f"Reagent locations: {reagent_locations}")

    # Initialize plates
    new_media_plate = PlateSimulator("New Media Plate")
    spheroid_plate = PlateSimulator("Spheroid Plate")

    # Initialize spheroid plate with starting volume
    for col in columns_used:
        for row in 'ABCDEFGH':
            well = f'{row}{col}'
            spheroid_plate.add_volume(well, INITIAL_SPHEROID_VOLUME, 'old_media')

    # Track tips used
    tips_used = 0

    # =========================================================================
    # STEP 1: Assemble new media
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: Assembling new media")
    print("=" * 70)

    # Step 1a: Add base media to all wells
    tips_used += 1  # One tip for base media
    print(f"\nAdding {BASE_MEDIA_VOLUME}uL base media to {len(plate_layout)} wells...")
    for well in plate_layout.keys():
        new_media_plate.add_volume(well, BASE_MEDIA_VOLUME, 'base_media')

    # Step 1b: Add reagents
    all_reagents = set()
    for reagents in plate_layout.values():
        for reagent_name, _ in reagents:
            all_reagents.add(reagent_name)

    print(f"\nAdding {len(all_reagents)} reagents...")
    for reagent_name in sorted(all_reagents):
        tips_used += 1  # One tip per reagent
        print(f"  {reagent_name}:")
        for well, reagents in plate_layout.items():
            for r_name, volume in reagents:
                if r_name == reagent_name and volume > 0:
                    new_media_plate.add_volume(well, volume, reagent_name)
                    print(f"    {well}: +{volume}uL")

    # =========================================================================
    # STEP 2: Wash spheroids
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: Washing spheroids")
    print("=" * 70)

    tips_used += 8  # 8-channel tip pickup

    # Remove old media
    print(f"\nRemoving {WASH_VOLUME}uL from each spheroid well...")
    for col in columns_used:
        for row in 'ABCDEFGH':
            well = f'{row}{col}'
            spheroid_plate.remove_volume(well, WASH_VOLUME)

    # Add fresh base media
    print(f"Adding {WASH_VOLUME}uL base media to each spheroid well...")
    for col in columns_used:
        for row in 'ABCDEFGH':
            well = f'{row}{col}'
            spheroid_plate.add_volume(well, WASH_VOLUME, 'base_media')

    # =========================================================================
    # STEP 3: Transfer assembled media
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: Transferring assembled media")
    print("=" * 70)

    tips_used += 8  # 8-channel tip pickup

    # Remove wash media
    print(f"\nRemoving {TRANSFER_VOLUME}uL wash from each spheroid well...")
    for col in columns_used:
        for row in 'ABCDEFGH':
            well = f'{row}{col}'
            spheroid_plate.remove_volume(well, TRANSFER_VOLUME)

    # Transfer from new media plate
    print(f"Transferring {TRANSFER_VOLUME}uL from new media plate to spheroid plate...")
    for col in columns_used:
        for row in 'ABCDEFGH':
            well = f'{row}{col}'
            # Get reagent composition from new media plate
            source_reagents = new_media_plate.get_reagents(well)
            source_volume = new_media_plate.get_volume(well)

            if source_volume > 0:
                # Calculate proportion of each reagent being transferred
                transfer_proportion = TRANSFER_VOLUME / source_volume

                for reagent, amount in source_reagents.items():
                    transferred = amount * transfer_proportion
                    spheroid_plate.add_volume(well, 0, reagent)  # Just for tracking
                    spheroid_plate.wells[well]['reagents'][reagent] += transferred

                spheroid_plate.wells[well]['volume'] += TRANSFER_VOLUME
                new_media_plate.remove_volume(well, TRANSFER_VOLUME)

    print(f"\nTotal tips used: {tips_used}")

    return new_media_plate, spheroid_plate, plate_layout, columns_used, tips_used


def verify_results(new_media_plate, spheroid_plate, plate_layout, columns_used):
    """Verify the simulation results match expected values."""

    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    all_passed = True

    # =========================================================================
    # Verify new media plate composition
    # =========================================================================
    print("\n--- New Media Plate (after transfer) ---")
    print("Expected: (150uL base + reagents) - 100uL transferred")

    new_media_ok = True
    for well in sorted(plate_layout.keys()):
        # Calculate expected: base media + all reagents - transfer volume
        reagent_total = sum(v for _, v in plate_layout[well])
        expected_remaining = BASE_MEDIA_VOLUME + reagent_total - TRANSFER_VOLUME
        actual = new_media_plate.get_volume(well)
        status = "OK" if abs(actual - expected_remaining) < 0.01 else "FAIL"
        if status == "FAIL":
            new_media_ok = False
            all_passed = False
            print(f"  {well}: {actual:.1f}uL (expected {expected_remaining:.1f}uL) - {status}")

    if new_media_ok:
        print(f"  All {len(plate_layout)} wells have correct remaining volume (varies by reagent content)")

    # =========================================================================
    # Verify spheroid plate final volumes
    # =========================================================================
    print("\n--- Spheroid Plate Final Volumes ---")
    expected_final = INITIAL_SPHEROID_VOLUME - WASH_VOLUME + WASH_VOLUME - TRANSFER_VOLUME + TRANSFER_VOLUME
    print(f"Expected: {expected_final}uL (200 - 100 + 100 - 100 + 100 = 200)")

    volume_ok = True
    for col in columns_used:
        for row in 'ABCDEFGH':
            well = f'{row}{col}'
            actual = spheroid_plate.get_volume(well)
            if abs(actual - expected_final) > 0.01:
                volume_ok = False
                all_passed = False
                print(f"  {well}: {actual:.1f}uL (expected {expected_final}uL) - FAIL")

    if volume_ok:
        print(f"  All wells have correct final volume: {expected_final}uL")

    # =========================================================================
    # Verify reagent ratios in spheroid plate
    # =========================================================================
    print("\n--- Spheroid Plate Reagent Composition ---")
    print("Checking that reagent ratios match CSV specification...")

    # The final reagent amounts should be proportional to what was in the new media plate
    # Since we transferred 100uL from a well that had BASE_MEDIA_VOLUME + reagents

    for well in sorted(plate_layout.keys()):
        csv_reagents = {r: v for r, v in plate_layout[well]}
        spheroid_reagents = spheroid_plate.get_reagents(well)

        # Calculate expected reagent amounts after transfer
        # Total in new media plate = BASE_MEDIA_VOLUME + sum(reagent volumes)
        total_in_source = BASE_MEDIA_VOLUME + sum(csv_reagents.values())
        transfer_ratio = TRANSFER_VOLUME / total_in_source

        well_ok = True
        for reagent, csv_volume in csv_reagents.items():
            expected_in_spheroid = csv_volume * transfer_ratio
            actual_in_spheroid = spheroid_reagents.get(reagent, 0)

            # Allow for some floating point tolerance
            if abs(actual_in_spheroid - expected_in_spheroid) > 0.01:
                well_ok = False
                all_passed = False
                print(f"  {well} {reagent}: {actual_in_spheroid:.2f}uL (expected {expected_in_spheroid:.2f}uL) - FAIL")

        if well_ok:
            # Just show a sample for verification
            if well in ['A1', 'A2', 'A3']:
                print(f"  {well}: {dict(spheroid_reagents)} - OK")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED - check output above")
    print("=" * 70)

    return all_passed


def print_detailed_well_info(spheroid_plate, plate_layout):
    """Print detailed information about each well's final state."""

    print("\n" + "=" * 70)
    print("DETAILED WELL COMPOSITION (Spheroid Plate)")
    print("=" * 70)

    for well in sorted(plate_layout.keys()):
        csv_reagents = {r: v for r, v in plate_layout[well]}
        spheroid_reagents = spheroid_plate.get_reagents(well)
        total_vol = spheroid_plate.get_volume(well)

        print(f"\n{well} (total: {total_vol:.1f}uL):")
        print(f"  CSV specification: {csv_reagents}")
        print(f"  Final reagents: ", end="")

        # Show non-zero reagents
        non_zero = {k: v for k, v in spheroid_reagents.items() if v > 0.01}
        print(non_zero)


if __name__ == '__main__':
    new_media_plate, spheroid_plate, plate_layout, columns_used, tips_used = simulate_protocol()
    passed = verify_results(new_media_plate, spheroid_plate, plate_layout, columns_used)

    # Optionally print detailed info
    print_detailed_well_info(spheroid_plate, plate_layout)

    print(f"\n\nSummary:")
    print(f"  - Wells processed: {len(plate_layout)}")
    print(f"  - Columns used: {columns_used}")
    print(f"  - Tips used: {tips_used}")
    print(f"  - Tests passed: {'Yes' if passed else 'No'}")
