#!/usr/bin/env python3
"""Debug script to see why the protocol upload is failing."""

import requests
import json
import sys

robot_ip = "10.90.158.110"

print("Attempting to upload protocol to robot analyzer...")
print(f"Robot IP: {robot_ip}")
print()

try:
    with open('pickup_and_dip_labware.py', 'rb') as f:
        files = {'files': ('pickup_and_dip_labware.py', f, 'application/octet-stream')}
        headers = {'Opentrons-Version': '3'}

        response = requests.post(
            f'http://{robot_ip}:31950/protocols',
            files=files,
            headers=headers,
            timeout=60
        )

        print(f'Status Code: {response.status_code}')
        print(f'Response:')
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)

        if response.status_code != 200:
            print("\n❌ Upload failed!")
            sys.exit(1)
        else:
            print("\n✅ Upload successful!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
