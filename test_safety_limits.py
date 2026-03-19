#!/usr/bin/env python3
"""Test the safety limit system."""

# Test the check_position_safe function
class MockGUI:
    def __init__(self):
        self.limits = {
            'x': {'min': 0.0, 'max': 470.0},
            'y': {'min': 0.0, 'max': 350.0},
            'z': {'min': 0.0, 'max': 250.0},
        }
        self.current_position = {'x': 100.0, 'y': 100.0, 'z': 100.0}

    def check_position_safe(self, x=None, y=None, z=None):
        """Check if a position is within safe limits."""
        check_x = x if x is not None else self.current_position.get('x', 0)
        check_y = y if y is not None else self.current_position.get('y', 0)
        check_z = z if z is not None else self.current_position.get('z', 0)

        # Check X limits
        if check_x < self.limits['x']['min']:
            return False, f"X={check_x:.1f} below minimum {self.limits['x']['min']:.1f}mm"
        if check_x > self.limits['x']['max']:
            return False, f"X={check_x:.1f} exceeds maximum {self.limits['x']['max']:.1f}mm"

        # Check Y limits
        if check_y < self.limits['y']['min']:
            return False, f"Y={check_y:.1f} below minimum {self.limits['y']['min']:.1f}mm"
        if check_y > self.limits['y']['max']:
            return False, f"Y={check_y:.1f} exceeds maximum {self.limits['y']['max']:.1f}mm"

        # Check Z limits
        if check_z < self.limits['z']['min']:
            return False, f"Z={check_z:.1f} below minimum {self.limits['z']['min']:.1f}mm"
        if check_z > self.limits['z']['max']:
            return False, f"Z={check_z:.1f} exceeds maximum {self.limits['z']['max']:.1f}mm"

        return True, ""


def test_safety_limits():
    gui = MockGUI()

    print("Safety Limit Tests")
    print("=" * 70)

    # Test valid positions
    print("\n[PASS] Valid positions (should PASS):")
    test_cases_pass = [
        (100, 100, 100, "Center of workspace"),
        (0, 0, 0, "Minimum corner"),
        (470, 350, 250, "Maximum corner"),
        (235, 175, 125, "Middle of workspace"),
    ]

    for x, y, z, desc in test_cases_pass:
        is_safe, msg = gui.check_position_safe(x, y, z)
        status = "[PASS]" if is_safe else "[FAIL]"
        print(f"  {status}: X={x}, Y={y}, Z={z} - {desc}")
        if msg:
            print(f"       Error: {msg}")

    # Test invalid positions
    print("\n[FAIL] Invalid positions (should FAIL):")
    test_cases_fail = [
        (-1, 100, 100, "X below minimum"),
        (471, 100, 100, "X above maximum"),
        (100, -1, 100, "Y below minimum"),
        (100, 351, 100, "Y above maximum"),
        (100, 100, -1, "Z below minimum"),
        (100, 100, 251, "Z above maximum"),
        (-10, -10, -10, "All axes below minimum"),
        (500, 400, 300, "All axes above maximum"),
    ]

    for x, y, z, desc in test_cases_fail:
        is_safe, msg = gui.check_position_safe(x, y, z)
        status = "[BLOCKED]" if not is_safe else "[ERROR: Should have blocked]"
        print(f"  {status}: X={x}, Y={y}, Z={z} - {desc}")
        if msg:
            print(f"       Reason: {msg}")

    print("\n" + "=" * 70)
    print("Test complete!")


if __name__ == "__main__":
    test_safety_limits()
