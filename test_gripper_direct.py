#!/usr/bin/env python3
"""
Direct gripper test using HTTP API - No labware pickup required.

This script directly controls the gripper without trying to pick up anything.
Perfect for testing gripper functionality safely.

Usage:
    python test_gripper_direct.py
"""

import requests
import sys
import time


def run_gripper_test(robot_ip: str):
    """Test gripper open/close directly via HTTP API."""
    base_url = f"http://{robot_ip}:31950"
    headers = {
        "Content-Type": "application/json",
        "Opentrons-Version": "3"
    }

    print("=" * 70)
    print("DIRECT GRIPPER TEST")
    print("=" * 70)
    print(f"Robot: {robot_ip}")
    print()

    # Create a run
    print("Creating run...")
    resp = requests.post(
        f"{base_url}/runs",
        json={"data": {}},
        headers=headers
    )
    if resp.status_code >= 400:
        print(f"ERROR: Failed to create run: {resp.text}")
        sys.exit(1)

    run_id = resp.json()["data"]["id"]
    print(f"Run ID: {run_id}")
    print()

    def queue_and_execute(command_type, params, description):
        """Queue a command and execute it."""
        print(f"\n{description}")
        print(f"Command: {command_type}")
        print(f"Params: {params}")

        # Queue the command
        resp = requests.post(
            f"{base_url}/runs/{run_id}/commands",
            json={
                "data": {
                    "commandType": command_type,
                    "params": params,
                    "intent": "protocol"
                }
            },
            headers=headers
        )

        if resp.status_code >= 400:
            print(f"ERROR: {resp.text}")
            return False

        command_id = resp.json()["data"]["id"]
        print(f"Queued: {command_id}")

        # Start the run if this is the first command
        if command_type == "home":
            print("\nStarting run...")
            resp = requests.post(
                f"{base_url}/runs/{run_id}/actions",
                json={"data": {"actionType": "play"}},
                headers=headers
            )
            if resp.status_code >= 400:
                print(f"ERROR: Failed to start run: {resp.text}")
                return False

        # Wait for completion
        for i in range(300):  # 60 second timeout
            resp = requests.get(
                f"{base_url}/runs/{run_id}/commands/{command_id}",
                headers=headers
            )
            data = resp.json()["data"]
            status = data.get("status")

            if status == "succeeded":
                print("✓ Complete")
                return True
            elif status == "failed":
                print(f"✗ Failed: {data.get('error', 'Unknown error')}")
                return False
            elif status in ["queued", "running"]:
                time.sleep(0.2)

        print("✗ Timeout")
        return False

    try:
        # Test sequence
        input("\nPress Enter to start test...")

        # 1. Home
        if not queue_and_execute("home", {}, "Step 1: Homing robot"):
            sys.exit(1)
        input("\n✓ Homed. Press Enter to close gripper...")

        # 2. Close gripper
        if not queue_and_execute(
            "robot/closeGripperJaw",
            {},
            "Step 2: Closing gripper"
        ):
            sys.exit(1)
        input("\n✓ Gripper closed. Press Enter to open gripper...")

        # 3. Open gripper
        if not queue_and_execute(
            "robot/openGripperJaw",
            {},
            "Step 3: Opening gripper"
        ):
            sys.exit(1)

        print("\n" + "=" * 70)
        print("TEST COMPLETE")
        print("=" * 70)
        print("\n✓ All gripper commands executed successfully!")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            requests.delete(
                f"{base_url}/runs/{run_id}",
                headers=headers,
                timeout=10
            )
            print("Run deleted")
        except:
            pass


if __name__ == "__main__":
    robot_ip = "10.90.158.110"
    run_gripper_test(robot_ip)
