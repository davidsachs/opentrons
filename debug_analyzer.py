#!/usr/bin/env python3
"""Debug what's happening with the analyzer."""

from pathlib import Path
from analyzer.runner import ProtocolAnalyzer

protocol_path = Path("pickup_and_dip_labware.py")
robot_ip = "10.90.158.110"

print(f"Analyzing: {protocol_path}")
print(f"Robot: {robot_ip}")
print()

analyzer = ProtocolAnalyzer(robot_ip=robot_ip, use_local=False)

try:
    result = analyzer.analyze(protocol_path)

    print(f"Status: {result.status}")
    print(f"Commands: {len(result.commands)}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")

    if result.raw_result:
        import json
        print("\nRaw result:")
        print(json.dumps(result.raw_result, indent=2)[:1000])

except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
