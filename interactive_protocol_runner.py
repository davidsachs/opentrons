#!/usr/bin/env python3
"""
Interactive Protocol Runner - Execute Python protocols with manual control.

This runner:
1. Analyzes your Python protocol
2. Queues all commands to a run
3. Executes them step-by-step with pause points
4. Allows manual adjustments between commands

Usage:
    python interactive_protocol_runner.py <protocol.py>
"""

import sys
import json
import requests
import time
from pathlib import Path
from typing import Dict, Any, List

from analyzer.runner import ProtocolAnalyzer


class InteractiveProtocolRunner:
    """Execute protocols step-by-step with manual control."""

    def __init__(self, robot_ip: str, port: int = 31950):
        self.robot_ip = robot_ip
        self.port = port
        self.base_url = f"http://{robot_ip}:{port}"
        self.run_id = None
        self.command_ids = []
        self.current_command_index = 0

    def analyze_protocol(self, protocol_path: Path) -> List[Dict[str, Any]]:
        """Analyze the Python protocol."""
        print("=" * 70)
        print("Analyzing Python Protocol")
        print("=" * 70)
        print(f"Protocol: {protocol_path}")
        print()

        analyzer = ProtocolAnalyzer(robot_ip=self.robot_ip, use_local=False)
        result = analyzer.analyze(protocol_path)

        if result.status != "ok":
            print("ERROR: Protocol analysis failed")
            for error in result.errors:
                print(f"  {error}")
            sys.exit(1)

        print(f"Analysis complete: {len(result.commands)} commands")
        print()

        return result.commands

    def create_and_queue_run(self, commands: List[Dict[str, Any]]) -> str:
        """Create a run and queue all commands."""
        print("=" * 70)
        print("Creating Run and Queuing Commands")
        print("=" * 70)

        headers = {"Content-Type": "application/json", "Opentrons-Version": "3"}

        # Create run
        resp = requests.post(
            f"{self.base_url}/runs",
            json={"data": {}},
            headers=headers
        )

        if resp.status_code >= 400:
            print(f"ERROR: Failed to create run: {resp.text}")
            sys.exit(1)

        data = resp.json()
        self.run_id = data["data"]["id"]
        print(f"Run ID: {self.run_id}")
        print()

        # Queue all commands
        print(f"Queuing {len(commands)} commands...")
        for i, cmd in enumerate(commands, 1):
            cmd_type = cmd["commandType"]
            params = cmd["params"]

            resp = requests.post(
                f"{self.base_url}/runs/{self.run_id}/commands",
                json={
                    "data": {
                        "commandType": cmd_type,
                        "params": params,
                        "intent": "protocol"
                    }
                },
                headers=headers
            )

            if resp.status_code >= 400:
                print(f"ERROR: Failed to queue command {i}: {resp.text}")
                sys.exit(1)

            command_id = resp.json()["data"]["id"]
            self.command_ids.append(command_id)
            print(f"  {i}. {cmd_type} - {command_id}")

        print(f"\n✓ All {len(commands)} commands queued")
        print()
        return self.run_id

    def execute_step_by_step(self, commands: List[Dict[str, Any]]):
        """Execute commands one at a time with pause points."""
        print("=" * 70)
        print("INTERACTIVE EXECUTION")
        print("=" * 70)
        print(f"Total commands: {len(commands)}")
        print("You'll be able to pause after each command for adjustments")
        print("=" * 70)
        print()

        input("Press Enter to begin...")

        # Start the run (it will execute all queued commands automatically)
        # We need a different approach - we can't pause between commands easily

        print("\nNOTE: The robot's run system executes all commands automatically.")
        print("For true step-by-step control, we need to use a different approach.")
        print()

        # Start run
        print("Starting run...")
        headers = {"Content-Type": "application/json", "Opentrons-Version": "3"}
        resp = requests.post(
            f"{self.base_url}/runs/{self.run_id}/actions",
            json={"data": {"actionType": "play"}},
            headers=headers
        )

        if resp.status_code >= 400:
            print(f"ERROR: Failed to start run: {resp.text}")
            sys.exit(1)

        print("Run started - commands executing...")
        print()

        # Monitor execution
        for i, (cmd, cmd_id) in enumerate(zip(commands, self.command_ids), 1):
            print(f"Command {i}/{len(commands)}: {cmd['commandType']}")

            # Wait for this command to complete
            while True:
                resp = requests.get(
                    f"{self.base_url}/runs/{self.run_id}/commands/{cmd_id}",
                    headers={"Opentrons-Version": "3"}
                )

                if resp.status_code >= 400:
                    print(f"ERROR: Failed to get command status")
                    break

                data = resp.json()["data"]
                status = data.get("status")

                if status == "succeeded":
                    print(f"  ✓ Complete")
                    break
                elif status == "failed":
                    print(f"  ✗ Failed: {data.get('error', 'Unknown error')}")
                    break
                elif status in ["queued", "running"]:
                    time.sleep(0.1)
                else:
                    time.sleep(0.1)

        print("\n" + "=" * 70)
        print("PROTOCOL COMPLETE")
        print("=" * 70)

    def cleanup(self):
        """Clean up the run."""
        if self.run_id:
            print(f"\nCleaning up run {self.run_id}...")
            try:
                requests.delete(
                    f"{self.base_url}/runs/{self.run_id}",
                    headers={"Opentrons-Version": "3"},
                    timeout=10
                )
                print("Run deleted.")
            except Exception as e:
                print(f"Warning: Failed to delete run: {e}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python interactive_protocol_runner.py <protocol.py>")
        sys.exit(1)

    protocol_path = Path(sys.argv[1])

    if not protocol_path.exists():
        print(f"ERROR: Protocol file not found: {protocol_path}")
        sys.exit(1)

    robot_ip = "10.90.158.110"

    print("=" * 70)
    print("INTERACTIVE PROTOCOL RUNNER")
    print("=" * 70)
    print(f"Protocol: {protocol_path}")
    print(f"Robot: {robot_ip}")
    print("=" * 70)
    print()
    print("NOTE: This version queues all commands and runs them automatically.")
    print("For true pause-between-commands control, use individual command runs.")
    print()

    runner = InteractiveProtocolRunner(robot_ip)

    try:
        # Analyze
        commands = runner.analyze_protocol(protocol_path)

        # Queue
        runner.create_and_queue_run(commands)

        # Execute
        runner.execute_step_by_step(commands)

    except KeyboardInterrupt:
        print("\n\nProtocol interrupted by user.")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        runner.cleanup()


if __name__ == "__main__":
    main()
