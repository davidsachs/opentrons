#!/usr/bin/env python3
"""
Dry Run Executor - Executes HTTP scripts without robot movement.

This modifies the HTTPProtocolRunner to queue commands without executing them,
allowing us to capture the full command sequence for comparison.
"""

import sys
import json
from pathlib import Path
from typing import Any, Optional

import requests


class DryRunHTTPProtocolRunner:
    """
    Modified HTTPProtocolRunner that queues commands without executing.

    This allows testing the full command sequence without robot movement.
    """

    def __init__(self, robot_host: str, run_id: Optional[str] = None):
        self.robot_host = robot_host
        self.robot_port = 31950
        self.base_url = f"http://{robot_host}:{self.robot_port}"
        self.run_id = run_id

        # Track all commands
        self.queued_commands = []

        # ID mappings (variable name -> assigned ID)
        self.labware_ids = {}
        self.pipette_ids = {}
        self.module_ids = {}
        self.liquid_ids = {}

    def create_run(self) -> str:
        """Create a new run on the robot."""
        resp = requests.post(
            f"{self.base_url}/runs",
            json={"data": {}},
            headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
        )
        resp.raise_for_status()
        data = resp.json()
        self.run_id = data["data"]["id"]
        return self.run_id

    def execute_command(
        self,
        command_type: str,
        params: dict[str, Any],
        wait: bool = False,  # Changed default to False for dry run
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """Queue a command without executing (dry run mode)."""
        if not self.run_id:
            raise RuntimeError("No active run. Call create_run() first.")

        url = f"{self.base_url}/runs/{self.run_id}/commands"

        payload = {
            "data": {
                "commandType": command_type,
                "params": params,
                "intent": "protocol",
            }
        }

        # Don't wait for completion in dry run mode
        query_params = {}

        resp = requests.post(
            url,
            json=payload,
            params=query_params,
            headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
        )

        if resp.status_code >= 400:
            # Command failed - return error info
            error_data = resp.json()
            print(f"  Warning: Command {command_type} failed validation: {error_data.get('errors', [{}])[0].get('detail', 'Unknown error')}")
            return {"data": {"commandType": command_type, "params": params, "status": "failed", "error": error_data}}

        result = resp.json()
        self.queued_commands.append(result.get("data", result))
        return result

    def get_all_commands(self) -> list[dict]:
        """Get all commands that were queued."""
        if not self.run_id:
            raise RuntimeError("No active run.")

        resp = requests.get(
            f"{self.base_url}/runs/{self.run_id}/commands",
            headers={"Opentrons-Version": "3"},
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def cleanup(self):
        """Delete the run without executing."""
        if self.run_id:
            try:
                requests.delete(
                    f"{self.base_url}/runs/{self.run_id}",
                    headers={"Opentrons-Version": "3"},
                    timeout=10
                )
            except Exception:
                pass  # Ignore cleanup errors


def execute_http_script_dry_run(script_path: Path, robot_ip: str) -> list[dict]:
    """
    Execute an HTTP script in dry run mode.

    Args:
        script_path: Path to the generated HTTP script
        robot_ip: Robot IP address

    Returns:
        List of commands that would have been executed
    """
    print(f"Executing HTTP script in dry run mode: {script_path}")
    print(f"Robot: {robot_ip}")
    print()

    # Create a modified version of the script that uses our dry run runner
    with open(script_path) as f:
        script_code = f.read()

    # Replace the class definition
    modified_code = script_code.replace(
        'class HTTPProtocolRunner:',
        'class HTTPProtocolRunner(DryRunHTTPProtocolRunner):'
    )

    # But we need a simpler approach - just monkey patch the script's imports
    # Import the script as a module and monkey-patch it

    import importlib.util
    import sys

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("http_protocol", script_path)
        module = importlib.util.module_from_spec(spec)

        # Monkey-patch HTTPProtocolRunner before executing
        # Save original
        original_code = script_path.read_text()

        # Create temp file with our dry run class injected
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Write import for our dry run class
            f.write("from dry_run_executor import DryRunHTTPProtocolRunner\n")
            # Replace HTTPProtocolRunner class with ours
            f.write(original_code.replace(
                "class HTTPProtocolRunner:",
                "HTTPProtocolRunner = DryRunHTTPProtocolRunner\nclass _OriginalHTTPProtocolRunner:"
            ))
            temp_path = f.name

        # Load the modified module
        spec = importlib.util.spec_from_file_location("http_protocol_modified", temp_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules['http_protocol_modified'] = module
        spec.loader.exec_module(module)

        # Execute run_protocol
        if hasattr(module, 'run_protocol'):
            print("Executing run_protocol...")
            module.run_protocol(robot_ip)

            # The module should have created a runner - find it
            # It's created inside run_protocol, so we need to capture it differently
            print("ERROR: Cannot easily capture runner from module")
            return []
        else:
            print("ERROR: No run_protocol function found")
            return []

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if 'temp_path' in locals():
            import os
            try:
                os.unlink(temp_path)
            except:
                pass


def main():
    """Test the dry run executor."""
    script_path = Path("test_protocol_simple_http.py")
    robot_ip = "10.90.158.110"

    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        print("Run test_comparison_no_movement.py first to generate it")
        return 1

    print("="*70)
    print("DRY RUN EXECUTOR TEST")
    print("="*70)
    print()

    commands = execute_http_script_dry_run(script_path, robot_ip)

    if commands:
        print("\n" + "="*70)
        print("COMMANDS CAPTURED")
        print("="*70)
        print()

        # Show command types
        from collections import Counter
        cmd_types = Counter(cmd.get("commandType") for cmd in commands)
        print(f"Total commands: {len(commands)}")
        print("\nCommand breakdown:")
        for cmd_type, count in cmd_types.most_common():
            print(f"  {cmd_type}: {count}")

        print("\nFirst 5 commands:")
        for i, cmd in enumerate(commands[:5], 1):
            print(f"{i}. {cmd.get('commandType')} - {cmd.get('status', 'queued')}")

        # Save to file
        output_path = Path("dry_run_commands.json")
        with open(output_path, 'w') as f:
            json.dump(commands, f, indent=2)
        print(f"\nSaved all commands to: {output_path}")

        return 0
    else:
        print("\nERROR: No commands captured")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
