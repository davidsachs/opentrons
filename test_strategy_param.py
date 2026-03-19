#!/usr/bin/env python3
"""Test if robot/moveTo accepts a 'strategy' parameter."""

import requests
import json

API_URL = "http://10.90.158.110:31950"

# Create run
resp = requests.post(
    f"{API_URL}/runs",
    json={"data": {}},
    headers={"Content-Type": "application/json", "Opentrons-Version": "3"}
)

if resp.status_code >= 400:
    print(f"Failed to create run: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))
    exit(1)

run_id = resp.json()["data"]["id"]
print(f"Created run: {run_id}")

# Try robot/moveTo with strategy parameter
print("\nTesting robot/moveTo with 'strategy' parameter...")
resp = requests.post(
    f"{API_URL}/runs/{run_id}/commands",
    json={
        "data": {
            "commandType": "robot/moveTo",
            "params": {
                "gripperId": "flex_gripper",
                "mount": "extension",
                "strategy": "direct",  # <-- Testing this
                "destination": {
                    "x": 228.0,
                    "y": 150.0,
                    "z": 50.0
                }
            },
            "intent": "setup"
        }
    },
    headers={"Content-Type": "application/json", "Opentrons-Version": "3"}
)

print(f"Status: {resp.status_code}")
print(f"Response:")
print(json.dumps(resp.json(), indent=2))
