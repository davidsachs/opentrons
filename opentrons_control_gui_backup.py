#!/usr/bin/env python3
"""
Opentrons Control GUI - Interactive protocol execution with live video feed.

Features:
- Live video stream from robot
- Display gantry position (X, Y, Z) with safety limit warnings
- Context-sensitive command help system
- Manual gantry control with soft limits (x1, x-1, y1, z-1, etc.)
- Gripper control (GO=open, GC=close)
- Instrument switching (P1/P2/P3 for left/right/gripper)
- Auto-executing protocols with pause/resume capability
- Pause/Resume with Tab (protocols auto-pause on comments with "pause")
- Comprehensive logging to log.txt (protocol code, HTTP, responses, commands)
- Error handling - continue even if commands fail
- Safety limits prevent crashes
- Asynchronous homing with live video

Controls:
  Enter          - Execute typed command (or manual step through paused protocol)
  Ctrl+Enter     - Next protocol step (if paused)
  Tab            - Pause/Resume protocol (protocols start paused, Tab to begin)
  Ctrl+Q         - Quit
  ESC            - Clear command input

Commands:
  Movement:      x1, y-2, z5 (relative mm)
  Home:          h
  Gripper:       GO (open), GC (close)
  Instruments:   P1 (left pipette), P2 (right pipette), P3 (gripper)
  Pipetting:     PA5 (aspirate 5µL), PD5 (dispense 5µL), PRAT10 (set rate 10µL/s)
                 Note: Requires tips picked up via protocol first
"""

import cv2
import numpy as np
import requests
import json
import threading
import queue
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from analyzer.runner import ProtocolAnalyzer


