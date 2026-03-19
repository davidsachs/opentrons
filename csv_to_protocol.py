#!/usr/bin/env python3
"""
CSV to Protocol Converter

Converts a CSV file with reagent locations and plate layout into Python code
that can be pasted into spheroid_media_change.py

Usage: python csv_to_protocol.py sample_media_change.csv
"""

import csv
import sys


def parse_csv(csv_path):
    """Parse CSV file to extract reagent locations and plate layout."""
    reagent_locations = {}
    plate_layout = {}

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

                reagents = []
                i = 1
                while i + 1 < len(row):
                    reagent_name = row[i].strip()
                    volume = float(row[i + 1].strip())
                    if reagent_name:
                        reagents.append((reagent_name, int(volume) if volume == int(volume) else volume))
                    i += 2

                plate_layout[well] = reagents

    return reagent_locations, plate_layout


def generate_python_code(reagent_locations, plate_layout):
    """Generate Python code for embedding in the protocol."""

    lines = []

    # Reagent locations
    lines.append("# Reagent tube locations in the 24-tube rack")
    lines.append("# Format: reagent_name -> tube well")
    lines.append("REAGENT_LOCATIONS = {")
    for reagent, well in sorted(reagent_locations.items()):
        lines.append(f"    '{reagent}': '{well}',")
    lines.append("}")
    lines.append("")

    # Plate layout
    lines.append("# Plate layout: which reagents and volumes go in each well")
    lines.append("# Format: well -> [(reagent_name, volume_uL), ...]")
    lines.append("PLATE_LAYOUT = {")

    # Sort wells by column then row
    def well_sort_key(well):
        row = well[0]
        col = int(well[1:])
        return (col, row)

    for well in sorted(plate_layout.keys(), key=well_sort_key):
        reagents = plate_layout[well]
        reagent_str = ", ".join(f"('{r}', {v})" for r, v in reagents)
        lines.append(f"    '{well}': [{reagent_str}],")

    lines.append("}")
    lines.append("")

    # Columns used
    lines.append("# Columns used (derived from PLATE_LAYOUT)")
    lines.append("COLUMNS_USED = sorted(set(int(''.join(filter(str.isdigit, well))) for well in PLATE_LAYOUT.keys()))")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python csv_to_protocol.py <csv_file>")
        print("\nThis script converts a CSV file to Python code that can be")
        print("pasted into opentrons_spheroid_media_change.py")
        sys.exit(1)

    csv_path = sys.argv[1]

    try:
        reagent_locations, plate_layout = parse_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    print(f"# Generated from: {csv_path}")
    print(f"# Reagents: {len(reagent_locations)}")
    print(f"# Wells: {len(plate_layout)}")
    print()
    print(generate_python_code(reagent_locations, plate_layout))


if __name__ == '__main__':
    main()
