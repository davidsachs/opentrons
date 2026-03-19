"""
Protocol analyzer runner.

Runs protocols through the Opentrons analyzer to get command sequences.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests


@dataclass
class AnalysisResult:
    """Result from protocol analysis."""

    status: str  # "ok", "not-ok", "parameter-value-required"
    commands: list[dict[str, Any]] = field(default_factory=list)
    labware: list[dict[str, Any]] = field(default_factory=list)
    pipettes: list[dict[str, Any]] = field(default_factory=list)
    modules: list[dict[str, Any]] = field(default_factory=list)
    liquids: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    raw_result: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "commands": self.commands,
            "labware": self.labware,
            "pipettes": self.pipettes,
            "modules": self.modules,
            "liquids": self.liquids,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ProtocolAnalyzer:
    """
    Analyzes protocols using the Opentrons analyzer.

    Can use either:
    - Local analyzer (opentrons_cli analyze command)
    - Robot HTTP API (POST /protocols followed by analysis)
    """

    def __init__(
        self,
        robot_ip: Optional[str] = None,
        use_local: bool = False,
    ) -> None:
        """
        Initialize the analyzer.

        Args:
            robot_ip: IP address of robot for HTTP API analysis
            use_local: Use local CLI analyzer instead of robot
        """
        self.robot_ip = robot_ip
        self.use_local = use_local or (robot_ip is None)
        self._robot_base_url = f"http://{robot_ip}:31950" if robot_ip else None

    def analyze(
        self,
        protocol_path: str | Path,
        runtime_params: Optional[dict[str, Any]] = None,
    ) -> AnalysisResult:
        """
        Analyze a protocol file.

        Args:
            protocol_path: Path to the protocol file
            runtime_params: Optional runtime parameter values

        Returns:
            AnalysisResult with commands and other analysis data
        """
        protocol_path = Path(protocol_path)

        if self.use_local:
            return self._analyze_local(protocol_path, runtime_params)
        else:
            return self._analyze_http(protocol_path, runtime_params)

    def _analyze_local(
        self,
        protocol_path: Path,
        runtime_params: Optional[dict[str, Any]] = None,
    ) -> AnalysisResult:
        """Analyze using local CLI tool."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            output_file = f.name

        try:
            cmd = [
                "python",
                "-m",
                "opentrons.cli",
                "analyze",
                str(protocol_path),
                "--json-output",
                output_file,
            ]

            if runtime_params:
                cmd.extend(["--rtp-values", json.dumps(runtime_params)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                # Check if there's an analysis result anyway
                output_path = Path(output_file)
                if output_path.exists():
                    with open(output_path) as f:
                        analysis_data = json.load(f)
                    return self._parse_analysis_result(analysis_data)
                else:
                    return AnalysisResult(
                        status="not-ok",
                        errors=[{"message": result.stderr or "Analysis failed"}],
                    )

            # Parse the output
            output_path = Path(output_file)
            with open(output_path) as f:
                analysis_data = json.load(f)

            return self._parse_analysis_result(analysis_data)

        except subprocess.TimeoutExpired:
            return AnalysisResult(
                status="not-ok",
                errors=[{"message": "Analysis timed out"}],
            )
        except FileNotFoundError:
            return AnalysisResult(
                status="not-ok",
                errors=[
                    {
                        "message": "opentrons CLI not found. Install with: pip install opentrons"
                    }
                ],
            )
        finally:
            # Cleanup
            output_path = Path(output_file)
            if output_path.exists():
                output_path.unlink()

    def _analyze_http(
        self,
        protocol_path: Path,
        runtime_params: Optional[dict[str, Any]] = None,
    ) -> AnalysisResult:
        """Analyze using robot HTTP API."""
        if not self._robot_base_url:
            raise ValueError("Robot IP not configured for HTTP analysis")

        # Upload protocol
        with open(protocol_path, "rb") as f:
            files = {"files": (protocol_path.name, f, "application/octet-stream")}
            data = {}
            if runtime_params:
                data["runTimeParameterValues"] = json.dumps(runtime_params)

            headers = {"Opentrons-Version": "3"}

            resp = requests.post(
                f"{self._robot_base_url}/protocols",
                files=files,
                data=data,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            protocol_data = resp.json()

        protocol_id = protocol_data["data"]["id"]

        try:
            # Get the analysis
            analyses = protocol_data["data"].get("analysisSummaries", [])
            import time

            # Wait for initial analysis to complete if it's pending
            if analyses and analyses[0].get("status") == "pending":
                analysis_id = analyses[0]["id"]
                for _ in range(60):  # Wait up to 60 seconds
                    resp = requests.get(
                        f"{self._robot_base_url}/protocols/{protocol_id}/analyses/{analysis_id}",
                        headers={"Opentrons-Version": "3"},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    analysis_data = resp.json()["data"]

                    if analysis_data.get("status") == "completed":
                        # Update the analysis summary
                        analyses[0]["status"] = "completed"
                        break
                    time.sleep(1)

            if not analyses:
                # Trigger new analysis
                resp = requests.post(
                    f"{self._robot_base_url}/protocols/{protocol_id}/analyses",
                    json={},
                    headers={"Opentrons-Version": "3"},
                    timeout=30,
                )
                resp.raise_for_status()

                # Wait for analysis
                for _ in range(60):  # Wait up to 60 seconds
                    resp = requests.get(
                        f"{self._robot_base_url}/protocols/{protocol_id}/analyses",
                        headers={"Opentrons-Version": "3"},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    analyses = resp.json()["data"]

                    if analyses and analyses[-1].get("status") == "completed":
                        break
                    time.sleep(1)

            if not analyses:
                return AnalysisResult(
                    status="not-ok",
                    errors=[{"message": "No analysis completed"}],
                )

            # Get the full analysis
            analysis_id = analyses[-1]["id"]
            resp = requests.get(
                f"{self._robot_base_url}/protocols/{protocol_id}/analyses/{analysis_id}",
                headers={"Opentrons-Version": "3"},
                timeout=30,
            )
            resp.raise_for_status()
            analysis_data = resp.json()["data"]

            return self._parse_analysis_result(analysis_data)

        finally:
            # Clean up - delete the protocol
            try:
                requests.delete(
                    f"{self._robot_base_url}/protocols/{protocol_id}",
                    headers={"Opentrons-Version": "3"},
                    timeout=10,
                )
            except Exception:
                pass  # Ignore cleanup errors

    def _parse_analysis_result(self, data: dict[str, Any]) -> AnalysisResult:
        """Parse analysis result from JSON data."""
        status = data.get("result", data.get("status", "unknown"))
        if status == "parameter-value-required":
            status = "parameter-value-required"
        elif status in ("ok", "succeeded", "completed"):
            status = "ok"
        else:
            status = "not-ok"

        # Extract commands
        commands = data.get("commands", [])

        # Extract resources
        labware = data.get("labware", [])
        pipettes = data.get("pipettes", [])
        modules = data.get("modules", [])
        liquids = data.get("liquids", [])

        # Extract errors
        errors = data.get("errors", [])
        if isinstance(errors, list):
            errors = [
                e if isinstance(e, dict) else {"message": str(e)} for e in errors
            ]

        # Extract warnings (from command annotations or other sources)
        warnings = []
        for cmd in commands:
            if "notes" in cmd:
                for note in cmd["notes"]:
                    if note.get("noteKind") == "warning":
                        warnings.append(note)

        return AnalysisResult(
            status=status,
            commands=commands,
            labware=labware,
            pipettes=pipettes,
            modules=modules,
            liquids=liquids,
            errors=errors,
            warnings=warnings,
            raw_result=data,
        )

    def analyze_commands_only(
        self,
        protocol_path: str | Path,
        runtime_params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Analyze and return just the command sequence.

        This is useful for comparison between protocols.
        """
        result = self.analyze(protocol_path, runtime_params)
        return self._normalize_commands(result.commands)

    def _normalize_commands(
        self, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Normalize commands for comparison.

        Removes runtime-specific data like IDs, timestamps, etc.
        """
        normalized = []

        for cmd in commands:
            norm_cmd = {
                "commandType": cmd.get("commandType"),
                "params": self._normalize_params(cmd.get("params", {})),
            }

            # Include result for comparison if present
            if "result" in cmd:
                norm_cmd["result"] = self._normalize_result(cmd["result"])

            normalized.append(norm_cmd)

        return normalized

    def _normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Normalize command parameters."""
        # Remove IDs but keep names and values
        normalized = {}

        for key, value in params.items():
            # Skip runtime-specific IDs
            if key.endswith("Id") and isinstance(value, str):
                continue

            # Keep other values
            if isinstance(value, dict):
                normalized[key] = self._normalize_params(value)
            elif isinstance(value, list):
                normalized[key] = [
                    self._normalize_params(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                normalized[key] = value

        return normalized

    def _normalize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Normalize command result."""
        if not isinstance(result, dict):
            return result

        normalized = {}

        for key, value in result.items():
            # Skip runtime-specific data
            if key in ("createdAt", "startedAt", "completedAt", "id"):
                continue

            if isinstance(value, dict):
                normalized[key] = self._normalize_result(value)
            else:
                normalized[key] = value

        return normalized
