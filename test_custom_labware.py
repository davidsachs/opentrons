#!/usr/bin/env python3
"""Test analysis of reservoir transfer protocol to see custom labware data."""

import json
from analyzer.runner import ProtocolAnalyzer

analyzer = ProtocolAnalyzer()
result = analyzer.analyze('opentrons_reservoir_transfer.py')

print(f'Status: {result.status}')
if result.errors:
    print(f'Errors: {result.errors}')

# Find the loadLabware command for custom labware
for i, cmd in enumerate(result.commands):
    cmd_type = cmd.get('commandType', '')
    if cmd_type == 'loadLabware':
        params = cmd.get('params', {})
        load_name = params.get('loadName', '')
        print(f"\n=== Command {i}: loadLabware ===")
        print(f"loadName: {load_name}")
        print(f"namespace: {params.get('namespace', '')}")
        print(f"Full params keys: {list(params.keys())}")

        # Check result for definition
        result_data = cmd.get('result', {})
        print(f"Result keys: {list(result_data.keys())}")

        if 'definition' in result_data:
            defn = result_data['definition']
            print(f"Definition found! Keys: {list(defn.keys())}")
            print(f"  loadName: {defn.get('parameters', {}).get('loadName', 'N/A')}")
            print(f"  namespace: {defn.get('namespace', 'N/A')}")

# Also check labware list
print("\n=== Labware List ===")
for lw in result.labware:
    if isinstance(lw, dict):
        print(f"  {lw.get('loadName', 'Unknown')}")
        print(f"    Keys: {list(lw.keys())}")
        if 'definition' in lw:
            print(f"    Has definition!")