class OT3ControlGUI:
    """GUI for controlling Opentrons Flex with live video and protocol execution."""

    def __init__(self, robot_ip: str = "10.90.158.110"):
        self.robot_ip = robot_ip
        self.video_url = f"http://{robot_ip}:8080/stream.mjpg"
        self.api_url = f"http://{robot_ip}:31950"

        # Start video server if not running
        self._ensure_video_server_running()

        # Video capture
        self.cap = cv2.VideoCapture(self.video_url)

        # Video reconnection state
        self.video_failed_reads = 0  # Counter for consecutive failed reads
        self.video_reconnect_threshold = 10  # Fail reads before attempting reconnect
        self.last_reconnect_attempt = 0  # Timestamp of last reconnect attempt

        # State
        self.current_position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.command_input = ""
        self.status_message = "Ready"
        self.error_message = ""
        self.pending_command = None  # Command waiting for confirmation

        # Pipette state
        self.active_pipette = None  # 'left', 'right', or 'gripper'
        self.pipette_volume = 10.0  # microliters
        self.pipette_rate = 10.0  # microliters per second (Opentrons uses uL/s)

        # Movement feedrate (speed in mm/s for gantry movements)
        self.feedrate = 50.0  # mm/s (default moderate speed)

        # Instrument IDs and offsets (populated during initialization)
        self.instrument_ids = {}  # {'left': 'id', 'right': 'id', 'gripper': 'id'}
        self.instrument_offsets = {}  # {'left': {'x': 0, 'y': 0, 'z': 0}, ...}

        # Store home positions for each instrument (used to calculate gripper position)
        self.instrument_home_positions = {}  # {'left': {'x': ..., 'y': ..., 'z': ...}, ...}

        # Per-instrument limits (populated during homing)
        # Each instrument has its own limits based on its home position
        self.instrument_limits = {}  # {'left': {'x': {...}, 'y': {...}, 'z': {...}}, ...}

        # Soft limits for OT-3 Flex (in mm)
        # Based on actual robot measurements and Opentrons coordinate system
        # IMPORTANT: Z=0 is at DECK LEVEL (bottom), positive Z is UP (away from deck)
        # Origin (0,0,0) is at front-left corner of deck
        # NOTE: These are initial defaults, updated during homing based on detected instruments
        self.limits = {
            'x': {'min': 0.0, 'max': 550.0},    # X axis range (left to right)
            'y': {'min': 0.0, 'max': 450.0},    # Y axis range (front to back)
            'z': {'min': 0.0, 'max': 164.0},    # Z axis range (0=deck, 164=max height for gripper)
        }

        # Track whether we have a valid position from the robot yet
        self.position_initialized = False

        print(f"Opentrons Control GUI initialized")
        print(f"Robot IP: {robot_ip}")
        print(f"Video URL: {self.video_url}")
        print(f"API URL: {self.api_url}")
        print("-" * 70)
        print("Safety Limits:")
        print(f"  X: {self.limits['x']['min']:.1f} - {self.limits['x']['max']:.1f} mm")
        print(f"  Y: {self.limits['y']['min']:.1f} - {self.limits['y']['max']:.1f} mm")
        print(f"  Z: {self.limits['z']['min']:.1f} - {self.limits['z']['max']:.1f} mm (NOTE: Z=0 is DECK, higher values move UP)")
        print(f"  Warning zone: Within 20mm of limits (position display turns RED)")
        print(f"  IMPORTANT: Home robot (H command) before first movement to initialize position!")
        print("-" * 70)

        # Protocol execution
        self.run_id = None
        self.protocol_commands = []
        self.current_command_index = 0
        self.protocol_paused = True  # Start paused - user must press Tab to begin
        self.protocol_auto_advance = True  # Auto-advance through protocol steps
        self.id_map = {}  # Simulated ID -> Real ID mapping

        # Logging
        self.log_file = Path("log.txt")
        self._log("COMMAND", "=== Program Started ===", write_mode="a")

        # Command queue for async execution
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.command_executing = False  # Track if a command is currently executing
        self.user_command_queue = []  # Queue for user-entered commands
        self.pending_home_initialization = False  # Track if we need to initialize after homing

        # Start command execution thread
        self.running = True
        self.executor_thread = threading.Thread(target=self._command_executor, daemon=True)
        self.executor_thread.start()

        # Position update thread
        self.position_thread = threading.Thread(target=self._update_position, daemon=True)
        self.position_thread.start()

    def _log(self, log_type: str, message: str, write_mode: str = "a"):
        """Log activity to log.txt with timestamp and type.

        Args:
            log_type: One of "PROTOCOL", "HTTP", "RESPONSE", "COMMAND"
            message: The message to log (will be reformatted to single line)
            write_mode: File write mode ("a" for append, "w" for overwrite)
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        # Reformat message to single line (replace newlines/tabs with spaces, collapse multiple spaces)
        single_line_msg = " ".join(message.split())
        log_entry = f"[{timestamp}] {log_type}: {single_line_msg}\n"
        try:
            with open(self.log_file, write_mode) as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Warning: Failed to write to log file: {e}")

    def _ensure_video_server_running(self):
        """Start the video broadcast server on the robot if not already running."""
        try:
            ssh_key = r"C:\Users\David Sachs\Downloads\robot_key"
            ssh_cmd = [
                "ssh", "-i", ssh_key, f"root@{self.robot_ip}",
                "systemctl is-active --quiet broadcast_service || systemd-run --unit=broadcast_service --property=Restart=always --property=RestartSec=1 --collect python3 /data/broadcast.py"
            ]
            print("Ensuring video server is running...")
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("Video server is running (with auto-restart enabled)")
                # Give server time to start if it was just launched
                print("Waiting for video server to initialize...")
                time.sleep(3)
            else:
                print(f"Video server status: {result.stderr if result.stderr else 'OK'}")
                # Still wait in case it's starting up
                time.sleep(3)
        except Exception as e:
            print(f"Warning: Could not check/start video server: {e}")
            print("Video stream may not be available")

    def _reconnect_video_stream(self):
        """Attempt to reconnect to the video stream."""
        current_time = time.time()

        # Don't attempt reconnect too frequently (wait at least 6 seconds between attempts)
        if current_time - self.last_reconnect_attempt < 6:
            return False

        self.last_reconnect_attempt = current_time

        print("\nVideo stream lost. Attempting to reconnect...")
        print("(Video server will auto-restart in 5 seconds)")

        # Release the old capture
        try:
            self.cap.release()
        except:
            pass

        # Wait for server to restart (5 seconds + 1 second buffer)
        time.sleep(6)

        # Try to reconnect (up to 3 attempts)
        for attempt in range(1, 4):
            print(f"Reconnection attempt {attempt}/3...")
            try:
                self.cap = cv2.VideoCapture(self.video_url)
                # Test if we can read a frame
                ret, _ = self.cap.read()
                if ret:
                    print("Video stream reconnected successfully!")
                    self.video_failed_reads = 0
                    self.status_message = "Video stream reconnected"
                    return True
                else:
                    print(f"Attempt {attempt} failed: Could not read frame")
            except Exception as e:
                print(f"Attempt {attempt} failed: {e}")

            # Wait before next attempt
            if attempt < 3:
                time.sleep(2)

        print("Failed to reconnect video stream after 3 attempts")
        self.status_message = "Video stream disconnected - reconnection failed"
        return False

    def _update_position(self):
        """Background thread to update gantry position."""
        while self.running:
            try:
                # Get current position from robot
                # Note: This is a placeholder - you may need to adjust based on actual API
                resp = requests.get(
                    f"{self.api_url}/robot/positions",
                    headers={"Opentrons-Version": "3"},
                    timeout=2
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Extract position data (adjust based on actual API response)
                    # For now, we'll update based on command results
                    pass
            except:
                pass
            time.sleep(0.5)

    def _command_executor(self):
        """Background thread to execute commands."""
        while self.running:
            try:
                cmd = self.command_queue.get(timeout=0.1)
                result = self._execute_command_sync(cmd)
                self.result_queue.put(result)
            except queue.Empty:
                continue
            except Exception as e:
                self.result_queue.put({"error": str(e)})

    def _initialize_after_homing(self):
        """Initialize instruments and positions after homing completes."""
        print("\nHoming complete, loading instruments and querying position...")

        # Get instruments to learn their IDs and offsets
        try:
            resp = requests.get(
                f"{self.api_url}/instruments",
                headers={"Opentrons-Version": "3"},
                timeout=10
            )

            if resp.status_code == 200:
                response_data = resp.json()
                instruments = response_data.get("data", [])
                print(f"\nFound {len(instruments)} instruments")

                if not instruments:
                    print("WARNING: No instruments found in response!")
                    print("This might be because instruments need to be loaded via protocol")
                    self.position_initialized = False
                    self.error_message = "No instruments attached - cannot initialize position!"
                else:
                    # Track which instruments we found
                    has_gripper = False
                    has_pipette = False

                    for inst in instruments:
                        mount = inst.get("mount")
                        serial = inst.get("serialNumber")
                        inst_type = inst.get("instrumentType")

                        # Extract offset from nested structure
                        offset = inst.get("data", {}).get("calibratedOffset", {}).get("offset", {})

                        print(f"  {inst_type} on {mount}: {serial}")

                        if mount == "left":
                            self.instrument_ids["left"] = serial
                            self.instrument_offsets["left"] = offset
                            has_pipette = True
                        elif mount == "right":
                            self.instrument_ids["right"] = serial
                            self.instrument_offsets["right"] = offset
                            has_pipette = True
                        elif mount == "extension":
                            self.instrument_ids["gripper"] = serial
                            self.instrument_offsets["gripper"] = offset
                            has_gripper = True

                    # Update Z-axis limits based on instruments
                    z_clearance = 5.0  # 5mm safety margin above mechanical limit
                    if has_gripper and not has_pipette:
                        self.limits['z']['max'] = 164.0 + z_clearance
                        print(f"  Z-axis limit set to {self.limits['z']['max']:.0f}mm (gripper only, {z_clearance}mm clearance)")
                    elif has_pipette:
                        self.limits['z']['max'] = 250.0 + z_clearance
                        print(f"  Z-axis limit set to {self.limits['z']['max']:.0f}mm (pipette, {z_clearance}mm clearance)")
                    else:
                        print(f"  Z-axis limit: {self.limits['z']['max']:.0f}mm (default)")

                    # Initialize pipettes so we can use savePosition
                    pipettes_loaded = []

                    if "left" in self.instrument_ids:
                        print(f"\nLoading left pipette: {self.instrument_ids['left']}")
                        load_left_cmd = {
                            "commandType": "loadPipette",
                            "params": {
                                "pipetteName": "p50_multi_flex",
                                "mount": "left",
                                "pipetteId": self.instrument_ids["left"]
                            }
                        }
                        result = self._execute_command_sync(load_left_cmd)
                        if "error" not in result:
                            pipettes_loaded.append("left")
                            print(f"  Left pipette loaded successfully")
                        else:
                            print(f"  WARNING: Failed to load left pipette: {result.get('error')}")

                    if "right" in self.instrument_ids:
                        print(f"\nLoading right pipette: {self.instrument_ids['right']}")
                        load_right_cmd = {
                            "commandType": "loadPipette",
                            "params": {
                                "pipetteName": "p1000_multi_flex",
                                "mount": "right",
                                "pipetteId": self.instrument_ids["right"]
                            }
                        }
                        result = self._execute_command_sync(load_right_cmd)
                        if "error" not in result:
                            pipettes_loaded.append("right")
                            print(f"  Right pipette loaded successfully")
                        else:
                            print(f"  WARNING: Failed to load right pipette: {result.get('error')}")

                    # Calculate limits for all instruments based on their positions
                    print(f"\nCalculating limits for each instrument...")
                    clearance = 5.0  # 5mm safety margin
                    z_clearance = 5.0  # 5mm safety margin above mechanical limit

                    # Query and calculate limits for left pipette
                    if "left" in pipettes_loaded:
                        print(f"  Querying left pipette position...")
                        save_pos_cmd = {
                            "commandType": "savePosition",
                            "params": {"pipetteId": self.instrument_ids["left"]}
                        }
                        pos_result = self._execute_command_sync(save_pos_cmd)
                        if "error" not in pos_result and "position" in pos_result.get("result", {}):
                            pos = pos_result["result"]["position"]
                            # Store home position for later use
                            self.instrument_home_positions["left"] = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
                            self.instrument_limits["left"] = {
                                'x': {'min': 0.0, 'max': pos["x"] + clearance},
                                'y': {'min': 0.0, 'max': pos["y"] + clearance},
                                'z': {'min': 0.0, 'max': 250.0 + z_clearance}
                            }
                            print(f"    Left limits: X={self.instrument_limits['left']['x']['max']:.1f}, Y={self.instrument_limits['left']['y']['max']:.1f}, Z={self.instrument_limits['left']['z']['max']:.1f}")

                    # Query and calculate limits for right pipette
                    if "right" in pipettes_loaded:
                        print(f"  Querying right pipette position...")
                        save_pos_cmd = {
                            "commandType": "savePosition",
                            "params": {"pipetteId": self.instrument_ids["right"]}
                        }
                        pos_result = self._execute_command_sync(save_pos_cmd)
                        if "error" not in pos_result and "position" in pos_result.get("result", {}):
                            pos = pos_result["result"]["position"]
                            # Store home position for later use
                            self.instrument_home_positions["right"] = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
                            self.instrument_limits["right"] = {
                                'x': {'min': 0.0, 'max': pos["x"] + clearance},
                                'y': {'min': 0.0, 'max': pos["y"] + clearance},
                                'z': {'min': 0.0, 'max': 250.0 + z_clearance}
                            }
                            print(f"    Right limits: X={self.instrument_limits['right']['x']['max']:.1f}, Y={self.instrument_limits['right']['y']['max']:.1f}, Z={self.instrument_limits['right']['z']['max']:.1f}")

                    # Calculate limits for gripper based on left pipette home position + offsets
                    if has_gripper and "left" in self.instrument_home_positions:
                        print(f"  Calculating gripper limits from left pipette home + offsets...")
                        p1_home = self.instrument_home_positions["left"]
                        # Gripper position: P1 X+120.5, P1 Y-5.2, Z=164
                        gripper_x = p1_home["x"] + 120.5
                        gripper_y = p1_home["y"] - 5.2
                        self.instrument_limits["gripper"] = {
                            'x': {'min': 0.0, 'max': gripper_x + clearance},
                            'y': {'min': 0.0, 'max': gripper_y + clearance},
                            'z': {'min': 0.0, 'max': 164.0 + z_clearance}
                        }
                        print(f"    Gripper limits: X={self.instrument_limits['gripper']['x']['max']:.1f}, Y={self.instrument_limits['gripper']['y']['max']:.1f}, Z={self.instrument_limits['gripper']['z']['max']:.1f}")

                    # Initialize with left pipette if available
                    if "left" in self.instrument_limits:
                        # Query left pipette position one more time for current position
                        save_pos_cmd = {
                            "commandType": "savePosition",
                            "params": {"pipetteId": self.instrument_ids["left"]}
                        }
                        pos_result = self._execute_command_sync(save_pos_cmd)
                        if "error" not in pos_result and "position" in pos_result.get("result", {}):
                            pos = pos_result["result"]["position"]
                            self.current_position = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
                            self.limits = self.instrument_limits["left"]
                            self.active_pipette = "left"
                            self.position_initialized = True
                            print(f"\nPosition initialized from left pipette: X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z']:.1f}")
                            print(f"Active limits (left): X={self.limits['x']['max']:.1f}, Y={self.limits['y']['max']:.1f}, Z={self.limits['z']['max']:.1f}")
                            self.status_message = "Homing complete, position initialized (left pipette)"
                        else:
                            self.position_initialized = False
                            self.error_message = "Could not query position after loading pipettes!"
                    else:
                        print("WARNING: No pipettes loaded successfully, cannot query position!")
                        self.position_initialized = False
                        self.error_message = "Failed to load pipettes - cannot initialize position!"
            else:
                print(f"Failed to get instruments: {resp.status_code}")
                print(f"Response: {resp.text}")
                self.error_message = "Failed to get instruments!"
        except Exception as e:
            print(f"Error querying instruments: {e}")
            import traceback
            traceback.print_exc()
            self.error_message = f"Initialization error: {e}"

    def _execute_command_sync(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command synchronously."""
        try:
            # Ensure we have a run_id (create one if needed for manual commands)
            if not self.run_id:
                print(f"\n{'='*70}")
                print("Creating run for commands...")
                print(f"{'='*70}")
                run_url = f"{self.api_url}/runs"
                run_data = {"data": {}}
                self._log("HTTP", f"POST {run_url} {json.dumps(run_data)}")
                resp = requests.post(
                    run_url,
                    json=run_data,
                    headers={"Content-Type": "application/json", "Opentrons-Version": "3"}
                )
                print(f"HTTP POST {run_url}")
                print(f"Response Status: {resp.status_code}")
                response_json = resp.json()
                print(f"Response Body: {json.dumps(response_json, indent=2)}")
                self._log("RESPONSE", f"Status: {resp.status_code} {json.dumps(response_json)}")
                if resp.status_code >= 400:
                    return {"error": f"Failed to create run: {resp.text}"}
                self.run_id = response_json["data"]["id"]
                print(f"Created run ID: {self.run_id}")

            cmd_type = cmd["commandType"]
            params = cmd["params"]

            # Translate IDs if needed
            translated_params = self._translate_ids(params)

            # Log the HTTP request
            url = f"{self.api_url}/runs/{self.run_id}/commands?waitUntilComplete=true"
            request_data = {
                "data": {
                    "commandType": cmd_type,
                    "params": translated_params,
                    "intent": "setup"
                }
            }

            print(f"\n{'='*70}")
            print(f"HTTP Command Request:")
            print(f"{'='*70}")
            print(f"POST {url}")
            print(f"Request Body:")
            print(json.dumps(request_data, indent=2))

            # Log HTTP request to file
            self._log("HTTP", f"POST {url} {json.dumps(request_data)}")

            # Send command
            resp = requests.post(
                url,
                json=request_data,
                headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
                timeout=300
            )

            # Log the response
            print(f"\nResponse Status: {resp.status_code}")
            try:
                response_json = resp.json()
                print(f"Response Body:")
                print(json.dumps(response_json, indent=2))
                # Log response to file
                self._log("RESPONSE", f"Status: {resp.status_code} {json.dumps(response_json)}")
            except:
                print(f"Response Text: {resp.text}")
                # Log response to file
                self._log("RESPONSE", f"Status: {resp.status_code} {resp.text}")

            if resp.status_code >= 400:
                return {"error": f"Command failed: {resp.text}", "status": "failed"}

            result = resp.json()["data"]

            # Map IDs if this created resources
            if "simulated_result" in cmd:
                self._map_resource_ids(cmd_type, cmd["simulated_result"], result)

            # Update position from command response when available
            # This ensures we track the ACTUAL robot position, not just our commands
            if "position" in result.get("result", {}):
                pos = result["result"]["position"]
                # savePosition and gripper moves return x, y, z (not leftZ/rightZ)
                if "z" in pos and "x" in pos and "y" in pos:
                    # This is a gantry position - update from actual robot state
                    self.current_position = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
                    self.position_initialized = True
                    print(f"Position updated from robot: X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z']:.1f}")

            return result

        except Exception as e:
            print(f"\nException during command execution: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    def _translate_ids(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate simulated IDs to real IDs."""
        translated = {}
        for key, value in params.items():
            if key.endswith("Id") and isinstance(value, str):
                translated[key] = self.id_map.get(value, value)
            elif isinstance(value, dict):
                translated[key] = self._translate_ids(value)
            elif isinstance(value, list):
                translated[key] = [
                    self._translate_ids(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                translated[key] = value
        return translated

    def _map_resource_ids(self, cmd_type: str, sim_data: Dict, real_data: Dict):
        """Map simulated resource IDs to real ones."""
        sim_result = sim_data.get("result", {})
        real_result = real_data.get("result", {})

        for id_type in ["labwareId", "pipetteId", "moduleId"]:
            sim_id = sim_result.get(id_type)
            real_id = real_result.get(id_type)
            if sim_id and real_id:
                self.id_map[sim_id] = real_id

    def load_protocol(self, protocol_path: Path):
        """Load a protocol for execution."""
        self.status_message = f"Loading protocol: {protocol_path.name}"
        print(f"\n{self.status_message}")

        # Log the protocol code
        try:
            with open(protocol_path, 'r') as f:
                protocol_code = f.read()
            self._log("PROTOCOL", f"Loaded {protocol_path.name}: {protocol_code}")
        except Exception as e:
            print(f"Warning: Could not log protocol file: {e}")

        try:
            # Analyze protocol
            analyzer = ProtocolAnalyzer(robot_ip=self.robot_ip, use_local=False)
            result = analyzer.analyze(protocol_path)

            if result.status != "ok":
                self.error_message = f"Protocol analysis failed: {result.errors}"
                print(f"ERROR: {self.error_message}")
                return False

            self.protocol_commands = result.commands
            self.current_command_index = 0

            # Create run
            resp = requests.post(
                f"{self.api_url}/runs",
                json={"data": {}},
                headers={"Content-Type": "application/json", "Opentrons-Version": "3"}
            )

            if resp.status_code >= 400:
                self.error_message = f"Failed to create run: {resp.text}"
                print(f"ERROR: {self.error_message}")
                return False

            self.run_id = resp.json()["data"]["id"]

            # Count only non-comment steps
            step_count = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")
            self.status_message = f"Protocol loaded: {step_count} steps"
            print(f"{self.status_message}")
            print(f"Run ID: {self.run_id}")
            return True

        except Exception as e:
            self.error_message = f"Error loading protocol: {e}"
            print(f"ERROR: {self.error_message}")
            return False

    def execute_next_protocol_step(self):
        """Execute the next command in the protocol."""
        if not self.protocol_commands:
            self.error_message = "No protocol loaded"
            return

        if self.protocol_paused:
            self.error_message = "Protocol is paused (press Tab to resume)"
            return

        if self.current_command_index >= len(self.protocol_commands):
            self.status_message = "Protocol complete!"
            return

        # Skip through comments automatically
        while self.current_command_index < len(self.protocol_commands):
            cmd = self.protocol_commands[self.current_command_index]
            cmd_type = cmd["commandType"]

            if cmd_type == "comment":
                # Display comment and auto-advance
                comment_text = cmd.get("params", {}).get("message", "")
                self.status_message = f"Comment: {comment_text}"
                print(f"\nComment: {comment_text}")
                self._log("PROTOCOL", f"Comment: {comment_text}")

                # Check if comment contains "pause" - if so, pause protocol
                if "pause" in comment_text.lower():
                    self.protocol_paused = True
                    self.status_message = f"Protocol paused (comment: {comment_text})"
                    print(f"\nProtocol auto-paused due to comment with 'pause'")
                    self._log("COMMAND", "Protocol auto-paused due to 'pause' in comment")
                    self.current_command_index += 1
                    return  # Exit to allow user to press Tab to resume

                self.current_command_index += 1
                self.error_message = ""
                # Continue to next iteration to check if next command is also a comment
                continue
            else:
                # Found a non-comment command, break and execute it
                break

        # Check again if we've reached the end after skipping comments
        if self.current_command_index >= len(self.protocol_commands):
            self.status_message = "Protocol complete!"
            return

        cmd = self.protocol_commands[self.current_command_index]
        cmd_type = cmd["commandType"]

        # Count non-comment steps for display
        step_num = sum(1 for c in self.protocol_commands[:self.current_command_index + 1] if c["commandType"] != "comment")
        total_steps = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")

        self.status_message = f"Executing: {cmd_type} ({step_num}/{total_steps})"
        print(f"\nExecuting step {step_num}/{total_steps}: {cmd_type}")

        # Log protocol command execution
        self._log("PROTOCOL", f"Executing step {step_num}/{total_steps}: {cmd_type} params={json.dumps(cmd.get('params', {}))}")

        # Add simulated result for ID mapping
        cmd["simulated_result"] = cmd

        # Queue command for execution
        self.command_queue.put(cmd)
        self.command_executing = True

        # Command is now executing in background
        # Result will be handled by main loop's async checker
        self.status_message = f"Executing: {cmd_type} ({step_num}/{total_steps})..."

    def check_position_safe(self, x: float = None, y: float = None, z: float = None) -> tuple[bool, str]:
        """
        Check if a position is within safe limits.

        Args:
            x, y, z: Position coordinates (None means use current position)

        Returns:
            (is_safe, error_message) - is_safe is True if position is valid
        """
        # Use current position for any axis not specified
        check_x = x if x is not None else self.current_position.get('x', 0)
        check_y = y if y is not None else self.current_position.get('y', 0)
        check_z = z if z is not None else self.current_position.get('z', 0)

        # Check X limits
        # Allow small tolerance (0.5mm) to account for floating point precision
        tolerance = 0.5
        if check_x < self.limits['x']['min'] - tolerance:
            return False, f"X={check_x:.1f} below minimum {self.limits['x']['min']:.1f}mm"
        if check_x > self.limits['x']['max'] + tolerance:
            return False, f"X={check_x:.1f} exceeds maximum {self.limits['x']['max']:.1f}mm"

        # Check Y limits
        if check_y < self.limits['y']['min'] - tolerance:
            return False, f"Y={check_y:.1f} below minimum {self.limits['y']['min']:.1f}mm"
        if check_y > self.limits['y']['max'] + tolerance:
            return False, f"Y={check_y:.1f} exceeds maximum {self.limits['y']['max']:.1f}mm"

        # Check Z limits
        if check_z < self.limits['z']['min'] - tolerance:
            return False, f"Z={check_z:.1f} below minimum {self.limits['z']['min']:.1f}mm"
        if check_z > self.limits['z']['max'] + tolerance:
            return False, f"Z={check_z:.1f} exceeds maximum {self.limits['z']['max']:.1f}mm"

        return True, ""

    def get_command_suggestions(self) -> str:
        """Get context-sensitive command suggestions based on current input."""
        cmd = self.command_input.upper()

        if not cmd:
            # No input - show all available root commands
            return "Commands: G P X Y Z H F"

        # Gripper commands
        if cmd == 'G':
            return "Gripper: GO (open) GC (close)"

        # Pipette commands
        if cmd == 'P':
            return "Mount: P1 (left) P2 (right) P3 (gripper) PA PD PRAT"

        if cmd == 'P1':
            return "P1 - Activate left pipette"
        if cmd == 'P2':
            return "P2 - Activate right pipette"
        if cmd == 'P3':
            return "P3 - Activate gripper"

        if cmd.startswith('PA'):
            return "PA# - Aspirate volume (µL), e.g. PA5"
        if cmd.startswith('PD'):
            return "PD# - Dispense volume (µL), e.g. PD5"
        if cmd.startswith('PRAT'):
            return "PRAT# - Set flow rate (µL/s), e.g. PRAT10"

        # Movement commands
        if cmd[0] in 'XYZ':
            return f"{cmd[0]} - Move {cmd[0]} axis (mm), e.g. {cmd[0]}5 or {cmd[0]}-2.5"

        if cmd == 'H':
            return "H - Home all axes"

        if cmd == 'F' or cmd.startswith('F'):
            return "F# - Set feedrate (mm/s), e.g. F50 or F100"

        # If we're typing a number after a command, show what it means
        if len(cmd) > 1 and cmd[0] in 'XYZ':
            try:
                float(cmd[1:])
                return f"Move {cmd[0]} axis by {cmd[1:]} mm"
            except:
                pass

        return ""

    def execute_manual_command(self, cmd_text: str):
        """Execute a manual G-code style command.

        Supports multiple space-separated commands on one line.
        Example: X-50 Y-50 F10
        """
        original_text = cmd_text.strip()
        cmd_text = original_text.lower()

        if not cmd_text:
            return

        # Log the manual command
        self._log("COMMAND", f"Manual: {original_text}")

        # Parse multiple commands separated by spaces
        # Split on spaces and process each command
        commands = cmd_text.split()

        # Variables to accumulate for combined movements
        delta_x = 0.0
        delta_y = 0.0
        delta_z = 0.0
        has_movement = False
        feedrate_updated = False

        try:
            # First pass: parse all commands and update state
            for cmd in commands:
            # Gripper commands
            if cmd_text == 'go':
                cmd = {
                    "commandType": "robot/openGripperJaw",
                    "params": {}
                }
                self.status_message = "Opening gripper..."
                print(f"\nCommand: {original_text} -> {self.status_message}")
                self.command_executing = True
                self.command_queue.put(cmd)
                return

            elif cmd_text == 'gc':
                cmd = {
                    "commandType": "robot/closeGripperJaw",
                    "params": {}
                }
                self.status_message = "Closing gripper..."
                print(f"\nCommand: {original_text} -> {self.status_message}")
                self.command_executing = True
                self.command_queue.put(cmd)
                return

            # Mount activation (pipettes and gripper)
            elif cmd_text == 'p1':
                if 'left' not in self.instrument_ids:
                    self.error_message = "Left pipette not found! Home first (H)"
                    self.command_executing = False
                    return

                if 'left' not in self.instrument_limits:
                    self.error_message = "Left pipette limits not calculated! Home first (H)"
                    self.command_executing = False
                    return

                # Switch to left pipette and query position
                print(f"\nCommand: {original_text} -> Switching to LEFT pipette...")
                save_pos_cmd = {
                    "commandType": "savePosition",
                    "params": {
                        "pipetteId": self.instrument_ids["left"]
                    }
                }
                result = self._execute_command_sync(save_pos_cmd)

                if "error" not in result and "position" in result.get("result", {}):
                    pos = result["result"]["position"]
                    # Subtract 1mm from Z to ensure first movement will be within bounds
                    self.current_position = {"x": pos["x"], "y": pos["y"], "z": pos["z"] - 1.0}

                    # Swap to left pipette limits
                    self.limits = self.instrument_limits["left"]
                    self.active_pipette = 'left'
                    self.status_message = f"Activated LEFT pipette - X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z'] - 1.0:.1f}"
                    print(f"  Position updated: {self.status_message}")
                    print(f"  Limits switched to left: X={self.limits['x']['max']:.1f}, Y={self.limits['y']['max']:.1f}, Z={self.limits['z']['max']:.1f}")
                else:
                    self.error_message = "Failed to query left pipette position"
                # P1/P2/P3 commands are synchronous, so reset the executing flag
                self.command_executing = False
                return

            elif cmd_text == 'p2':
                if 'right' not in self.instrument_ids:
                    self.error_message = "Right pipette not found! Home first (H)"
                    self.command_executing = False
                    return

                if 'right' not in self.instrument_limits:
                    self.error_message = "Right pipette limits not calculated! Home first (H)"
                    self.command_executing = False
                    return

                # Switch to right pipette and query position
                print(f"\nCommand: {original_text} -> Switching to RIGHT pipette...")
                save_pos_cmd = {
                    "commandType": "savePosition",
                    "params": {
                        "pipetteId": self.instrument_ids["right"]
                    }
                }
                result = self._execute_command_sync(save_pos_cmd)

                if "error" not in result and "position" in result.get("result", {}):
                    pos = result["result"]["position"]
                    # Subtract 1mm from Z to ensure first movement will be within bounds
                    self.current_position = {"x": pos["x"], "y": pos["y"], "z": pos["z"] - 1.0}

                    # Swap to right pipette limits
                    self.limits = self.instrument_limits["right"]
                    self.active_pipette = 'right'
                    self.status_message = f"Activated RIGHT pipette - X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z'] - 1.0:.1f}"
                    print(f"  Position updated: {self.status_message}")
                    print(f"  Limits switched to right: X={self.limits['x']['max']:.1f}, Y={self.limits['y']['max']:.1f}, Z={self.limits['z']['max']:.1f}")
                else:
                    self.error_message = "Failed to query right pipette position"
                # P1/P2/P3 commands are synchronous, so reset the executing flag
                self.command_executing = False
                return

            elif cmd_text == 'p3':
                if 'gripper' not in self.instrument_ids:
                    self.error_message = "Gripper not found! Home first (H)"
                    self.command_executing = False
                    return

                if 'gripper' not in self.instrument_limits:
                    self.error_message = "Gripper limits not calculated! Home first (H)"
                    self.command_executing = False
                    return

                if 'left' not in self.instrument_ids:
                    self.error_message = "Left pipette not found! Need P1 to calculate gripper position"
                    self.command_executing = False
                    return

                # Switch to gripper - query CURRENT P1 position and calculate gripper position
                print(f"\nCommand: {original_text} -> Switching to GRIPPER...")

                # Query current P1 position
                save_pos_cmd = {
                    "commandType": "savePosition",
                    "params": {
                        "pipetteId": self.instrument_ids["left"]
                    }
                }
                result = self._execute_command_sync(save_pos_cmd)

                if "error" not in result and "position" in result.get("result", {}):
                    p1_pos = result["result"]["position"]

                    # Calculate gripper position from CURRENT P1 position: P1 X+120.5, P1 Y-5.2, Z=164
                    gripper_x = p1_pos["x"] + 125#120.5
                    gripper_y = p1_pos["y"] - 10.4#
                    gripper_z = 164.0

                    self.current_position = {"x": gripper_x, "y": gripper_y, "z": gripper_z}

                    # Swap to gripper limits
                    self.limits = self.instrument_limits["gripper"]
                    self.active_pipette = 'gripper'
                    self.status_message = f"Activated GRIPPER - X={gripper_x:.1f}, Y={gripper_y:.1f}, Z={gripper_z:.1f}"
                    print(f"  Current P1 position: X={p1_pos['x']:.1f}, Y={p1_pos['y']:.1f}, Z={p1_pos['z']:.1f}")
                    print(f"  Gripper position (P1 + offset): {self.status_message}")
                    print(f"  Limits switched to gripper: X={self.limits['x']['max']:.1f}, Y={self.limits['y']['max']:.1f}, Z={self.limits['z']['max']:.1f}")
                else:
                    self.error_message = "Failed to query P1 position for gripper calculation"
                # P1/P2/P3 commands are synchronous, so reset the executing flag
                self.command_executing = False
                return

            # Pipette volume/rate setting
            elif cmd_text.startswith('pvol'):
                try:
                    value = float(cmd_text[4:])
                    self.pipette_volume = value
                    self.status_message = f"Set pipette volume: {value} µL"
                    print(f"\nCommand: {original_text} -> {self.status_message}")
                    self.command_executing = False  # Instant command, no async execution
                    return
                except ValueError:
                    self.error_message = f"Invalid volume: {cmd_text}"
                    self.command_executing = False
                    return

            elif cmd_text.startswith('prat'):
                try:
                    value = float(cmd_text[4:])
                    self.pipette_rate = value
                    self.status_message = f"Set pipette rate: {value} µL/s"
                    print(f"\nCommand: {original_text} -> {self.status_message}")
                    self.command_executing = False  # Instant command, no async execution
                    return
                except ValueError:
                    self.error_message = f"Invalid rate: {cmd_text}"
                    self.command_executing = False
                    return

            # Pipette flow control - aspirate/dispense in place (requires tips picked up via protocol first)
            elif cmd_text.startswith('pa'):  # Aspirate
                if not self.active_pipette or self.active_pipette == 'gripper':
                    self.error_message = "No pipette active! Use P1 or P2 first"
                    self.command_executing = False
                    return
                try:
                    volume = float(cmd_text[2:])
                    pipette_id = self.instrument_ids.get(self.active_pipette)
                    if not pipette_id:
                        self.error_message = f"{self.active_pipette} pipette not found!"
                        self.command_executing = False
                        return

                    cmd = {
                        "commandType": "aspirateInPlace",
                        "params": {
                            "pipetteId": pipette_id,
                            "volume": volume,
                            "flowRate": self.pipette_rate
                        }
                    }
                    self.status_message = f"Aspirating {volume}µL at {self.pipette_rate}µL/s"
                    print(f"\nCommand: {original_text} -> {self.status_message}")
                    self.command_executing = True
                    self.command_queue.put(cmd)
                    return
                except ValueError:
                    self.error_message = f"Invalid volume: {cmd_text}"
                    self.command_executing = False
                    return

            elif cmd_text.startswith('pd'):  # Dispense
                if not self.active_pipette or self.active_pipette == 'gripper':
                    self.error_message = "No pipette active! Use P1 or P2 first"
                    self.command_executing = False
                    return
                try:
                    volume = float(cmd_text[2:])
                    pipette_id = self.instrument_ids.get(self.active_pipette)
                    if not pipette_id:
                        self.error_message = f"{self.active_pipette} pipette not found!"
                        self.command_executing = False
                        return

                    cmd = {
                        "commandType": "dispenseInPlace",
                        "params": {
                            "pipetteId": pipette_id,
                            "volume": volume,
                            "flowRate": self.pipette_rate
                        }
                    }
                    self.status_message = f"Dispensing {volume}µL at {self.pipette_rate}µL/s"
                    print(f"\nCommand: {original_text} -> {self.status_message}")
                    self.command_executing = True
                    self.command_queue.put(cmd)
                    return
                except ValueError:
                    self.error_message = f"Invalid volume: {cmd_text}"
                    self.command_executing = False
                    return

            # Parse movement commands (x1, x-1, y5, z-2, etc.)
            elif cmd_text[0] in ['x', 'y', 'z'] and len(cmd_text) > 1:
                axis = cmd_text[0]
                try:
                    distance = float(cmd_text[1:])
                except ValueError:
                    self.error_message = f"Invalid command: {cmd_text}"
                    return

                # Calculate new position
                curr_x = self.current_position.get('x', 0)
                curr_y = self.current_position.get('y', 0)
                curr_z = self.current_position.get('z', 0)

                new_x = curr_x + distance if axis == 'x' else curr_x
                new_y = curr_y + distance if axis == 'y' else curr_y
                new_z = curr_z + distance if axis == 'z' else curr_z

                # Check if we have a valid position from the robot
                if not self.position_initialized:
                    self.error_message = "Position not initialized! Home robot first (H command)"
                    print(f"\n{'='*70}")
                    print(f"SAFETY WARNING: POSITION NOT INITIALIZED")
                    print(f"{'='*70}")
                    print(f"Command: {cmd_text}")
                    print(f"ERROR: Cannot move until robot position is known!")
                    print(f"SOLUTION: First home the robot with 'H' command")
                    print(f"         This will initialize the position tracking.")
                    print(f"{'='*70}")
                    return

                # Check safety limits
                is_safe, error_msg = self.check_position_safe(x=new_x, y=new_y, z=new_z)
                if not is_safe:
                    self.error_message = f"SAFETY LIMIT: {error_msg}"
                    print(f"\n{'='*70}")
                    print(f"SAFETY LIMIT VIOLATION")
                    print(f"{'='*70}")
                    print(f"Command: {cmd_text}")
                    print(f"Current: X={curr_x:.1f}, Y={curr_y:.1f}, Z={curr_z:.1f}")
                    print(f"Requested: {axis.upper()}{distance:+.1f}mm")
                    print(f"Would result in: X={new_x:.1f}, Y={new_y:.1f}, Z={new_z:.1f}")
                    print(f"ERROR: {error_msg}")
                    print(f"{'='*70}")
                    return

                # Use robot/moveTo for all X/Y/Z movements
                # This ensures we get position feedback from all movements
                # Use the correct mount based on which instrument is active
                if self.active_pipette == "gripper":
                    cmd = {
                        "commandType": "robot/moveTo",
                        "params": {
                            "gripperId": "flex_gripper",
                            "mount": "extension",
                            "destination": {
                                "x": new_x,
                                "y": new_y,
                                "z": new_z
                            }
                        }
                    }
                else:
                    # For pipettes, use the mount (left or right)
                    cmd = {
                        "commandType": "robot/moveTo",
                        "params": {
                            "pipetteId": f"{self.active_pipette}_pipette",
                            "mount": self.active_pipette,
                            "destination": {
                                "x": new_x,
                                "y": new_y,
                                "z": new_z
                            }
                        }
                    }

                self.status_message = f"Moving {axis.upper()}{distance:+.1f}mm -> X={new_x:.1f}, Y={new_y:.1f}, Z={new_z:.1f}"
                print(f"\n{'='*70}")
                print(f"EXECUTING MOVE:")
                print(f"{'='*70}")
                print(f"Command: {cmd_text}")
                print(f"Current: X={curr_x:.1f}, Y={curr_y:.1f}, Z={curr_z:.1f}")
                print(f"Requested: {axis.upper()}{distance:+.1f}mm")
                print(f"New: X={new_x:.1f}, Y={new_y:.1f}, Z={new_z:.1f}")
                print(f"{'='*70}")

                # Execute immediately
                self.command_executing = True
                self.command_queue.put(cmd)

            elif cmd_text == 'h' or cmd_text == 'home':
                # Home command - now asynchronous so video stream can continue
                self.status_message = "Homing robot..."
                print(f"\nCommand: {cmd_text} -> Homing robot (async)...")

                # Queue the home command asynchronously
                home_cmd = {"commandType": "home", "params": {}}
                self.command_queue.put(home_cmd)

                # Set flag to run initialization after homing completes
                self.pending_home_initialization = True
                # Note: command_executing flag stays True until initialization completes
                return

            else:
                self.error_message = f"Unknown command: {cmd_text}"
                print(f"ERROR: {self.error_message}")

        except Exception as e:
            self.error_message = f"Command error: {e}"
            print(f"ERROR: {self.error_message}")
            import traceback
            traceback.print_exc()

    def draw_overlay(self, frame):
        """Draw status overlay on video frame."""
        height, width = frame.shape[:2]

        # Use LINE_AA for antialiasing, doubled font size
        font = cv2.FONT_HERSHEY_SIMPLEX
        line_type = cv2.LINE_AA
        small_scale = 0.6
        tiny_scale = 0.5
        thickness = 1

        # Position info (upper right) - green text directly on image
        # Color changes to red when near limits (within 20mm)
        # Note: Position is from actual robot responses, not locally tracked
        status_y = 25
        x_pos = width - 230

        curr_x = self.current_position.get('x', 0)
        curr_y = self.current_position.get('y', 0)
        curr_z = self.current_position.get('z', 0)

        # Check proximity to limits (within 20mm = warning)
        # NOTE: For Z axis, higher values = closer to deck (inverted axis)
        x_color = (0, 255, 0)
        if curr_x < 20 or curr_x > (self.limits['x']['max'] - 20):
            x_color = (0, 0, 255)  # Red warning

        y_color = (0, 255, 0)
        if curr_y < 20 or curr_y > (self.limits['y']['max'] - 20):
            y_color = (0, 0, 255)  # Red warning

        z_color = (0, 255, 0)
        # Red if near deck (low Z = close to deck) or if not initialized
        if curr_z < 20 or not self.position_initialized:
            z_color = (0, 0, 255)  # Red warning

        cv2.putText(frame, f"X: {curr_x:.1f}/{self.limits['x']['max']:.0f}",
                   (x_pos, status_y), font, small_scale, x_color, thickness, line_type)
        cv2.putText(frame, f"Y: {curr_y:.1f}/{self.limits['y']['max']:.0f}",
                   (x_pos, status_y + 25), font, small_scale, y_color, thickness, line_type)
        cv2.putText(frame, f"Z: {curr_z:.1f}/{self.limits['z']['max']:.0f}",
                   (x_pos, status_y + 50), font, small_scale, z_color, thickness, line_type)

        # Pipette state (if active)
        if self.active_pipette:
            pip_text = f"Pip: {self.active_pipette[0].upper()} {self.pipette_volume:.1f}uL@{self.pipette_rate:.1f}uL/s"
            cv2.putText(frame, pip_text, (x_pos, status_y + 75),
                       font, tiny_scale, (0, 255, 0), thickness, line_type)

        # Protocol status (if running)
        if self.protocol_commands:
            current_step = sum(1 for c in self.protocol_commands[:self.current_command_index] if c["commandType"] != "comment")
            total_steps = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")
            protocol_text = f"Protocol: {current_step}/{total_steps}"
            if self.protocol_paused:
                protocol_text += " PAUSED"
            cv2.putText(frame, protocol_text, (x_pos, status_y + 100),
                       font, tiny_scale, (0, 255, 0), thickness, line_type)

        # Command input (upper left) - green/red directly on image
        input_y = 25
        cv2.putText(frame, f"> {self.command_input}_", (10, input_y),
                   font, small_scale, (0, 255, 0), thickness, line_type)

        # Context-sensitive help (below command input)
        suggestions = self.get_command_suggestions()
        if suggestions:
            cv2.putText(frame, suggestions, (10, input_y + 25),
                       font, tiny_scale, (0, 255, 0), thickness, line_type)

        # Status message (bottom) - green for normal, red for errors
        status_color = (0, 255, 0) if not self.error_message else (0, 0, 255)
        status_text = self.error_message if self.error_message else self.status_message
        cv2.putText(frame, status_text, (10, height - 10),
                   font, small_scale, status_color, thickness, line_type)

        return frame

    def cleanup(self):
        """Clean up resources and delete run."""
        print("\nCleaning up...")

        # Delete the run if one was created
        if self.run_id:
            try:
                print(f"Deleting run: {self.run_id}")
                resp = requests.delete(
                    f"{self.api_url}/runs/{self.run_id}",
                    headers={"Opentrons-Version": "4"}
                )
                if resp.status_code == 200:
                    print("Run deleted successfully")
                else:
                    print(f"Warning: Failed to delete run (status {resp.status_code})")
            except Exception as e:
                print(f"Warning: Error deleting run: {e}")

        # Stop threads
        self.running = False

        # Release video
        if self.cap:
            self.cap.release()

        cv2.destroyAllWindows()
        print("Cleanup complete")

    def run(self):
        """Main GUI loop."""
        print("Starting Opentrons Control GUI...")
        print("Press Ctrl+Q to quit")

        cv2.namedWindow('Opentrons Control', cv2.WINDOW_NORMAL)

        while self.running:
            # Check for completed commands (non-blocking)
            try:
                result = self.result_queue.get_nowait()
                if "error" in result:
                    self.error_message = f"Command error: {result['error']}"
                    print(f"\nCommand error: {self.error_message}")
                    self.command_executing = False  # Command finished (with error)
                    self.pending_home_initialization = False  # Cancel initialization on error
                    # Don't advance index - wait for user to press Ctrl+Enter to skip
                    if self.protocol_commands:
                        step_num = sum(1 for c in self.protocol_commands[:self.current_command_index + 1] if c["commandType"] != "comment")
                        self.status_message = f"Error on step {step_num}. Press Enter to skip and continue."
                elif result.get("status") == "succeeded":
                    print(f"\nCommand completed successfully")
                    self.error_message = ""

                    # Check if this was a homing command that needs initialization
                    if self.pending_home_initialization:
                        print("\nHoming completed, starting initialization...")
                        self.status_message = "Initializing instruments..."
                        self.pending_home_initialization = False
                        # Run initialization (this is synchronous but happens after homing)
                        self._initialize_after_homing()
                        # Now we're done with the entire home+init process
                        self.command_executing = False
                    else:
                        # Normal command completion
                        self.command_executing = False  # Command finished successfully

                    # Advance to next protocol step if we're running a protocol
                    if self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                        self.current_command_index += 1
                        # Count completed steps
                        step_num = sum(1 for c in self.protocol_commands[:self.current_command_index] if c["commandType"] != "comment")
                        total_steps = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")

                        # Auto-advance to next step if enabled and not paused
                        if self.protocol_auto_advance and not self.protocol_paused:
                            self.status_message = f"Step {step_num}/{total_steps} complete. Auto-advancing..."
                            # Automatically execute next step after a brief pause
                            import time
                            time.sleep(0.1)  # Brief pause to allow UI update
                            self.execute_next_protocol_step()
                        else:
                            self.status_message = f"Step {step_num}/{total_steps} complete. Press Enter for next step."
            except queue.Empty:
                pass

            # Process queued user commands if no command is executing
            if not self.command_executing and self.user_command_queue:
                next_cmd = self.user_command_queue.pop(0)
                print(f"\n{'='*70}")
                print(f"PROCESSING QUEUED COMMAND: {next_cmd}")
                print(f"Queue remaining: {len(self.user_command_queue)}")
                print(f"{'='*70}")
                self.command_executing = True
                self.execute_manual_command(next_cmd)
                print(f"After execute_manual_command: command_executing = {self.command_executing}")

            # Read video frame
            ret, frame = self.cap.read()
            if not ret:
                # Increment failed read counter
                self.video_failed_reads += 1

                # If we've exceeded the threshold, attempt reconnection
                if self.video_failed_reads >= self.video_reconnect_threshold:
                    self.error_message = "Video stream lost - reconnecting..."
                    # Attempt reconnection in a non-blocking way
                    # Note: This will block the main loop briefly, but that's acceptable
                    # since we can't display video anyway
                    reconnected = self._reconnect_video_stream()
                    if not reconnected:
                        self.error_message = "Video stream disconnected - reconnection failed"
                else:
                    self.error_message = f"Video stream disconnected ({self.video_failed_reads}/{self.video_reconnect_threshold})"

                # Create blank frame
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            else:
                # Successfully read frame - reset counter
                if self.video_failed_reads > 0:
                    print("Video stream recovered")
                    self.video_failed_reads = 0
                    if self.error_message.startswith("Video stream"):
                        self.error_message = ""

            # Draw overlay
            frame = self.draw_overlay(frame)

            # Display
            cv2.imshow('Opentrons Control', frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == 17:  # Ctrl+Q
                break
            elif key == 13:  # Enter
                if self.command_input:
                    if self.command_executing:
                        # Queue the command if one is already executing
                        self.user_command_queue.append(self.command_input)
                        print(f"Command queued: {self.command_input} (queue length: {len(self.user_command_queue)})")
                        self.status_message = f"Command queued: {self.command_input}"
                    else:
                        # Execute immediately if no command is running
                        self.command_executing = True
                        self.execute_manual_command(self.command_input)
                    self.command_input = ""
                elif self.pending_command:
                    # Execute the pending command
                    print("\nExecuting pending command...")
                    cmd_data = self.pending_command
                    self.command_executing = True
                    self.command_queue.put(cmd_data["cmd"])

                    # Note: Position will be updated from the robot's response
                    # robot/moveTo returns actual position for all X/Y/Z movements

                    self.pending_command = None
                    self.status_message = "Command executing..."
                else:
                    # Enter without input = advance protocol step
                    # If there's an error, skip the failed command
                    if self.error_message and self.protocol_commands:
                        print("\nSkipping failed command, advancing to next step...")
                        self.current_command_index += 1
                        self.error_message = ""
                    self.execute_next_protocol_step()
            elif key == 10:  # Ctrl+Enter (on some systems)
                # If there's an error, skip the failed command
                if self.error_message and self.protocol_commands:
                    print("\nSkipping failed command, advancing to next step...")
                    self.current_command_index += 1
                    self.error_message = ""
                self.execute_next_protocol_step()
            elif key == 9:  # Tab
                self.protocol_paused = not self.protocol_paused
                self.status_message = "Protocol PAUSED" if self.protocol_paused else "Protocol RESUMED"
                print(f"\n{self.status_message}")
                self._log("COMMAND", self.status_message)

                # If unpausing and auto-advance is enabled, start executing protocol
                if not self.protocol_paused and self.protocol_auto_advance and self.protocol_commands:
                    if not self.command_executing:
                        self.execute_next_protocol_step()
            elif key == 27:  # ESC
                self.command_input = ""
                self.error_message = ""
                self.pending_command = None
            elif key == 8:  # Backspace
                self.command_input = self.command_input[:-1]
            elif 32 <= key <= 126:  # Printable characters
                # Convert to uppercase for display
                self.command_input += chr(key).upper()

        # Cleanup
        self.cleanup()


def main():
    """Main entry point."""
    import sys

    robot_ip = "10.90.158.110"

    # Create GUI
    gui = OT3ControlGUI(robot_ip)

    # Load protocol if provided
    if len(sys.argv) > 1:
        protocol_path = Path(sys.argv[1])
        if protocol_path.exists():
            gui.load_protocol(protocol_path)
        else:
            print(f"Warning: Protocol file not found: {protocol_path}")

    # Run GUI
    try:
        gui.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        gui.cleanup()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        gui.cleanup()


if __name__ == "__main__":
    main()
