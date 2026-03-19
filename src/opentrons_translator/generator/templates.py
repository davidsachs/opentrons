"""
Code templates for HTTP API protocol generation.
"""

PROTOCOL_HEADER = '''"""
HTTP API Protocol - Translated from Python API
{original_name}

This protocol uses the Opentrons HTTP API to execute commands.
It is functionally equivalent to the original Python API protocol.

Original API Level: {api_level}
Robot Type: {robot_type}
"""

import requests
import json
import time
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class RobotConnection:
    """Connection to an Opentrons robot."""
    host: str
    port: int = 31950

    @property
    def base_url(self) -> str:
        return f"http://{{self.host}}:{{self.port}}"

    def health_check(self) -> bool:
        """Check if robot is reachable."""
        try:
            resp = requests.get(f"{{self.base_url}}/health", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False


class HTTPProtocolRunner:
    """
    Runs protocols via HTTP API commands.

    This class manages:
    - Creating and managing runs
    - Executing commands
    - Tracking resource IDs (labware, pipettes, modules)
    """

    def __init__(self, robot: RobotConnection):
        self.robot = robot
        self.run_id: Optional[str] = None

        # ID mappings (variable name -> assigned ID)
        self.labware_ids: dict[str, str] = {{}}
        self.pipette_ids: dict[str, str] = {{}}
        self.module_ids: dict[str, str] = {{}}
        self.liquid_ids: dict[str, str] = {{}}

    def create_run(self) -> str:
        """Create a new run on the robot."""
        resp = requests.post(
            f"{{self.robot.base_url}}/runs",
            json={{"data": {{}}}},
            headers={{"Content-Type": "application/json"}},
        )
        resp.raise_for_status()
        data = resp.json()
        self.run_id = data["data"]["id"]
        return self.run_id

    def execute_command(
        self,
        command_type: str,
        params: dict[str, Any],
        wait: bool = True,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """Execute a command in the current run."""
        if not self.run_id:
            raise RuntimeError("No active run. Call create_run() first.")

        url = f"{{self.robot.base_url}}/runs/{{self.run_id}}/commands"

        payload = {{
            "data": {{
                "commandType": command_type,
                "params": params,
                "intent": "protocol",
            }}
        }}

        query_params = {{}}
        if wait:
            query_params["waitUntilComplete"] = "true"
            query_params["timeout"] = str(timeout)

        resp = requests.post(
            url,
            json=payload,
            params=query_params,
            headers={{"Content-Type": "application/json"}},
        )
        resp.raise_for_status()
        return resp.json()

    def execute_stateless_command(
        self,
        command_type: str,
        params: dict[str, Any],
        wait: bool = True,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """Execute a stateless command (outside of a run)."""
        url = f"{{self.robot.base_url}}/commands"

        payload = {{
            "data": {{
                "commandType": command_type,
                "params": params,
            }}
        }}

        query_params = {{}}
        if wait:
            query_params["waitUntilComplete"] = "true"
            query_params["timeout"] = str(timeout)

        resp = requests.post(
            url,
            json=payload,
            params=query_params,
            headers={{"Content-Type": "application/json"}},
        )
        resp.raise_for_status()
        return resp.json()

    def get_run_status(self) -> dict[str, Any]:
        """Get current run status."""
        if not self.run_id:
            raise RuntimeError("No active run.")

        resp = requests.get(f"{{self.robot.base_url}}/runs/{{self.run_id}}")
        resp.raise_for_status()
        return resp.json()

    def play_run(self) -> None:
        """Start/resume the run."""
        if not self.run_id:
            raise RuntimeError("No active run.")

        resp = requests.post(
            f"{{self.robot.base_url}}/runs/{{self.run_id}}/actions",
            json={{"data": {{"actionType": "play"}}}},
        )
        resp.raise_for_status()

    def pause_run(self) -> None:
        """Pause the run."""
        if not self.run_id:
            raise RuntimeError("No active run.")

        resp = requests.post(
            f"{{self.robot.base_url}}/runs/{{self.run_id}}/actions",
            json={{"data": {{"actionType": "pause"}}}},
        )
        resp.raise_for_status()

    def stop_run(self) -> None:
        """Stop the run."""
        if not self.run_id:
            raise RuntimeError("No active run.")

        resp = requests.post(
            f"{{self.robot.base_url}}/runs/{{self.run_id}}/actions",
            json={{"data": {{"actionType": "stop"}}}},
        )
        resp.raise_for_status()

    def delete_run(self) -> None:
        """Delete the current run."""
        if not self.run_id:
            return

        resp = requests.delete(f"{{self.robot.base_url}}/runs/{{self.run_id}}")
        resp.raise_for_status()
        self.run_id = None

    # Helper methods for common operations

    def load_labware(
        self,
        var_name: str,
        load_name: str,
        location: dict[str, Any],
        namespace: str = "opentrons",
        version: int = 1,
        display_name: Optional[str] = None,
    ) -> str:
        """Load labware and track its ID."""
        params: dict[str, Any] = {{
            "loadName": load_name,
            "location": location,
            "namespace": namespace,
            "version": version,
        }}
        if display_name:
            params["displayName"] = display_name

        result = self.execute_command("loadLabware", params)
        labware_id = result["data"]["result"]["labwareId"]
        self.labware_ids[var_name] = labware_id
        return labware_id

    def load_pipette(
        self,
        var_name: str,
        pipette_name: str,
        mount: str,
    ) -> str:
        """Load pipette and track its ID."""
        params = {{
            "pipetteName": pipette_name,
            "mount": mount,
        }}

        result = self.execute_command("loadPipette", params)
        pipette_id = result["data"]["result"]["pipetteId"]
        self.pipette_ids[var_name] = pipette_id
        return pipette_id

    def load_module(
        self,
        var_name: str,
        model: str,
        location: dict[str, Any],
    ) -> str:
        """Load module and track its ID."""
        params = {{
            "model": model,
            "location": location,
        }}

        result = self.execute_command("loadModule", params)
        module_id = result["data"]["result"]["moduleId"]
        self.module_ids[var_name] = module_id
        return module_id

    def pick_up_tip(
        self,
        pipette_var: str,
        labware_var: str,
        well_name: str,
    ) -> None:
        """Pick up a tip."""
        self.execute_command("pickUpTip", {{
            "pipetteId": self.pipette_ids[pipette_var],
            "labwareId": self.labware_ids[labware_var],
            "wellName": well_name,
        }})

    def drop_tip(
        self,
        pipette_var: str,
        labware_var: Optional[str] = None,
        well_name: Optional[str] = None,
    ) -> None:
        """Drop the current tip."""
        params: dict[str, Any] = {{"pipetteId": self.pipette_ids[pipette_var]}}

        if labware_var and well_name:
            params["labwareId"] = self.labware_ids[labware_var]
            params["wellName"] = well_name
            self.execute_command("dropTip", params)
        else:
            self.execute_command("dropTipInPlace", params)

    def aspirate(
        self,
        pipette_var: str,
        labware_var: str,
        well_name: str,
        volume: float,
        flow_rate: Optional[float] = None,
    ) -> None:
        """Aspirate liquid."""
        params: dict[str, Any] = {{
            "pipetteId": self.pipette_ids[pipette_var],
            "labwareId": self.labware_ids[labware_var],
            "wellName": well_name,
            "volume": volume,
        }}
        if flow_rate:
            params["flowRate"] = flow_rate

        self.execute_command("aspirate", params)

    def dispense(
        self,
        pipette_var: str,
        labware_var: str,
        well_name: str,
        volume: float,
        flow_rate: Optional[float] = None,
        push_out: Optional[float] = None,
    ) -> None:
        """Dispense liquid."""
        params: dict[str, Any] = {{
            "pipetteId": self.pipette_ids[pipette_var],
            "labwareId": self.labware_ids[labware_var],
            "wellName": well_name,
            "volume": volume,
        }}
        if flow_rate:
            params["flowRate"] = flow_rate
        if push_out is not None:
            params["pushOut"] = push_out

        self.execute_command("dispense", params)

    def blow_out(
        self,
        pipette_var: str,
        labware_var: Optional[str] = None,
        well_name: Optional[str] = None,
    ) -> None:
        """Blow out."""
        params: dict[str, Any] = {{"pipetteId": self.pipette_ids[pipette_var]}}

        if labware_var and well_name:
            params["labwareId"] = self.labware_ids[labware_var]
            params["wellName"] = well_name
            self.execute_command("blowout", params)
        else:
            self.execute_command("blowOutInPlace", params)

    def touch_tip(
        self,
        pipette_var: str,
        labware_var: str,
        well_name: str,
    ) -> None:
        """Touch tip to well sides."""
        self.execute_command("touchTip", {{
            "pipetteId": self.pipette_ids[pipette_var],
            "labwareId": self.labware_ids[labware_var],
            "wellName": well_name,
        }})

    def home(self) -> None:
        """Home the robot."""
        self.execute_command("home", {{}})

    def delay(self, seconds: float) -> None:
        """Wait for specified duration."""
        self.execute_command("waitForDuration", {{"seconds": seconds}})

    def pause(self, message: str = "") -> None:
        """Pause and wait for resume."""
        params: dict[str, Any] = {{}}
        if message:
            params["message"] = message
        self.execute_command("waitForResume", params)

    def comment(self, message: str) -> None:
        """Add a comment to the run log."""
        self.execute_command("comment", {{"message": message}})

'''

