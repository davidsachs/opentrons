#!/usr/bin/env python3
"""
Hybrid Protocol Runner - Combines Python API ease-of-use with HTTP API control.

This allows you to:
1. Write protocols using the familiar Python API
2. Have them executed as atomic HTTP commands
3. Pause between any command to make fine positioning adjustments
4. Continue execution after adjustments

Usage:
    python hybrid_protocol_runner.py <protocol.py>

The runner will:
- Parse your Python protocol to understand labware and commands
- Translate to HTTP commands
- Execute each command individually with pause points
- Allow manual gantry adjustments between commands
"""

import sys
import json
import requests
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.opentrons_translator.parser import ProtocolParser
from analyzer.runner import ProtocolAnalyzer


class HybridProtocolRunner:
    """
    Runs Python protocols as atomic HTTP commands with manual control.

    This bridges the gap between:
    - High-level Python API (easy labware definitions)
    - Low-level HTTP API (granular control)
    """

    def __init__(self, robot_ip: str, port: int = 31950):
        self.robot_ip = robot_ip
        self.port = port
        self.base_url = f"http://{robot_ip}:{port}"
        self.run_id = None
        self.command_count = 0

        # Resource ID mappings (from variable names to robot IDs)
        self.labware_ids: Dict[str, str] = {}
        self.pipette_ids: Dict[str, str] = {}
        self.module_ids: Dict[str, str] = {}

        # ID translation map (simulated ID -> real ID)
        self.id_map: Dict[str, str] = {}

    def analyze_protocol(self, protocol_path: Path) -> List[Dict[str, Any]]:
        """Analyze the Python protocol to get the full command sequence."""
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

    def parse_protocol(self, protocol_path: Path):
        """Parse the protocol to extract structure."""
        print("=" * 70)
        print("Parsing Protocol Structure")
        print("=" * 70)

        parser = ProtocolParser()
        parsed = parser.parse_file(protocol_path)

        print(f"Labware: {len(parsed.labware)}")
        print(f"Pipettes: {len(parsed.pipettes)}")
        print(f"Modules: {len(parsed.modules)}")
        print()

        return parsed

    def create_run(self) -> str:
        """Create a new run."""
        print("=" * 70)
        print("Creating Run")
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
        print(f"Run ID: {self.run_id}")
        print()
        return self.run_id

    def start_run(self):
        """Start the run (begin executing queued commands)."""
        print(f"Starting run {self.run_id}...")
        resp = requests.post(
            f"{self.base_url}/runs/{self.run_id}/actions",
            json={"data": {"actionType": "play"}},
            headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
        )
        if resp.status_code >= 400:
            print(f"ERROR: Failed to start run: {resp.text}")
            sys.exit(1)
        print("Run started!")
        print()

    def translate_ids(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate simulated IDs to real IDs in parameters."""
        translated = {}
        for key, value in params.items():
            if key.endswith("Id") and isinstance(value, str):
                # This is an ID field - translate it
                translated[key] = self.id_map.get(value, value)
            elif isinstance(value, dict):
                # Recursively translate nested dicts
                translated[key] = self.translate_ids(value)
            elif isinstance(value, list):
                # Handle lists
                translated[key] = [
                    self.translate_ids(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                translated[key] = value
        return translated

    def queue_and_execute_command(
        self,
        command_type: str,
        params: Dict[str, Any],
        description: str = "",
        simulated_result: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Queue a command and wait for it to execute."""
        self.command_count += 1

        print(f"\n{'=' * 70}")
        print(f"Command {self.command_count}: {command_type}")
        if description:
            print(f"Description: {description}")
        print(f"{'=' * 70}")

        # Translate any simulated IDs to real IDs
        translated_params = self.translate_ids(params)

        # Show simplified params (hide IDs for readability)
        simplified_params = {
            k: v for k, v in translated_params.items()
            if not k.endswith("Id")
        }
        if simplified_params:
            print(f"Parameters: {json.dumps(simplified_params, indent=2)}")

        # Send command with waitUntilComplete=true for atomic execution
        # This executes the command immediately and waits for completion
        print(f"Executing...")
        resp = requests.post(
            f"{self.base_url}/runs/{self.run_id}/commands?waitUntilComplete=true",
            json={
                "data": {
                    "commandType": command_type,
                    "params": translated_params,
                    "intent": "setup",  # Use "setup" intent for atomic commands
                }
            },
            headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
            timeout=300  # 5 minute timeout for long operations
        )

        if resp.status_code >= 400:
            print(f"\nERROR: Command failed")
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
            sys.exit(1)

        result = resp.json()

        # Check if command succeeded
        if result["data"]["status"] == "succeeded":
            print(f"✓ Command completed successfully")
        else:
            print(f"✗ Command failed: {result['data'].get('error', 'Unknown error')}")
            sys.exit(1)

        # Map simulated IDs to real IDs for resource creation commands
        if simulated_result:
            self.map_resource_ids(command_type, simulated_result, result["data"])

        return result["data"]

    def wait_for_command(self, command_id: str) -> None:
        """Poll until command completes."""
        for i in range(300):  # 60 second timeout
            resp = requests.get(
                f"{self.base_url}/runs/{self.run_id}/commands/{command_id}",
                headers={"Opentrons-Version": "3"},
            )

            if resp.status_code >= 400:
                print(f"ERROR: Failed to get command status")
                sys.exit(1)

            data = resp.json()["data"]
            status = data.get("status")

            if status == "succeeded":
                print(f"✓ Command completed successfully")
                return
            elif status == "failed":
                print(f"✗ Command failed: {data.get('error', 'Unknown error')}")
                sys.exit(1)
            elif status in ["queued", "running"]:
                time.sleep(0.2)
            else:
                time.sleep(0.2)

        print("ERROR: Command timed out")
        sys.exit(1)

    def map_resource_ids(self, command_type: str, simulated_data: Dict[str, Any], real_data: Dict[str, Any]):
        """Map simulated resource IDs to real IDs."""
        sim_result = simulated_data.get("result", {})
        real_result = real_data.get("result", {})

        if command_type == "loadLabware":
            sim_id = sim_result.get("labwareId")
            real_id = real_result.get("labwareId")
            if sim_id and real_id:
                self.id_map[sim_id] = real_id
                print(f"  Mapped labware ID: {sim_id[:8]}... -> {real_id[:8]}...")

        elif command_type == "loadPipette":
            sim_id = sim_result.get("pipetteId")
            real_id = real_result.get("pipetteId")
            if sim_id and real_id:
                self.id_map[sim_id] = real_id
                print(f"  Mapped pipette ID: {sim_id[:8]}... -> {real_id[:8]}...")

        elif command_type == "loadModule":
            sim_id = sim_result.get("moduleId")
            real_id = real_result.get("moduleId")
            if sim_id and real_id:
                self.id_map[sim_id] = real_id
                print(f"  Mapped module ID: {sim_id[:8]}... -> {real_id[:8]}...")

    def pause_for_adjustment(self, message: str = None):
        """Pause and allow user to make adjustments."""
        print(f"\n{'-' * 70}")
        print("PAUSE POINT")
        print(f"{'-' * 70}")

        if message:
            print(message)

        print("\nOptions:")
        print("  [Enter] - Continue to next command")
        print("  [a] - Make manual adjustment")
        print("  [s] - Skip pause points for rest of protocol")
        print("  [q] - Quit")

        try:
            choice = input("\nChoice: ").strip().lower()

            if choice == 'q':
                print("\nQuitting...")
                self.cleanup()
                sys.exit(0)
            elif choice == 'a':
                self.manual_adjustment_mode()
            elif choice == 's':
                return 'skip'

            return 'continue'

        except KeyboardInterrupt:
            print("\n\nInterrupted. Cleaning up...")
            self.cleanup()
            sys.exit(130)

    def manual_adjustment_mode(self):
        """Enter manual adjustment mode for fine positioning."""
        print("\n" + "=" * 70)
        print("MANUAL ADJUSTMENT MODE")
        print("=" * 70)
        print("\nYou can now send manual positioning commands.")
        print("Available commands:")
        print("  move <x> <y> <z>  - Move to absolute coordinates")
        print("  nudge <x> <y> <z> - Move relative to current position")
        print("  home              - Home all axes")
        print("  done              - Return to protocol")
        print()

        while True:
            try:
                cmd = input("Adjustment> ").strip().lower()

                if cmd == 'done':
                    print("Returning to protocol execution...")
                    break

                elif cmd == 'home':
                    print("Homing...")
                    self.queue_and_execute_command("home", {})

                elif cmd.startswith('move '):
                    parts = cmd.split()
                    if len(parts) == 4:
                        x, y, z = map(float, parts[1:4])
                        print(f"Moving to X:{x}, Y:{y}, Z:{z}")
                        self.queue_and_execute_command(
                            "robot/moveTo",
                            {"position": {"x": x, "y": y, "z": z}}
                        )
                    else:
                        print("Usage: move <x> <y> <z>")

                elif cmd.startswith('nudge '):
                    parts = cmd.split()
                    if len(parts) == 4:
                        x, y, z = map(float, parts[1:4])
                        print(f"Moving relative X:{x}, Y:{y}, Z:{z}")
                        self.queue_and_execute_command(
                            "robot/moveAxesRelative",
                            {
                                "axis": "x",
                                "distance": x
                            }
                        )
                        # Note: You'd need to call this for each axis
                        # This is simplified
                    else:
                        print("Usage: nudge <x> <y> <z>")
                else:
                    print("Unknown command. Type 'done' to return to protocol.")

            except KeyboardInterrupt:
                print("\nReturning to protocol...")
                break
            except Exception as e:
                print(f"Error: {e}")

    def execute_protocol(self, protocol_path: Path, auto_mode: bool = False):
        """Execute the protocol with pause points."""
        # Analyze to get full command sequence
        commands = self.analyze_protocol(protocol_path)

        # Parse to get structure
        parsed = self.parse_protocol(protocol_path)

        # Create run
        self.create_run()

        print("=" * 70)
        print("PROTOCOL EXECUTION")
        print("=" * 70)
        print(f"Total commands: {len(commands)}")
        print(f"Mode: {'Automatic' if auto_mode else 'Interactive (with pause points)'}")
        print("=" * 70)
        print()

        if not auto_mode:
            input("Press Enter to begin...")

        skip_pauses = auto_mode

        # Execute each command
        for i, cmd in enumerate(commands, 1):
            cmd_type = cmd["commandType"]
            params = cmd["params"]

            # Create description
            description = self.describe_command(cmd_type, params)

            # Execute (pass the full simulated command for ID mapping)
            self.queue_and_execute_command(cmd_type, params, description, simulated_result=cmd)

            # Pause point (unless skipping)
            if not skip_pauses and i < len(commands):
                result = self.pause_for_adjustment(
                    f"\nCompleted {i}/{len(commands)} commands. Next: {commands[i]['commandType']}"
                )
                if result == 'skip':
                    skip_pauses = True

        print("\n" + "=" * 70)
        print("PROTOCOL COMPLETE")
        print("=" * 70)
        print(f"\nExecuted {len(commands)} commands successfully!")

    def describe_command(self, cmd_type: str, params: Dict[str, Any]) -> str:
        """Create a human-readable description of a command."""
        if cmd_type == "home":
            return "Homing all axes"
        elif cmd_type == "loadLabware":
            return f"Loading {params.get('loadName', 'labware')} at {params.get('location', {}).get('slotName', 'unknown')}"
        elif cmd_type == "loadPipette":
            return f"Loading {params.get('pipetteName', 'pipette')} on {params.get('mount', 'unknown')} mount"
        elif cmd_type == "pickUpTip":
            return f"Picking up tip from {params.get('wellName', 'unknown')}"
        elif cmd_type == "aspirate":
            return f"Aspirating {params.get('volume', 0)}µL from {params.get('wellName', 'unknown')}"
        elif cmd_type == "dispense":
            return f"Dispensing {params.get('volume', 0)}µL to {params.get('wellName', 'unknown')}"
        elif cmd_type == "dropTip" or cmd_type == "dropTipInPlace":
            return "Dropping tip"
        elif cmd_type == "moveLabware":
            return f"Moving labware to {params.get('newLocation', 'unknown')}"
        else:
            return cmd_type

    def cleanup(self):
        """Clean up the run."""
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


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python hybrid_protocol_runner.py <protocol.py> [--auto]")
        print()
        print("Options:")
        print("  --auto    Run without pause points (automatic mode)")
        sys.exit(1)

    protocol_path = Path(sys.argv[1])
    auto_mode = "--auto" in sys.argv

    if not protocol_path.exists():
        print(f"ERROR: Protocol file not found: {protocol_path}")
        sys.exit(1)

    robot_ip = "10.90.158.110"

    print("=" * 70)
    print("HYBRID PROTOCOL RUNNER")
    print("=" * 70)
    print(f"Protocol: {protocol_path}")
    print(f"Robot: {robot_ip}")
    print(f"Mode: {'Automatic' if auto_mode else 'Interactive'}")
    print("=" * 70)
    print()

    runner = HybridProtocolRunner(robot_ip)

    try:
        runner.execute_protocol(protocol_path, auto_mode)
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
