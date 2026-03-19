#!/usr/bin/env python3
"""Debug analyzer with detailed output."""

import requests
import json
import time
from pathlib import Path

protocol_path = Path("pickup_and_dip_labware.py")
robot_ip = "10.90.158.110"
base_url = f"http://{robot_ip}:31950"

print("Step 1: Upload protocol")
with open(protocol_path, 'rb') as f:
    files = {"files": (protocol_path.name, f, "application/octet-stream")}
    headers = {"Opentrons-Version": "3"}

    resp = requests.post(
        f"{base_url}/protocols",
        files=files,
        headers=headers,
        timeout=60,
    )

    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2)[:500])

protocol_id = data["data"]["id"]
analyses = data["data"].get("analysisSummaries", [])

print(f"\nProtocol ID: {protocol_id}")
print(f"Analysis summaries: {len(analyses)}")

if analyses:
    for i, analysis in enumerate(analyses):
        print(f"  Analysis {i+1}: id={analysis.get('id')}, status={analysis.get('status')}")

    analysis_id = analyses[0]["id"]
    print(f"\nStep 2: Get full analysis for ID: {analysis_id}")

    resp = requests.get(
        f"{base_url}/protocols/{protocol_id}/analyses/{analysis_id}",
        headers={"Opentrons-Version": "3"},
        timeout=30,
    )

    print(f"Status: {resp.status_code}")
    analysis_data = resp.json()["data"]

    print(f"Analysis status: {analysis_data.get('status')}")
    print(f"Commands: {len(analysis_data.get('commands', []))}")

    # If pending, wait
    if analysis_data.get('status') == 'pending':
        print("\nAnalysis is pending, waiting...")

        for i in range(30):
            time.sleep(1)
            resp = requests.get(
                f"{base_url}/protocols/{protocol_id}/analyses/{analysis_id}",
                headers={"Opentrons-Version": "3"},
                timeout=30,
            )
            analysis_data = resp.json()["data"]
            status = analysis_data.get('status')
            print(f"  Check {i+1}: {status}")

            if status == 'completed':
                break

        print(f"\nFinal status: {analysis_data.get('status')}")
        print(f"Commands: {len(analysis_data.get('commands', []))}")

    # Cleanup
    print(f"\nStep 3: Cleanup")
    requests.delete(
        f"{base_url}/protocols/{protocol_id}",
        headers={"Opentrons-Version": "3"},
        timeout=10,
    )
    print("Done")

else:
    print("\nNo analysis summaries found")
