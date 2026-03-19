import requests
import json

protocol_path = 'pickup_and_dip_labware.py'

with open(protocol_path, 'rb') as f:
    content = f.read()
    print(f'File size: {len(content)} bytes')

# Try different upload methods
robot_ip = "10.90.158.110"

print("\n=== Method 1: Single file ===")
with open(protocol_path, 'rb') as f:
    files = {'files': (protocol_path, f)}
    headers = {'Opentrons-Version': '3'}

    response = requests.post(
        f'http://{robot_ip}:31950/protocols',
        files=files,
        headers=headers,
        timeout=60
    )

    print(f'Status: {response.status_code}')
    if response.status_code != 200:
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)

print("\n=== Method 2: With content type ===")
with open(protocol_path, 'rb') as f:
    files = {'files': (protocol_path, f, 'application/octet-stream')}
    headers = {'Opentrons-Version': '3'}

    response = requests.post(
        f'http://{robot_ip}:31950/protocols',
        files=files,
        headers=headers,
        timeout=60
    )

    print(f'Status: {response.status_code}')
    if response.status_code != 200:
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
