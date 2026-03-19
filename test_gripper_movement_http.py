#!/usr/bin/env python3
"""
HTTP API version of gripper movement test - with manual pauses between commands.

This script sends atomic HTTP commands to the robot, waiting for Enter
between each command. This allows you to insert adjustments between commands.

Usage:
    python test_gripper_movement_http.py

The script will:
1. Create a run
2. Send each command individually
3. Wait for you to press Enter before the next command
4. Execute commands atomically on the robot
"""

import requests
import sys
import json
from typing import Dict, Any


class AtomicHTTPRunner:
    """Runs HTTP commands atomically with manual confirmation between steps."""

    def __init__(self, robot_ip: str, port: int = 31950):
        self.robot_ip = robot_ip
        self.port = port
        self.base_url = f"http://{robot_ip}:{port}"
        self.run_id = None
        self.command_count = 0

    def create_run(self) -> str:
        """Create a new run and return its ID."""
        print("=" * 70)
        print("Creating run...")
        print("=" * 70)

        resp = requests.post(
            f"{self.base_url}/runs",
            json={"data": {}},
            headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
        )

        if resp.status_code >= 400:
            print(f"ERROR: Failed to create run: {resp.text}")
            sys.exit(1)

        data = resp.json()
        self.run_id = data["data"]["id"]
        print(f"Created run: {self.run_id}\n")
        return self.run_id

    def queue_command(self, command_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Queue a command and return the response."""
        self.command_count += 1

        print(f"\n{'=' * 70}")
        print(f"Command {self.command_count}: {command_type}")
        print(f"{'=' * 70}")
        print(f"Parameters: {json.dumps(params, indent=2)}")

        resp = requests.post(
            f"{self.base_url}/runs/{self.run_id}/commands",
            json={
                "data": {
                    "commandType": command_type,
                    "params": params,
                    "intent": "protocol",
                }
            },
            headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
        )

        if resp.status_code >= 400:
            print(f"\nERROR: Command failed")
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
            sys.exit(1)

        result = resp.json()
        command_id = result["data"]["id"]
        print(f"Command queued: {command_id}")

        return result["data"]

    def wait_for_command(self, command_id: str) -> None:
        """Poll until command completes."""
        print(f"Waiting for command to complete...")

        import time

        for i in range(300):  # 5 minute timeout
            resp = requests.get(
                f"{self.base_url}/runs/{self.run_id}/commands/{command_id}",
                headers={"Opentrons-Version": "3"},
            )

            if resp.status_code >= 400:
                print(f"ERROR: Failed to get command status: {resp.text}")
                sys.exit(1)

            data = resp.json()["data"]
            status = data.get("status")

            if status == "succeeded":
                print(f"Command completed successfully!")
                return
            elif status == "failed":
                print(f"ERROR: Command failed")
                print(f"Error: {data.get('error', 'Unknown error')}")
                sys.exit(1)
            elif status in ["queued", "running"]:
                # Still executing
                time.sleep(0.2)
            else:
                print(f"Unknown status: {status}")
                time.sleep(0.2)

        print("ERROR: Command timed out")
        sys.exit(1)

    def execute_command(self, command_type: str, params: Dict[str, Any]) -> None:
        """Queue a command and wait for it to execute."""
        cmd_data = self.queue_command(command_type, params)
        command_id = cmd_data["id"]

        # Start the run if not already started
        if self.command_count == 1:
            print(f"\nStarting run {self.run_id}...")
            resp = requests.post(
                f"{self.base_url}/runs/{self.run_id}/actions",
                json={"data": {"actionType": "play"}},
                headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
            )
            if resp.status_code >= 400:
                print(f"ERROR: Failed to start run: {resp.text}")
                sys.exit(1)
            print("Run started!")

        self.wait_for_command(command_id)

    def pause_for_user(self, message: str = "Press Enter to continue...") -> None:
        """Pause and wait for user to press Enter."""
        print(f"\n{'-' * 70}")
        try:
            input(message)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Cleaning up...")
            self.cleanup()
            sys.exit(130)

    def cleanup(self) -> None:
        """Delete the run."""
        if self.run_id:
            print(f"\nCleaning up run {self.run_id}...")
            try:
                requests.delete(
                    f"{self.base_url}/runs/{self.run_id}",
                    headers={"Opentrons-Version": "3"},
                    timeout=10,
                )
                print("Run deleted.")
            except Exception as e:
                print(f"Warning: Failed to delete run: {e}")


def run_protocol(robot_ip: str):
    """Execute the gripper movement protocol."""
    runner = AtomicHTTPRunner(robot_ip)

    try:
        # Create run
        runner.create_run()

        print("\n" + "=" * 70)
        print("PROTOCOL: Gripper Movement Test")
        print("=" * 70)
        print("\nThis protocol will:")
        print("  1. Home the robot")
        print("  2. Move gantry to X:220, Y:220, Z:164")
        print("  3. Close the gripper")
        print("  4. Open the gripper")
        print("\nYou will be prompted before each command.")
        print("=" * 70)

        runner.pause_for_user("\nPress Enter to start...")

        # Command 1: Home
        runner.execute_command("home", {})
        runner.pause_for_user("\n✓ Homed. Press Enter to move to position...")

        # Command 2: Move to coordinates
        runner.execute_command(
            "robot/moveTo",
            {
                "position": {"x": 220.0, "y": 220.0, "z": 164.0},
            },
        )
        runner.pause_for_user("\n✓ Moved to position. Press Enter to close gripper...")

        # Command 3: Close gripper
        runner.execute_command("robot/closeGripperJaw", {})
        runner.pause_for_user("\n✓ Gripper closed. Press Enter to open gripper...")

        # Command 4: Open gripper
        runner.execute_command("robot/openGripperJaw", {})

        print("\n" + "=" * 70)
        print("PROTOCOL COMPLETE")
        print("=" * 70)
        print("\nAll commands executed successfully!")

    except KeyboardInterrupt:
        print("\n\nProtocol interrupted by user.")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        runner.cleanup()


def main():
    """Main entry point."""
    robot_ip = "10.90.158.110"

    print("=" * 70)
    print("ATOMIC HTTP PROTOCOL RUNNER")
    print("=" * 70)
    print(f"Robot: {robot_ip}")
    print(f"Mode: Manual execution with pauses")
    print("=" * 70)

    run_protocol(robot_ip)


if __name__ == "__main__":
    main()
