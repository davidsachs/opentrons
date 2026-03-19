#!/usr/bin/env python3
"""Test the new feedrate and multi-command functionality."""

# This demonstrates the new features:

# 1. Single-axis movements (unchanged)
# x10      - Move X axis +10mm at default speed (50mm/s)
# y-5      - Move Y axis -5mm at default speed

# 2. Setting feedrate
# f100     - Set feedrate to 100mm/s (affects subsequent moves)
# f25      - Set feedrate to 25mm/s (slower)

# 3. Multi-axis coordinated movements
# x-50 y-50           - Move diagonally (X-50, Y-50) at current feedrate
# x10 y10 z5          - Move all three axes simultaneously
# x-50 y-50 f10       - Move diagonally at 10mm/s
# x100 y50 z-10 f200  - Complex 3D move at 200mm/s

# Example usage sequence:
print("Example command sequences:")
print("=" * 70)
print()
print("1. Slow diagonal move:")
print("   x-50 y-50 f10")
print("   -> Moves X-50mm, Y-50mm at 10mm/s")
print()
print("2. Fast return:")
print("   x50 y50 f200")
print("   -> Moves X+50mm, Y+50mm at 200mm/s")
print()
print("3. Set default speed:")
print("   f75")
print("   -> Sets default feedrate to 75mm/s")
print()
print("4. 3D spiral move:")
print("   x10 y10 z5")
print("   -> Moves all three axes at 75mm/s (current feedrate)")
print()
print("=" * 70)
print()
print("Key features:")
print("- Commands separated by spaces are combined into single move")
print("- F command sets speed for that move AND future moves")
print("- Coordinates are relative (delta from current position)")
print("- Safety limits still apply")
print("- Speed is in mm/s (millimeters per second)")
