#!/usr/bin/env python3
"""Test the logging functionality."""

from pathlib import Path
import time

# Create a minimal test of the _log method
from opentrons_control_gui import OT3ControlGUI

print("Creating GUI instance (this will initialize logging)...")
gui = OT3ControlGUI(robot_ip='10.90.158.110')

# Give threads time to start
time.sleep(1)

# Manually log a test message
gui._log("COMMAND", "Test command logging")

# Stop the GUI
gui.running = False
time.sleep(1)

# Check log file
log_file = Path("log.txt")
if log_file.exists():
    print("\nLog file created successfully!")
    print("\nLog contents:")
    print("=" * 70)
    with open(log_file, 'r') as f:
        print(f.read())
    print("=" * 70)
else:
    print("\nERROR: Log file not created!")
