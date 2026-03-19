#!/usr/bin/env python3
"""Check what format commands come back in from analysis."""

import requests
import json
import time

robot_ip = '10.90.158.110'

# Upload a simple protocol
print("Uploading protocol for analysis...")

# Create a test protocol that will work
test_protocol = '''
metadata = {
    "protocolName": "Test Protocol",
    "author": "Test",
    "apiLevel": "2.19",
}

requirements = {
    "robotType": "Flex",
}

def run(protocol):
    tiprack = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "A1")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "A2")
    pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=[tiprack])

    pipette.pick_up_tip()
    pipette.aspirate(100, plate["A1"])
    pipette.dispense(100, plate["B1"])
    pipette.drop_tip()
'''

import tempfile
import os

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(test_protocol)
    temp_path = f.name

try:
    with open(temp_path, 'rb') as f:
        files = {'files': ('test_protocol.py', f)}
        headers = {'Opentrons-Version': '3'}

        resp = requests.post(
            f'http://{robot_ip}:31950/protocols',
            files=files,
            headers=headers,
            timeout=60
        )

    data = resp.json()
    if resp.status_code != 201:
        print(f"Error: {resp.status_code}")
        print(json.dumps(data, indent=2))
        exit(1)
    protocol_id = data['data']['id']
    analysis_id = data['data']['analysisSummaries'][0]['id']

    print(f"Protocol ID: {protocol_id}")
    print(f"Analysis ID: {analysis_id}")

    # Wait for analysis
    print("\nWaiting for analysis to complete...")
    time.sleep(3)

    # Get the analysis
    resp = requests.get(
        f'http://{robot_ip}:31950/protocols/{protocol_id}/analyses/{analysis_id}',
        headers={'Opentrons-Version': '3'},
        timeout=30
    )

    analysis = resp.json()['data']

    print(f"\nAnalysis Status: {analysis.get('status')}")
    print(f"Result: {analysis.get('result')}")
    print(f"Command Count: {len(analysis.get('commands', []))}")

    # Show first few commands in detail
    commands = analysis.get('commands', [])
    print(f"\nFirst 3 commands (full detail):")
    for i, cmd in enumerate(commands[:3], 1):
        print(f"\n--- Command {i} ---")
        print(json.dumps(cmd, indent=2))

    # Now let's try executing an HTTP command and see what it looks like
    print("\n" + "="*70)
    print("HTTP COMMAND EXECUTION TEST")
    print("="*70)

    print("\nCreating a run...")
    resp = requests.post(
        f'http://{robot_ip}:31950/runs',
        json={"data": {}},
        headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
    )
    run_data = resp.json()
    run_id = run_data['data']['id']
    print(f"Run ID: {run_id}")

    print("\nExecuting a simple 'home' command via HTTP...")
    resp = requests.post(
        f'http://{robot_ip}:31950/runs/{run_id}/commands',
        json={
            "data": {
                "commandType": "home",
                "params": {},
                "intent": "protocol"
            }
        },
        params={"waitUntilComplete": "true", "timeout": "30000"},
        headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
    )

    http_command = resp.json()['data']
    print(f"\nHTTP Command Result:")
    print(json.dumps(http_command, indent=2))

    # Compare formats
    print("\n" + "="*70)
    print("COMPARISON")
    print("="*70)
    print("\nAnalysis Command Format:")
    if commands:
        print(json.dumps(commands[0], indent=2)[:500])

    print("\nHTTP Execution Command Format:")
    print(json.dumps(http_command, indent=2)[:500])

    # Cleanup
    print("\nCleaning up...")
    requests.delete(
        f'http://{robot_ip}:31950/protocols/{protocol_id}',
        headers={'Opentrons-Version': '3'},
        timeout=10
    )
    requests.delete(
        f'http://{robot_ip}:31950/runs/{run_id}',
        headers={'Opentrons-Version': '3'},
        timeout=10
    )

    print("Done!")

finally:
    os.unlink(temp_path)