PROTOCOL_FOOTER = '''

def run_protocol(robot_ip: str = "localhost") -> None:
    """
    Run the translated protocol.

    Args:
        robot_ip: IP address of the Opentrons robot
    """
    robot = RobotConnection(host=robot_ip)

    if not robot.health_check():
        raise ConnectionError(f"Cannot connect to robot at {{robot_ip}}")

    runner = HTTPProtocolRunner(robot)

    try:
        # Create a new run
        run_id = runner.create_run()
        print(f"Created run: {{run_id}}")

        # Execute protocol commands
        execute_protocol(runner)

        print("Protocol completed successfully")

    except Exception as e:
        print(f"Protocol error: {{e}}")
        raise
    finally:
        # Clean up
        if runner.run_id:
            runner.stop_run()


if __name__ == "__main__":
    import sys
    robot_ip = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    run_protocol(robot_ip)
'''


class ProtocolTemplate:
    """Template for generating HTTP API protocols."""

    @staticmethod
    def get_header(
        original_name: str = "Translated Protocol",
        api_level: str = "2.19",
        robot_type: str = "OT-3 Standard",
    ) -> str:
        """Get the protocol header."""
        return PROTOCOL_HEADER.format(
            original_name=original_name,
            api_level=api_level,
            robot_type=robot_type,
        )

    @staticmethod
    def get_footer() -> str:
        """Get the protocol footer."""
        return PROTOCOL_FOOTER

    @staticmethod
    def format_dict(d: dict, indent: int = 4) -> str:
        """Format a dictionary as Python code."""
        import json
        return json.dumps(d, indent=indent)
