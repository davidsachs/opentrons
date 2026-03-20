#!/usr/bin/env python3
"""
Opentrons Control GUI - Interactive protocol execution with live video feed.

Features:
- Live video stream from robot
- Deck visualizer overlay showing labware layout and protocol animation
- Display gantry position (X, Y, Z) with safety limit warnings
- Context-sensitive command help system
- Manual gantry control with soft limits and feedrate control
- Multi-axis coordinated movements (e.g., X-50 Y-50 F10 for diagonal moves)
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
  Ctrl+L         - Load protocol file (opens file dialog)
  Ctrl+U         - Upload media change CSV (generates protocol from CSV)
  +/-            - Resize deck visualizer overlay (20%-80%)
  ESC            - Quit immediately

Commands:
  Relative:      X1, Y-2, Z5 (relative mm movement)
  Absolute:      GX200, GY150, GZ50 (absolute position, can combine)
  Saved loc:     SET0 (save position), G0 (move to saved position)
  Feedrate:      F50 (set speed to 50mm/s), F0 (reset to default)
  Home:          H
  Protocol:      R (restart protocol from beginning)
  Gripper:       GO (open), GC (close)
  Instruments:   P1 (left pipette), P2 (right pipette), P3 (gripper)
  Pipetting:     PA5 (aspirate 5µL), PD5 (dispense 5µL), PRAT10 (set rate 10µL/s)
  Quit:          Q (quit application)

Protocol comments (embedded gcode):
  protocol.comment("SET0")     - Save current position as location 0
  protocol.comment("G0")       - Move to saved location 0
  protocol.comment("GX200 GY150 GZ50") - Move to absolute coordinates
  protocol.comment("Pause.")   - Pause for manual adjustment
"""

import os
import sys

# FFmpeg writes noise (MJPEG boundary warnings etc.) directly to C-level fd 2,
# bypassing Python's logging. Redirect fd 2 to devnull while keeping
# Python's sys.stderr pointed at the original fd so exceptions still print.
_stderr_fd = sys.stderr.fileno()
_saved_stderr_fd = os.dup(_stderr_fd)
_devnull_fd = os.open(os.devnull, os.O_WRONLY)
os.dup2(_devnull_fd, _stderr_fd)
os.close(_devnull_fd)
sys.stderr = os.fdopen(_saved_stderr_fd, 'w')

import cv2
import numpy as np
import requests
import json
import threading
import queue
import time
import subprocess
import zmq
import csv
import re
import shutil
import ast
import tempfile
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from analyzer.runner import ProtocolAnalyzer
from deck_visualizer import DeckVisualizer


class OT3ControlGUI:
    """GUI for controlling Opentrons Flex with live video and protocol execution."""

    # Commands that configure the deck and should be skipped in MULTI mode
    DECK_SETUP_COMMANDS = {
        'home', 'loadLabware', 'loadPipette', 'loadModule', 'loadLiquid',
        'loadLidStack', 'configureNozzleLayout'
    }

    def __init__(self, robot_ip: str = "10.90.158.110"):
        self.robot_ip = robot_ip
        self.video_url = f"http://{robot_ip}:8080/stream.mjpg"
        self.api_url = f"http://{robot_ip}:31950"

        # DEBUG: Set to False to skip Opentrons video capture for frame rate testing
        ENABLE_OT_VIDEO_CAPTURE = True
        self.DEBUG_TIMING_PRINTS = False  # Set to True to enable loop timing debug prints

        # Start video server if not running
        if ENABLE_OT_VIDEO_CAPTURE:
            self._ensure_video_server_running()

        # Video capture - runs in background thread so it never blocks main loop
        if ENABLE_OT_VIDEO_CAPTURE:
            self.cap = cv2.VideoCapture(self.video_url)
        else:
            self.cap = None
            print("[DEBUG] Opentrons video capture DISABLED")

        self._ot_latest_frame = None
        self._ot_frame_lock = threading.Lock()
        if self.cap is not None:
            self._ot_video_thread = threading.Thread(target=self._ot_video_reader_loop, daemon=True)
            self._ot_video_thread.start()

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
        # None = use robot's default speed, set with F# command (F0 resets to default)
        self.feedrate = None

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
        self.uploaded_labware_defs = set()  # Track uploaded custom labware definition URIs
        self.protocol_path = None  # Path to current protocol file (for reloading)
        self.manual_move_during_pause = False  # Track if user moved pipette during pause
        self._in_place_labware_context = (None, None)  # (labwareId, wellName) before G/MR move
        self._next_is_in_place = False  # Set by INPLACE comment, consumed by next aspirate/dispense/blowout
        self._last_pipette_action = ''  # Last pipette action type (for prepareToAspirate after blowout/dispense)
        self._skip_next_advance = False  # Skip one protocol index advance (used for prepareToAspirate)
        self.multi_mode = False  # MULTI mode: run protocols back-to-back on same run
        self._pipette_has_tip = {}  # {mount: bool} — tracks tip state per pipette
        self._deck_real_results = {}  # {match_key: real_result_dict} — stored deck setup results for MULTI mode
        self.saved_locations = {}  # Saved gantry locations (SET# command)
        self.safe_z_height = 100.0  # Safe Z height for travel moves (mm)
        self.last_protocol_move_coords = None  # Track last moveToCoordinates target from protocol
        self.coordinate_substitutions = {}  # Maps (x,y,z) tuple -> saved location slot for auto-substitution
        self.pending_g_command_continuation = False  # Continue protocol after G command move completes
        self.tiprack_offset_overrides = {}  # Maps labware_id -> {'columns': n, 'rows': n} for runtime tip offset changes
        self.plate_offset_overrides = {}  # Maps labware_id -> {'columns': n, 'rows': n} for runtime plate well offset changes

        # Interactive seeding protocol support
        self.interactive_source_well = "A1"  # Current source well for interactive seeding (updated by UI clicks)
        self.interactive_source_slot = None  # Slot of the source plate (set when clicking on plate)
        self.interactive_exit_requested = False  # Set to True when user presses 'E' to exit loop

        # Logging - use absolute path relative to script location
        script_dir = Path(__file__).parent.resolve()
        self.log_file = script_dir / "log.txt"
        self._log("COMMAND", "=== Program Started ===", write_mode="a")

        # Command queue for async execution
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.command_executing = False  # Track if a command is currently executing
        self.executing_protocol_command = False  # Track if current command is from protocol (not manual)
        self.advance_on_command_complete = False  # Track if we should advance index when command completes (survives pause)
        self.user_command_queue = []  # Queue for user-entered commands
        self.pending_home_initialization = False  # Track if we need to initialize after homing

        # Start command execution thread
        self.running = True

        # DEBUG: Set to False to disable background threads for frame rate testing
        ENABLE_BACKGROUND_THREADS = True

        if ENABLE_BACKGROUND_THREADS:
            self.executor_thread = threading.Thread(target=self._command_executor, daemon=True)
            self.executor_thread.start()
        else:
            print("[DEBUG] Background executor thread DISABLED")

        # Position update thread
        self.position_thread = threading.Thread(target=self._update_position, daemon=True)

        # Deck visualizer (overlay on main window)
        self.deck_visualizer = DeckVisualizer(width=800, height=700)
        self.visualizer_enabled = False  # Will be enabled when protocol loads
        self.analysis_result = None  # Store analysis result for visualizer
        self.visualizer_size = 0.5  # Scale factor for overlay (0.2 to 0.8) - start at 50%
        self.visualizer_min_size = 0.2
        self.visualizer_max_size = 0.8
        self.visualizer_rect = None  # (x, y, w, h) of overlay for mouse mapping
        self.visualizer_dragging = False  # True when dragging the visualizer
        self.visualizer_drag_start = None  # (mouse_x, mouse_y) when drag started
        self.visualizer_drag_start_size = None  # size when drag started
        self.visualizer_position = None  # Custom (x, y) position, None = default lower-left
        if ENABLE_BACKGROUND_THREADS:
            self.position_thread.start()
        else:
            print("[DEBUG] Background position thread DISABLED")

        # Second robot (ZMQ/microscope) integration
        # Set to False to disable microscope connection - creates single-column Opentrons-only layout
        self.ENABLE_MICROSCOPE = True
        self.ZMQ_DEBUG_PRINTS = False  # Set to True to enable ZMQ FPS debug prints

        if self.ENABLE_MICROSCOPE:
            self._init_second_robot_connection()
        else:
            print("[INFO] Microscope connection DISABLED - Opentrons-only mode")
            # Initialize minimal state for disabled microscope
            self.second_robot_frame = None
            self.second_robot_connected = False
            self.second_robot_frame_size = (1280, 960)  # Default size (not used but avoids errors)
            self.zmq_diag_start = time.time()
            self.zmq_diag_frames = 0

        # UI panel state - which panel is active for command input
        self.active_panel = 'opentrons'  # Always opentrons when microscope disabled
        self.opentrons_panel_rect = None  # (x, y, w, h) for mouse detection
        self.second_robot_panel_rect = None  # (x, y, w, h) for mouse detection
        self.second_robot_command_input = ""  # Separate command input for second robot
        self.load_protocol_button_rect = None  # (x, y, w, h) for Load Protocol button

        # Drag-line state for click-and-drag movement commands
        # When Ctrl+drag or Shift+drag in the right panel, draws a line and sends X/Y move
        self.drag_line_start = None  # (x, y) pixel coordinates where drag started
        self.drag_line_mode = None  # 'opentrons' (Ctrl) or 'microscope' (Shift)
        self.drag_line_current = None  # (x, y) current mouse position during drag
        self.drag_line_video_rect = None  # (x, y, w, h) of the second robot video area
        self.drag_line_status = ""  # Status text to display during drag
        self.DRAG_FOV_MM = 2.5  # Horizontal field of view in mm for the microscope camera

    def _ot_video_reader_loop(self):
        """Background thread: continuously reads Opentrons MJPEG frames.

        Stores the latest frame so the main loop can grab it instantly
        without blocking on the HTTP stream.
        """
        while getattr(self, 'running', True):
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue
            ret, frame = self.cap.read()
            if ret:
                with self._ot_frame_lock:
                    self._ot_latest_frame = frame
            else:
                time.sleep(0.01)  # Brief sleep on failed read to avoid busy-spin

    def _init_second_robot_connection(self):
        """Initialize ZMQ sockets for the second robot."""
        print("Initializing second robot ZMQ connections...")

        # Use separate context for image socket (matching robot_socket.py exactly)
        # This isolates image receiving from other ZMQ operations
        self.zmq_image_context = zmq.Context()
        self.zmq_image_socket = self.zmq_image_context.socket(zmq.SUB)
        self.zmq_image_socket.setsockopt(zmq.CONFLATE, 1)  # Keep only latest frame - eliminates lag
        self.zmq_image_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.zmq_image_socket.connect("tcp://localhost:5557")

        # Separate context for data and command sockets
        self.zmq_context = zmq.Context()

        # Data socket - receives telemetry/status data
        self.zmq_data_socket = self.zmq_context.socket(zmq.SUB)
        self.zmq_data_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.zmq_data_socket.connect("tcp://localhost:5558")

        # Command socket - sends gcode commands to second robot
        self.zmq_cmd_socket = self.zmq_context.socket(zmq.PUSH)
        self.zmq_cmd_socket.connect("tcp://localhost:5559")

        # Second robot state
        self.second_robot_frame = None  # Latest frame from second robot
        self.second_robot_frame_lock = threading.Lock()  # Protect frame access between threads
        self.second_robot_data = {}  # Latest data from second robot
        self.second_robot_data_lines = []  # Data lines to display
        self.second_robot_fps = 0.0
        self.second_robot_frame_count = 0
        self.second_robot_fps_time = time.time()
        self.second_robot_connected = False
        self.second_robot_frame_size = (1280, 960)  # Expected frame size (width, height)

        # ZMQ FPS diagnostic (for main loop polling)
        self.zmq_diag_start = time.time()
        self.zmq_diag_frames = 0

        # NOTE: NOT using background thread - polling in main loop instead (like robot_socket.py)
        # self.zmq_receiver_thread = threading.Thread(target=self._zmq_receiver_loop, daemon=True)
        # self.zmq_receiver_thread.start()

        print("  Image socket: tcp://localhost:5557")
        print("  Data socket: tcp://localhost:5558")
        print("  Command socket: tcp://localhost:5559")
        print("  Mode: Main loop polling (no background thread)")

    def _zmq_receiver_loop(self):
        """Background thread to receive frames and data from second robot.

        Matches robot_socket.py pattern exactly - simple blocking receive.
        """
        # Diagnostic counters - printed every 2 seconds (like robot_socket.py)
        diag_start = time.time()
        diag_frames = 0

        while self.running:
            # Simple blocking receive - exactly like robot_socket.py
            img_bytes = self.zmq_image_socket.recv()

            diag_frames += 1
            np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is None:
                continue

            with self.second_robot_frame_lock:
                self.second_robot_frame = img
            self.second_robot_connected = True
            self.second_robot_frame_count += 1

            # Calculate FPS every second
            now = time.time()
            elapsed = now - self.second_robot_fps_time
            if elapsed >= 1.0:
                self.second_robot_fps = self.second_robot_frame_count / elapsed
                self.second_robot_frame_count = 0
                self.second_robot_fps_time = now

            # Check data socket (non-blocking) - like robot_socket.py
            try:
                data_bytes = self.zmq_data_socket.recv(flags=zmq.NOBLOCK)
                data_str = data_bytes.decode('utf-8', errors='ignore')
                try:
                    self.second_robot_data = json.loads(data_str)
                    self.second_robot_data_lines = [f"{k}: {v}" for k, v in self.second_robot_data.items()]
                except json.JSONDecodeError:
                    lines = data_str.strip().split('\n')
                    self.second_robot_data_lines = lines[-5:]
            except zmq.Again:
                pass
            except Exception:
                pass

            # Print diagnostics every 2 seconds (like robot_socket.py)
            diag_elapsed = now - diag_start
            if diag_elapsed >= 2.0:
                #if self.ZMQ_DEBUG_PRINTS:
                #    print(f"[ZMQ] FPS: {diag_frames/diag_elapsed:.2f}")
                diag_start = now
                diag_frames = 0

    def _poll_zmq_frame(self):
        """Poll for ZMQ frame in main loop (like robot_socket.py).

        Called from main loop instead of using background thread.
        Returns True if a new frame was received.
        """
        try:
            # Blocking receive - exactly like robot_socket.py main loop
            img_bytes = self.zmq_image_socket.recv(flags=zmq.NOBLOCK)

            self.zmq_diag_frames += 1
            np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is None:
                if not hasattr(self, '_zmq_decode_fails'):
                    self._zmq_decode_fails = 0
                self._zmq_decode_fails += 1
                return False

            self.second_robot_frame = img
            self.second_robot_connected = True
            self.second_robot_frame_count += 1

            # Calculate FPS every second
            now = time.time()
            elapsed = now - self.second_robot_fps_time
            if elapsed >= 1.0:
                recv_count = self.zmq_diag_frames
                decode_fails = getattr(self, '_zmq_decode_fails', 0)
                #print(f"[ZMQ] recv: {recv_count}/s, good: {self.second_robot_frame_count}/s, decode_fail: {decode_fails}")
                self.second_robot_fps = self.second_robot_frame_count / elapsed
                self.second_robot_frame_count = 0
                self.second_robot_fps_time = now
                self._zmq_decode_fails = 0
                self.zmq_diag_frames = 0

            # Print diagnostics every 2 seconds
            diag_elapsed = now - self.zmq_diag_start
            if diag_elapsed >= 2.0:
                #if self.ZMQ_DEBUG_PRINTS:
                #    print(f"[ZMQ] FPS: {self.zmq_diag_frames/diag_elapsed:.2f}")
                self.zmq_diag_start = now
                self.zmq_diag_frames = 0

            return True
        except zmq.Again:
            return False  # No frame available
        except Exception as e:
            if self.second_robot_connected:
                print(f"ZMQ frame error: {e}")
            self.second_robot_connected = False
            return False

    def send_second_robot_command(self, cmd: str, quiet: bool = False):
        """Send a gcode command to the second robot.

        Args:
            cmd: The command to send
            quiet: If True, don't print the command (for high-frequency commands like mouse streaming)
        """
        try:
            self.zmq_cmd_socket.send_string(cmd.upper() + "\n")
            if not quiet:
                print(f"Sent to second robot: {cmd.upper()}")
            return True
        except Exception as e:
            print(f"Failed to send to second robot: {e}")
            return False

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
                # Stop/delete any active run on the robot before creating a new one,
                # otherwise POST /runs will return 409 RunAlreadyActive.
                try:
                    runs_resp = requests.get(
                        f"{self.api_url}/runs",
                        headers={"Opentrons-Version": "3"}
                    )
                    if runs_resp.status_code == 200:
                        for run in runs_resp.json().get("data", []):
                            if run.get("status") not in ("stopped", "succeeded", "failed"):
                                active_id = run["id"]
                                print(f"Stopping active run {active_id}...")
                                requests.post(
                                    f"{self.api_url}/runs/{active_id}/actions",
                                    json={"data": {"actionType": "stop"}},
                                    headers={"Content-Type": "application/json", "Opentrons-Version": "3"}
                                )
                                requests.delete(
                                    f"{self.api_url}/runs/{active_id}",
                                    headers={"Opentrons-Version": "3"}
                                )
                                print(f"Deleted active run {active_id}")
                except Exception as e:
                    print(f"Warning: Could not clean up active runs: {e}")

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
                # Clear uploaded labware definitions for new run
                self.uploaded_labware_defs.clear()
                print("Cleared uploaded labware definitions for new run")

            cmd_type = cmd["commandType"]
            params = cmd["params"]

            # For custom labware, upload the definition first
            if cmd_type == "loadLabware":
                namespace = params.get("namespace", "opentrons")
                if namespace != "opentrons":
                    # This is custom labware - need to upload definition first
                    definition = cmd.get("result", {}).get("definition")
                    if definition:
                        self._upload_labware_definition(definition)

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

            # Store deck setup results for MULTI mode reuse
            if cmd_type in self.DECK_SETUP_COMMANDS:
                match_key = self._get_deck_match_key(cmd_type, params)
                if match_key:
                    self._deck_real_results[match_key] = result
                    print(f"  MULTI: Stored deck result for {match_key}")

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
            else:
                # Commands that move robot but don't return position - query position explicitly
                movement_commands_without_position = [
                    "dropTip", "dropTipInPlace", "moveToAddressableArea",
                    "moveToAddressableAreaForDropTip", "pickUpTip"
                ]
                if cmd_type in movement_commands_without_position:
                    self._query_and_update_position()

            return result

        except Exception as e:
            print(f"\nException during command execution: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    def _query_and_update_position(self):
        """Query the robot's current position and update self.current_position.

        This is used after commands that move the robot but don't return position data.
        """
        if not self.run_id:
            return

        # Determine which pipette to use for position query
        pipette_id = None
        if self.active_pipette == "left" and self.instrument_ids.get("left"):
            pipette_id = self.instrument_ids["left"]
        elif self.active_pipette == "right" and self.instrument_ids.get("right"):
            pipette_id = self.instrument_ids["right"]
        elif self.instrument_ids.get("right"):
            pipette_id = self.instrument_ids["right"]
        elif self.instrument_ids.get("left"):
            pipette_id = self.instrument_ids["left"]

        if not pipette_id:
            print("Warning: Cannot query position - no pipette ID available")
            return

        try:
            save_pos_cmd = {
                "commandType": "savePosition",
                "params": {"pipetteId": pipette_id}
            }

            url = f"{self.api_url}/runs/{self.run_id}/commands?waitUntilComplete=true"
            resp = requests.post(
                url,
                json={"data": save_pos_cmd, "intent": "setup"},
                headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
                timeout=10
            )

            if resp.status_code == 201:
                result = resp.json()["data"]
                if "position" in result.get("result", {}):
                    pos = result["result"]["position"]
                    if "z" in pos and "x" in pos and "y" in pos:
                        self.current_position = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
                        print(f"Position queried after movement: X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z']:.1f}")
        except Exception as e:
            print(f"Warning: Failed to query position after movement: {e}")

    def _upload_labware_definition(self, definition: Dict[str, Any]) -> bool:
        """Upload a custom labware definition to the robot for the current run.

        Args:
            definition: The labware definition dict (from analyzer result)

        Returns:
            True if upload successful, False otherwise
        """
        if not self.run_id:
            print("Warning: Cannot upload labware definition - no run_id")
            return False

        load_name = definition.get("parameters", {}).get("loadName", "unknown")
        namespace = definition.get("namespace", "unknown")
        version = definition.get("version", 1)

        # Create unique key for this definition
        def_uri = f"{namespace}/{load_name}/{version}"

        # Skip if already uploaded
        if def_uri in self.uploaded_labware_defs:
            print(f"Skipping labware definition (already uploaded): {def_uri}")
            return True

        print(f"\n{'='*70}")
        print(f"Uploading custom labware definition: {def_uri}")
        print(f"{'='*70}")

        try:
            url = f"{self.api_url}/runs/{self.run_id}/labware_definitions"
            request_data = {"data": definition}

            print(f"POST {url}")
            self._log("HTTP", f"POST {url} (labware definition)")

            resp = requests.post(
                url,
                json=request_data,
                headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
                timeout=30
            )

            print(f"Response Status: {resp.status_code}")

            if resp.status_code >= 400:
                print(f"ERROR: Failed to upload labware definition: {resp.text}")
                self._log("RESPONSE", f"Status: {resp.status_code} ERROR: {resp.text}")
                return False

            response_json = resp.json()
            print(f"Response Body: {json.dumps(response_json, indent=2)}")
            self._log("RESPONSE", f"Status: {resp.status_code} {json.dumps(response_json)}")

            uri = response_json.get("data", {}).get("definitionUri", "")
            print(f"Labware definition uploaded successfully: {uri}")

            # Track as uploaded to avoid duplicate uploads
            self.uploaded_labware_defs.add(def_uri)
            return True

        except Exception as e:
            print(f"Exception uploading labware definition: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _apply_labware_offsets_from_protocol(self, protocol_path: Path):
        """Extract and apply labware offsets defined in the protocol.

        Detects labware.set_offset(x=..., y=..., z=...) calls in the protocol source
        using AST parsing. Maps the labware variable back to its load_labware slot,
        then applies the offset to the current run via HTTP API.

        Also supports legacy SPHEROID_PLATE_X/Y/Z_OFFSET variables.
        """
        try:
            source = protocol_path.read_text()
            tree = ast.parse(source)

            # Step 1: Build map of variable_name -> slot from load_labware assignments
            # e.g. gel_plate = protocol.load_labware(..., location="D3", ...) -> {"gel_plate": "D3"}
            var_to_slot = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr == 'load_labware':
                            target = node.targets[0]
                            if isinstance(target, ast.Name):
                                # Find the slot/location argument (2nd positional or location= kwarg)
                                slot = None
                                if len(node.value.args) >= 2:
                                    arg = node.value.args[1]
                                    if isinstance(arg, ast.Constant):
                                        slot = str(arg.value)
                                for kw in node.value.keywords:
                                    if kw.arg == 'location' and isinstance(kw.value, ast.Constant):
                                        slot = str(kw.value.value)
                                if slot:
                                    var_to_slot[target.id] = slot

            # Step 2: Find set_offset calls: var.set_offset(x=..., y=..., z=...)
            offsets_to_apply = []
            for node in ast.walk(tree):
                if not isinstance(node, ast.Expr):
                    continue
                if not isinstance(node.value, ast.Call):
                    continue
                call = node.value
                if not isinstance(call.func, ast.Attribute):
                    continue
                if call.func.attr != 'set_offset':
                    continue

                # Get the variable name
                var_name = None
                if isinstance(call.func.value, ast.Name):
                    var_name = call.func.value.id

                if not var_name or var_name not in var_to_slot:
                    print(f"  set_offset: skipping (unknown variable '{var_name}')")
                    continue

                slot = var_to_slot[var_name]

                # Extract x, y, z from keyword args
                x_off = 0.0
                y_off = 0.0
                z_off = 0.0
                for kw in call.keywords:
                    if kw.arg == 'x' and isinstance(kw.value, (ast.Constant, ast.UnaryOp)):
                        x_off = self._ast_to_number(kw.value)
                    elif kw.arg == 'y' and isinstance(kw.value, (ast.Constant, ast.UnaryOp)):
                        y_off = self._ast_to_number(kw.value)
                    elif kw.arg == 'z' and isinstance(kw.value, (ast.Constant, ast.UnaryOp)):
                        z_off = self._ast_to_number(kw.value)

                # Also check positional args: set_offset(x, y, z)
                if len(call.args) >= 1:
                    x_off = self._ast_to_number(call.args[0])
                if len(call.args) >= 2:
                    y_off = self._ast_to_number(call.args[1])
                if len(call.args) >= 3:
                    z_off = self._ast_to_number(call.args[2])

                if x_off == 0.0 and y_off == 0.0 and z_off == 0.0:
                    continue

                # Find the matching loadLabware in analyzed commands to get definitionUri
                for cmd in self.protocol_commands:
                    if cmd.get('commandType') == 'loadLabware':
                        params = cmd.get('params', {})
                        result = cmd.get('result', {})
                        location = params.get('location', {})
                        if location.get('slotName', '') == slot:
                            load_name = params.get('loadName', '')
                            definition = result.get('definition', {})
                            namespace = definition.get('namespace', 'opentrons')
                            version = definition.get('version', 1)
                            def_uri = f"{namespace}/{load_name}/{version}"
                            label = params.get('displayName', load_name)

                            offsets_to_apply.append({
                                "definitionUri": def_uri,
                                "location": {"slotName": slot},
                                "vector": {"x": x_off, "y": y_off, "z": z_off}
                            })
                            print(f"  set_offset: {label} in slot {slot}")
                            print(f"    Offset: X={x_off}, Y={y_off}, Z={z_off}")
                            break

            # Legacy: SPHEROID_PLATE_X/Y/Z_OFFSET variables
            import importlib.util
            spec = importlib.util.spec_from_file_location("protocol", str(protocol_path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            x_off = getattr(module, 'SPHEROID_PLATE_X_OFFSET', 0.0)
            y_off = getattr(module, 'SPHEROID_PLATE_Y_OFFSET', 0.0)
            z_off = getattr(module, 'SPHEROID_PLATE_Z_OFFSET', 0.0)

            if x_off != 0.0 or y_off != 0.0 or z_off != 0.0:
                for cmd in self.protocol_commands:
                    if cmd.get('commandType') == 'loadLabware':
                        params = cmd.get('params', {})
                        result = cmd.get('result', {})
                        label = params.get('displayName', '').lower()
                        load_name = params.get('loadName', '')
                        location = params.get('location', {})

                        if 'spheroid' in label or ('corning' in load_name.lower() and 'C3' in str(location)):
                            slot_name = location.get('slotName', '')
                            # Don't duplicate if already added via set_offset
                            already_added = any(o['location']['slotName'] == slot_name for o in offsets_to_apply)
                            if not already_added:
                                definition = result.get('definition', {})
                                namespace = definition.get('namespace', 'opentrons')
                                version = definition.get('version', 1)
                                def_uri = f"{namespace}/{load_name}/{version}"

                                offsets_to_apply.append({
                                    "definitionUri": def_uri,
                                    "location": {"slotName": slot_name},
                                    "vector": {"x": x_off, "y": y_off, "z": z_off}
                                })
                                print(f"  Legacy offset: {load_name} in {slot_name}")
                                print(f"    Offset: X={x_off}, Y={y_off}, Z={z_off}")
                            break

            # Apply all found offsets to the run
            for offset in offsets_to_apply:
                self._apply_labware_offset(offset)

        except Exception as e:
            print(f"Warning: Could not extract labware offsets from protocol: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def _ast_to_number(node):
        """Extract a numeric value from an AST node (handles constants and unary minus)."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
                return -float(node.operand.value)
        return 0.0

    def _apply_labware_offset(self, offset: Dict[str, Any]) -> bool:
        """Apply a single labware offset to the current run via HTTP API.

        Args:
            offset: Dict with definitionUri, location, and vector

        Returns:
            True if successful, False otherwise
        """
        if not self.run_id:
            print("Warning: Cannot apply labware offset - no run_id")
            return False

        def_uri = offset.get("definitionUri", "unknown")
        location = offset.get("location", {})
        vector = offset.get("vector", {})

        print(f"\n{'='*70}")
        print(f"Applying labware offset: {def_uri}")
        print(f"  Location: {location}")
        print(f"  Vector: X={vector.get('x', 0)}, Y={vector.get('y', 0)}, Z={vector.get('z', 0)}")
        print(f"{'='*70}")

        try:
            url = f"{self.api_url}/runs/{self.run_id}/labware_offsets"
            request_data = {"data": offset}

            print(f"POST {url}")
            self._log("HTTP", f"POST {url} (labware offset)")

            resp = requests.post(
                url,
                json=request_data,
                headers={"Content-Type": "application/json", "Opentrons-Version": "3"},
                timeout=30
            )

            print(f"Response Status: {resp.status_code}")

            if resp.status_code >= 400:
                print(f"ERROR: Failed to apply labware offset: {resp.text}")
                self._log("RESPONSE", f"Status: {resp.status_code} ERROR: {resp.text}")
                return False

            response_json = resp.json()
            print(f"Labware offset applied successfully")
            self._log("RESPONSE", f"Status: {resp.status_code} {json.dumps(response_json)}")
            return True

        except Exception as e:
            print(f"Exception applying labware offset: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _translate_ids(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate simulated IDs to real IDs."""
        # Debug: show current id_map size
        print(f"  Translating IDs (id_map has {len(self.id_map)} entries)")
        translated = {}
        for key, value in params.items():
            if key.endswith("Id") and isinstance(value, str):
                real_id = self.id_map.get(value, value)
                if real_id != value:
                    print(f"    Translating {key}: {value[:8]}... -> {real_id[:8]}...")
                elif value not in self.id_map:
                    print(f"    WARNING: No mapping for {key}: {value[:8]}... (keeping original)")
                    # Show available mappings for debugging
                    if self.id_map:
                        print(f"    Available mappings: {[k[:8]+'...' for k in list(self.id_map.keys())[:5]]}")
                translated[key] = real_id
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

        # Debug: show what we're mapping
        print(f"  _map_resource_ids for {cmd_type}:")
        print(f"    sim_result keys: {list(sim_result.keys()) if sim_result else 'empty'}")
        print(f"    real_result keys: {list(real_result.keys()) if real_result else 'empty'}")

        # Map standard IDs from result
        for id_type in ["labwareId", "pipetteId", "moduleId", "lidId"]:
            sim_id = sim_result.get(id_type)
            real_id = real_result.get(id_type)
            if sim_id and real_id:
                print(f"    ID mapping: {id_type} {sim_id[:8]}... -> {real_id[:8]}...")
                self.id_map[sim_id] = real_id
            elif sim_id:
                print(f"    WARNING: sim has {id_type}={sim_id[:8]}... but real has none")
            elif real_id:
                print(f"    INFO: real has {id_type}={real_id[:8]}... but sim has none")

        # Handle loadLidStack which returns stackLabwareId (the stack) and labwareIds (items in stack)
        if cmd_type == "loadLidStack":
            # Map the stack container itself
            sim_stack_id = sim_result.get("stackLabwareId")
            real_stack_id = real_result.get("stackLabwareId")
            if sim_stack_id and real_stack_id:
                print(f"    Stack container ID mapping: {sim_stack_id[:8]}... -> {real_stack_id[:8]}...")
                self.id_map[sim_stack_id] = real_stack_id

            # Map items in the stack
            sim_item_ids = sim_result.get("labwareIds", [])
            real_item_ids = real_result.get("labwareIds", [])
            print(f"    loadLidStack: sim has {len(sim_item_ids)} items, real has {len(real_item_ids)} items")
            for i, (sim_id, real_id) in enumerate(zip(sim_item_ids, real_item_ids)):
                print(f"    Stack item ID mapping [{i}]: {sim_id[:8]}... -> {real_id[:8]}...")
                self.id_map[sim_id] = real_id

        # For loadLabware with lid, also check for lid in definition
        if cmd_type == "loadLabware" and "lidId" in real_result:
            # The lid ID from simulation might be in params or a separate field
            sim_lid_id = sim_data.get("params", {}).get("lidId")
            real_lid_id = real_result.get("lidId")
            if sim_lid_id and real_lid_id and sim_lid_id not in self.id_map:
                print(f"  ID mapping (lid): {sim_lid_id[:8]}... -> {real_lid_id[:8]}...")
                self.id_map[sim_lid_id] = real_lid_id

    def _get_deck_match_key(self, cmd_type, params):
        """Return a key that uniquely identifies a deck setup command by its slot/mount."""
        if cmd_type == 'loadLabware':
            loc = params.get('location', {})
            return ('loadLabware', loc.get('slotName', loc.get('addressableAreaName', '')))
        elif cmd_type == 'loadPipette':
            return ('loadPipette', params.get('mount', ''))
        elif cmd_type in ('loadModule', 'loadLiquid', 'loadLidStack'):
            loc = params.get('location', {})
            return (cmd_type, loc.get('slotName', str(loc)))
        elif cmd_type == 'configureNozzleLayout':
            # Resolve pipetteId to mount for stable matching across protocols
            pip_id = params.get('pipetteId', '')
            mount = self.id_map.get(pip_id, pip_id)  # Try to translate sim->real
            # Find mount name from instrument_ids
            for m, pid in self.instrument_ids.items():
                if pid == mount or pid == pip_id:
                    return ('configureNozzleLayout', m)
            return ('configureNozzleLayout', pip_id)
        return None

    def open_protocol_dialog(self):
        """Open a file dialog to select and load a protocol."""
        # Create a hidden tkinter root window
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        root.attributes('-topmost', True)  # Bring dialog to front

        # Default protocol folder (lowercase 'protocols')
        default_protocol_dir = Path(r"C:\Users\David Sachs\Documents\opentrons_api\protocols")
        if not default_protocol_dir.exists():
            # Try with capital P as fallback
            default_protocol_dir = Path(r"C:\Users\David Sachs\Documents\opentrons_api\Protocols")
        if not default_protocol_dir.exists():
            default_protocol_dir = Path.cwd()

        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Select Opentrons Protocol",
            filetypes=[
                ("Python files", "*.py"),
                ("All files", "*.*")
            ],
            initialdir=default_protocol_dir
        )

        root.destroy()  # Clean up the hidden window

        if file_path:
            protocol_path = Path(file_path)
            if protocol_path.exists():
                # Show loading message immediately
                self.status_message = "Loading protocol..."
                self.error_message = ""
                print(f"\nLoading protocol: {protocol_path}")
                return self.load_protocol(protocol_path)
            else:
                self.error_message = f"File not found: {file_path}"
                return False
        else:
            self.status_message = "Protocol load cancelled"
            return False

    def open_csv_dialog(self) -> bool:
        """Open a file dialog to select a media change CSV file."""
        # Create a hidden tkinter root window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        # Default to opentrons_api directory for CSV files
        default_dir = Path(r"C:\Users\David Sachs\Documents\opentrons_api")
        if not default_dir.exists():
            default_dir = Path.cwd()

        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Select Media Change CSV",
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ],
            initialdir=default_dir
        )

        root.destroy()

        if file_path:
            csv_path = Path(file_path)
            if csv_path.exists():
                self.status_message = "Loading CSV..."
                print(f"\nLoading media change CSV: {csv_path}")
                return self.load_media_change_csv(csv_path)
            else:
                self.error_message = f"File not found: {file_path}"
                return False
        else:
            self.status_message = "CSV load cancelled"
            return False

    def _parse_media_change_csv(self, csv_path: Path) -> Tuple[Dict[str, str], Dict[str, List[Tuple[str, float]]]]:
        """
        Parse a media change CSV file.

        CSV format:
        - Lines starting with # are comments
        - A1_tube,reagent_name - defines reagent location in tube rack
        - A1_plate,reagent1,volume1,reagent2,volume2,... - defines plate layout

        Returns:
            (reagent_locations, plate_layout) tuple
        """
        reagent_locations = {}
        plate_layout = {}

        with open(csv_path, 'r') as f:
            reader = csv.reader(f)

            for row in reader:
                if not row or not row[0].strip():
                    continue

                first_cell = row[0].strip()

                # Skip comments
                if first_cell.startswith('#'):
                    continue

                # Tube rack entries: A1_tube,reagent_name
                if '_tube' in first_cell:
                    well = first_cell.replace('_tube', '')
                    if len(row) > 1:
                        reagent_name = row[1].strip()
                        reagent_locations[reagent_name] = well

                # Plate layout entries: A1_plate,reagent1,vol1,reagent2,vol2,...
                elif '_plate' in first_cell:
                    well = first_cell.replace('_plate', '')
                    reagents = []
                    i = 1
                    while i + 1 < len(row):
                        reagent_name = row[i].strip()
                        try:
                            volume = float(row[i + 1].strip())
                            if reagent_name:
                                # Use int if volume is a whole number
                                vol = int(volume) if volume == int(volume) else volume
                                reagents.append((reagent_name, vol))
                        except (ValueError, IndexError):
                            pass
                        i += 2

                    if reagents:
                        plate_layout[well] = reagents

        return reagent_locations, plate_layout

    def _generate_protocol_data_code(self, reagent_locations: Dict[str, str],
                                      plate_layout: Dict[str, List[Tuple[str, float]]]) -> str:
        """Generate Python code for REAGENT_LOCATIONS and PLATE_LAYOUT."""
        lines = []

        # Reagent locations
        lines.append("# Reagent tube locations in the 24-tube rack")
        lines.append("# Format: reagent_name -> tube well")
        lines.append("REAGENT_LOCATIONS = {")
        for reagent, well in sorted(reagent_locations.items()):
            lines.append(f"    '{reagent}': '{well}',")
        lines.append("}")
        lines.append("")

        # Plate layout
        lines.append("# Plate layout: which reagents and volumes go in each well")
        lines.append("# Format: well -> [(reagent_name, volume_uL), ...]")
        lines.append("PLATE_LAYOUT = {")

        # Sort wells by column then row
        def well_sort_key(well):
            row = well[0]
            col = int(well[1:])
            return (col, row)

        for well in sorted(plate_layout.keys(), key=well_sort_key):
            reagents = plate_layout[well]
            reagent_str = ", ".join(f"('{r}', {v})" for r, v in reagents)
            lines.append(f"    '{well}': [{reagent_str}],")

        lines.append("}")
        lines.append("")

        # Columns used
        lines.append("# Columns used (derived from PLATE_LAYOUT)")
        lines.append("COLUMNS_USED = sorted(set(int(''.join(filter(str.isdigit, well))) for well in PLATE_LAYOUT.keys()))")

        return "\n".join(lines)

    def load_media_change_csv(self, csv_path: Path) -> bool:
        """
        Load a media change CSV and update the spheroid media change protocol.

        This parses the CSV, generates new REAGENT_LOCATIONS and PLATE_LAYOUT,
        and creates a modified protocol file that is then loaded.
        """
        try:
            # Parse CSV
            reagent_locations, plate_layout = self._parse_media_change_csv(csv_path)

            if not reagent_locations or not plate_layout:
                self.error_message = "CSV file is empty or invalid format"
                print(f"ERROR: {self.error_message}")
                return False

            print(f"Parsed CSV: {len(reagent_locations)} reagents, {len(plate_layout)} wells")
            print(f"  Reagents: {', '.join(reagent_locations.keys())}")

            # Find the base protocol
            base_protocol = Path(r"C:\Users\David Sachs\Documents\opentrons_api\Protocols\spheroid_media_change.py")
            if not base_protocol.exists():
                self.error_message = f"Base protocol not found: {base_protocol}"
                print(f"ERROR: {self.error_message}")
                return False

            # Read the base protocol
            with open(base_protocol, 'r') as f:
                protocol_content = f.read()

            # Generate new data code
            new_data_code = self._generate_protocol_data_code(reagent_locations, plate_layout)

            # Find and replace the REAGENT_LOCATIONS and PLATE_LAYOUT sections
            # Pattern to match from "REAGENT_LOCATIONS = {" to "COLUMNS_USED = ..."
            pattern = (
                r"# Reagent tube locations in the 24-tube rack\n"
                r"# Format: reagent_name -> tube well\n"
                r"REAGENT_LOCATIONS = \{[^}]+\}\n\n"
                r"# Plate layout: which reagents and volumes go in each well\n"
                r"# Format: well -> \[\(reagent_name, volume_uL\), \.\.\.\]\n"
                r"PLATE_LAYOUT = \{[^}]+\}\n\n"
                r"# Columns used \(derived from PLATE_LAYOUT\)\n"
                r"COLUMNS_USED = [^\n]+"
            )

            # Replace with new data
            new_content = re.sub(pattern, new_data_code, protocol_content, flags=re.DOTALL)

            if new_content == protocol_content:
                # Pattern didn't match, try simpler approach
                print("Warning: Could not find exact pattern, trying alternative approach...")

                # Find REAGENT_LOCATIONS section start
                rl_start = protocol_content.find("REAGENT_LOCATIONS = {")
                cu_end = protocol_content.find("COLUMNS_USED = sorted(")
                if rl_start > 0 and cu_end > rl_start:
                    # Find end of COLUMNS_USED line
                    cu_line_end = protocol_content.find("\n", cu_end)
                    if cu_line_end > 0:
                        # Find the comment lines before REAGENT_LOCATIONS
                        comment_start = protocol_content.rfind("# Reagent tube locations", 0, rl_start)
                        if comment_start > 0:
                            rl_start = comment_start

                        new_content = (
                            protocol_content[:rl_start] +
                            new_data_code +
                            protocol_content[cu_line_end:]
                        )

            # Update protocol name in metadata to indicate it's from CSV
            csv_name = csv_path.stem
            new_content = re.sub(
                r"'protocolName': '[^']+'",
                f"'protocolName': 'Spheroid Media Change - {csv_name}'",
                new_content
            )

            # Create output file (in same directory as CSV with _protocol suffix)
            output_path = csv_path.parent / f"{csv_path.stem}_protocol.py"

            # Write the modified protocol
            with open(output_path, 'w') as f:
                f.write(new_content)

            print(f"Generated protocol: {output_path}")
            self.status_message = f"Generated: {output_path.name}"

            # Load the generated protocol
            return self.load_protocol(output_path)

        except Exception as e:
            self.error_message = f"Error loading CSV: {e}"
            print(f"ERROR: {self.error_message}")
            import traceback
            traceback.print_exc()
            return False

    def _preprocess_protocol_for_inplace(self, protocol_path: Path) -> Path:
        """Auto-detect in-place aspirate/dispense/blow_out calls in the protocol source
        and inject INPLACE comments before them. Also injects dummy well references into
        the calls so the analyzer has proper well context (the INPLACE flag causes
        conversion to InPlace at runtime regardless). Returns path to a preprocessed
        temp file (or the original path if no in-place calls found).

        Detection logic:
        - aspirate(vol) or aspirate(vol, flow_rate=X) → in-place (no 2nd positional arg)
        - aspirate(vol, location) → explicit (has 2nd positional arg or location= kwarg)
        - dispense: same as aspirate
        - blow_out() → in-place; blow_out(location) → explicit
        """
        try:
            source = protocol_path.read_text()
            tree = ast.parse(source)
        except Exception as e:
            print(f"  INPLACE preprocessor: could not parse {protocol_path.name}: {e}")
            return protocol_path

        # Find the protocol context variable name from run(protocol)
        protocol_var = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'run':
                if node.args.args:
                    protocol_var = node.args.args[0].arg
                break

        if not protocol_var:
            print("  INPLACE preprocessor: no run() function found, skipping")
            return protocol_path

        # Find a non-tiprack labware variable for dummy well references.
        # Look for assignments like: var = protocol.load_labware('name', 'slot')
        # where name doesn't contain 'tiprack'
        dummy_labware_var = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                    if node.value.func.attr == 'load_labware' and node.value.args:
                        # Check if the labware name contains 'tiprack'
                        first_arg = node.value.args[0]
                        labware_name = ""
                        if isinstance(first_arg, ast.Constant):
                            labware_name = str(first_arg.value)
                        if 'tiprack' not in labware_name.lower():
                            target = node.targets[0]
                            if isinstance(target, ast.Name):
                                dummy_labware_var = target.id
                                break

        # Find line numbers of in-place pipette calls (and store method info)
        in_place_lines = {}  # lineno -> method name
        for node in ast.walk(tree):
            if not isinstance(node, ast.Expr):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            call = node.value
            if not isinstance(call.func, ast.Attribute):
                continue
            method = call.func.attr

            if method in ('aspirate', 'dispense'):
                # 2nd positional arg = location
                has_loc = len(call.args) >= 2
                if not has_loc:
                    has_loc = any(kw.arg == 'location' for kw in call.keywords)
                if not has_loc:
                    in_place_lines[node.lineno] = method
            elif method == 'blow_out':
                # 1st positional arg = location
                has_loc = len(call.args) >= 1
                if not has_loc:
                    has_loc = any(kw.arg == 'location' for kw in call.keywords)
                if not has_loc:
                    in_place_lines[node.lineno] = method

        if not in_place_lines:
            print("  INPLACE preprocessor: no in-place calls found")
            return protocol_path

        print(f"  INPLACE preprocessor: found {len(in_place_lines)} in-place calls at lines {sorted(in_place_lines.keys())}")
        if dummy_labware_var:
            print(f"  INPLACE preprocessor: using '{dummy_labware_var}' for dummy well references")

        # Inject protocol.comment("INPLACE") before each in-place line,
        # and add dummy well reference to the call so the analyzer has well context.
        lines = source.split('\n')
        new_lines = []
        for i, line in enumerate(lines):
            lineno = i + 1  # AST uses 1-based line numbers
            if lineno in in_place_lines:
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + f'{protocol_var}.comment("INPLACE")')

                # If we have a dummy labware, inject it as a location argument
                # so the analyzer has well context. At runtime, INPLACE flag
                # causes conversion to InPlace regardless.
                if dummy_labware_var:
                    method = in_place_lines[lineno]
                    dummy_well = f'{dummy_labware_var}["A1"]'
                    if method in ('aspirate', 'dispense'):
                        # Insert dummy well as 2nd positional arg (after volume)
                        # Pattern: .method(vol  or  .method(vol, flow_rate=...)
                        line = re.sub(
                            r'(\.' + method + r'\s*\([^,)]+)',
                            r'\1, ' + dummy_well,
                            line,
                            count=1
                        )
                    elif method == 'blow_out':
                        # Insert dummy well as 1st positional arg
                        line = re.sub(
                            r'(\.blow_out\s*\()',
                            r'\1' + dummy_well,
                            line,
                            count=1
                        )

            new_lines.append(line)

        # Write to temp file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.py', prefix='proto_')
        os.close(temp_fd)
        temp_path = Path(temp_path)
        temp_path.write_text('\n'.join(new_lines))
        print(f"  INPLACE preprocessor: wrote preprocessed protocol to {temp_path}")
        return temp_path

    def load_protocol(self, protocol_path: Path):
        """Load a protocol for execution."""
        self.status_message = f"Loading protocol: {protocol_path.name}"
        print(f"\n{self.status_message}")

        # Store protocol path for reloading
        self.protocol_path = protocol_path

        # Log the protocol code
        try:
            with open(protocol_path, 'r') as f:
                protocol_code = f.read()
            self._log("PROTOCOL", f"Loaded {protocol_path.name}: {protocol_code}")
        except Exception as e:
            print(f"Warning: Could not log protocol file: {e}")

        try:
            # Pre-process protocol to auto-detect in-place aspirate/dispense calls
            analysis_path = self._preprocess_protocol_for_inplace(protocol_path)

            # Analyze protocol (using preprocessed temp file if in-place calls were found)
            analyzer = ProtocolAnalyzer(robot_ip=self.robot_ip, use_local=False)
            result = analyzer.analyze(analysis_path)

            # Clean up temp file if one was created
            if analysis_path != protocol_path:
                try:
                    analysis_path.unlink()
                except Exception:
                    pass

            if result.status != "ok":
                self.error_message = f"Protocol analysis failed: {result.errors}"
                print(f"ERROR: {self.error_message}")
                self._log("ANALYSIS", f"Protocol analysis failed: {result.errors}")
                return False

            self.protocol_commands = result.commands
            self.current_command_index = 0
            self.analysis_result = result  # Store for visualizer
            self.tiprack_offset_overrides = {}  # Clear runtime tip offset overrides on protocol load
            self.plate_offset_overrides = {}  # Clear runtime plate offset overrides on protocol load
            # Don't clear saved_locations — let protocols use CLEAR explicitly if needed

            # MULTI mode: reuse existing run, skip deck setup, map IDs
            if self.multi_mode and self.run_id:
                print(f"\n*** MULTI MODE: Reusing run {self.run_id} ***")
                # Clear old sim->real mappings (new protocol has new sim IDs)
                self.id_map = {}

                # Skip deck setup commands and build ID mappings from stored results
                skipped = 0
                while self.current_command_index < len(self.protocol_commands):
                    cmd = self.protocol_commands[self.current_command_index]
                    cmd_type = cmd.get("commandType", "")

                    # Skip comments interspersed in setup
                    if cmd_type == "comment":
                        self.current_command_index += 1
                        skipped += 1
                        continue

                    # Stop at first non-setup command
                    if cmd_type not in self.DECK_SETUP_COMMANDS:
                        break

                    # Map this setup command's simulated IDs to existing real IDs
                    params = cmd.get("params", {})
                    match_key = self._get_deck_match_key(cmd_type, params)
                    if match_key and match_key in self._deck_real_results:
                        stored_result = self._deck_real_results[match_key]
                        # Add simulated_result so _map_resource_ids can extract sim IDs
                        cmd["simulated_result"] = cmd
                        self._map_resource_ids(cmd_type, cmd, stored_result)
                        print(f"  MULTI: Mapped {cmd_type} {match_key} -> existing IDs")
                    elif match_key:
                        print(f"  MULTI WARNING: No stored result for {cmd_type} {match_key}")
                    else:
                        print(f"  MULTI: Skipping {cmd_type} (no ID mapping needed)")

                    self.current_command_index += 1
                    skipped += 1

                print(f"  MULTI: Skipped {skipped} setup commands, starting at index {self.current_command_index}")

                # Don't reinitialize visualizer (deck layout unchanged)
                # Don't create a new run

                # Count only non-comment, non-setup steps remaining
                remaining = self.protocol_commands[self.current_command_index:]
                step_count = sum(1 for c in remaining if c["commandType"] != "comment")
                self.status_message = f"MULTI: Protocol loaded: {step_count} steps (setup skipped)"
                print(f"{self.status_message}")
                print(f"Run ID: {self.run_id} (reused)")
            else:
                # Normal mode: initialize visualizer and create new run
                self._init_visualizer(protocol_path, result)

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
                # Clear uploaded labware definitions for new run
                self.uploaded_labware_defs.clear()

                # Apply labware offsets from protocol (if defined)
                self._apply_labware_offsets_from_protocol(protocol_path)

                # Count only non-comment steps
                step_count = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")
                self.status_message = f"Protocol loaded: {step_count} steps"
                print(f"{self.status_message}")
                print(f"Run ID: {self.run_id}")
            return True

        except Exception as e:
            self.error_message = f"Error loading protocol: {e}"
            print(f"ERROR: {self.error_message}")
            self._log("ANALYSIS", f"Error loading protocol: {e}")
            return False

    def _init_visualizer(self, protocol_path: Path, analysis_result):
        """Initialize the deck visualizer with protocol data."""
        try:
            # Try to extract plate layout from protocol (protocol-specific)
            plate_layout = {}
            reagent_locations = {}
            base_media_volume = 150
            protocol_name = ""  # Initialize here so it's available later
            module = None  # Track if module was loaded

            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("protocol", str(protocol_path))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                plate_layout = getattr(module, 'PLATE_LAYOUT', {})
                reagent_locations = getattr(module, 'REAGENT_LOCATIONS', {})
                base_media_volume = getattr(module, 'BASE_MEDIA_VOLUME', 150)

                # Extract protocol name from metadata dict in protocol file
                metadata = getattr(module, 'metadata', {})
                if isinstance(metadata, dict):
                    protocol_name = metadata.get('protocolName', '')

                # Extract all offset configurations
                labware_offsets = {}

                # First, find tiprack locations from the analysis result
                tiprack_50_slot = None
                tiprack_1000_slot = None
                tube_rack_slot = None

                for lw in analysis_result.labware:
                    load_name = lw.get('definitionUri', '').split('/')[-2] if '/' in lw.get('definitionUri', '') else ''
                    if not load_name:
                        load_name = lw.get('loadName', '')
                    location = lw.get('location', {})
                    slot = location.get('slotName', '') if isinstance(location, dict) else str(location)

                    if 'tiprack' in load_name.lower() and '50' in load_name:
                        tiprack_50_slot = slot
                    elif 'tiprack' in load_name.lower() and '1000' in load_name:
                        tiprack_1000_slot = slot
                    elif 'tuberack' in load_name.lower() or 'tube_rack' in load_name.lower():
                        tube_rack_slot = slot

                # Tip rack offsets (columns, rows) - apply to detected slots
                tiprack_50_offset = getattr(module, 'TIPRACK_50_OFFSET', (0, 0))
                tiprack_1000_offset = getattr(module, 'TIPRACK_1000_OFFSET', (0, 0))
                if tiprack_50_offset != (0, 0) and tiprack_50_slot:
                    labware_offsets[tiprack_50_slot] = {'columns': tiprack_50_offset[0], 'rows': tiprack_50_offset[1]}
                    print(f"  Tiprack 50uL offset: {tiprack_50_offset} -> slot {tiprack_50_slot}")
                if tiprack_1000_offset != (0, 0) and tiprack_1000_slot:
                    labware_offsets[tiprack_1000_slot] = {'columns': tiprack_1000_offset[0], 'rows': tiprack_1000_offset[1]}
                    print(f"  Tiprack 1000uL offset: {tiprack_1000_offset} -> slot {tiprack_1000_slot}")

                # Reservoir offsets (well index)
                base_media_start = getattr(module, 'BASE_MEDIA_RESERVOIR_START_WELL', 0)
                waste_start = getattr(module, 'WASTE_RESERVOIR_START_WELL', 0)
                if base_media_start > 0:
                    labware_offsets['D2'] = {'well_index': base_media_start}
                if waste_start > 0:
                    labware_offsets['B2'] = {'well_index': waste_start}

                # Plate column offsets
                new_media_col_offset = getattr(module, 'NEW_MEDIA_PLATE_COLUMN_OFFSET', 0)
                spheroid_col_offset = getattr(module, 'SPHEROID_PLATE_COLUMN_OFFSET', 0)
                if new_media_col_offset > 0:
                    labware_offsets['C2'] = {'columns': new_media_col_offset, 'rows': 0}
                if spheroid_col_offset > 0:
                    labware_offsets['C3'] = {'columns': spheroid_col_offset, 'rows': 0}

                # Tube rack offset (starting tube position) - apply to detected slot
                tube_rack_offset = getattr(module, 'TUBE_RACK_OFFSET', (0, 0))
                if tube_rack_offset != (0, 0) and tube_rack_slot:
                    labware_offsets[tube_rack_slot] = {'columns': tube_rack_offset[0], 'rows': tube_rack_offset[1]}
                    print(f"  Tube rack offset: {tube_rack_offset} -> slot {tube_rack_slot}")

            except Exception as e:
                print(f"Note: Could not extract plate layout from protocol: {e}")
                labware_offsets = {}

            # Fall back to filename for protocol name if not extracted from metadata
            if not protocol_name:
                protocol_name = protocol_path.stem.replace('_', ' ').title()

            # Load visualizer data
            self.deck_visualizer.load_from_protocol_data(
                analysis_result.labware,
                plate_layout,
                reagent_locations,
                base_media_volume,
                commands=analysis_result.commands,
                labware_offsets=labware_offsets,
                protocol_name=protocol_name
            )

            # Enable visualizer (overlay mode - no separate window)
            self.visualizer_enabled = True
            self._visualizer_error_shown = False  # Reset error flag
            print(f"Deck visualizer initialized: {len(analysis_result.labware)} labware items")
            print(f"  Labware in visualizer: {len(self.deck_visualizer.labware)}")
            for slot, lw in sorted(self.deck_visualizer.labware.items()):
                print(f"    {slot}: {lw.display_name} ({lw.labware_type})")
            print(f"  Drag visualizer to move, drag corner to resize")

        except Exception as e:
            print(f"Warning: Could not initialize deck visualizer: {e}")
            self.visualizer_enabled = False

    def _get_visualizer_overlay(self, main_frame: np.ndarray) -> np.ndarray:
        """Render visualizer and overlay it on the main frame in lower-left corner."""
        if not self.visualizer_enabled:
            return main_frame

        try:
            # Update animation state based on current protocol step
            if self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                cmd = self.protocol_commands[self.current_command_index]
                self.deck_visualizer.update_animation(self.current_command_index, cmd)
            else:
                self.deck_visualizer.update_animation(self.current_command_index, None)

            # Render visualizer at full size
            vis_frame = self.deck_visualizer.render()

            # Calculate scaled size based on main frame height
            main_h, main_w = main_frame.shape[:2]
            vis_h, vis_w = vis_frame.shape[:2]

            # Scale based on main frame height and user-adjustable size factor
            target_h = int(main_h * self.visualizer_size)
            scale = target_h / vis_h
            target_w = int(vis_w * scale)

            # Ensure it doesn't exceed main frame width (with some margin)
            max_w = int(main_w * 0.6)
            if target_w > max_w:
                target_w = max_w
                scale = target_w / vis_w
                target_h = int(vis_h * scale)

            # Resize visualizer frame
            vis_scaled = cv2.resize(vis_frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

            # Position: use custom position if set, otherwise default to lower-left
            margin = 10
            if self.visualizer_position is not None:
                x_pos, y_pos = self.visualizer_position
                # Keep within bounds
                x_pos = max(0, min(x_pos, main_w - target_w))
                y_pos = max(0, min(y_pos, main_h - target_h))
            else:
                x_pos = margin
                y_pos = main_h - target_h - margin

            # Blend with semi-transparency for professional look
            # Create ROI in main frame
            roi = main_frame[y_pos:y_pos+target_h, x_pos:x_pos+target_w]

            # Blend: 85% visualizer, 15% background for slight see-through
            alpha = 0.85
            blended = cv2.addWeighted(vis_scaled, alpha, roi, 1 - alpha, 0)

            # Add subtle border (highlight if dragging)
            border_color = (0, 200, 200) if self.visualizer_dragging else (100, 100, 100)
            cv2.rectangle(blended, (0, 0), (target_w-1, target_h-1), border_color, 2 if self.visualizer_dragging else 1)

            # Add resize handle in upper-right corner (small triangle)
            handle_size = 15
            pts = np.array([
                [target_w - handle_size, 0],
                [target_w - 1, 0],
                [target_w - 1, handle_size]
            ], np.int32)
            cv2.fillPoly(blended, [pts], (150, 150, 150))

            # Place back on main frame
            main_frame[y_pos:y_pos+target_h, x_pos:x_pos+target_w] = blended

            # Store overlay rect for mouse mapping (scale factor for coordinate translation)
            self.visualizer_rect = (x_pos, y_pos, target_w, target_h, scale)

            # Add size indicator in corner of overlay
            font = cv2.FONT_HERSHEY_SIMPLEX
            size_text = f"{int(self.visualizer_size*100)}%"
            cv2.putText(main_frame, size_text, (x_pos + 5, y_pos + 20),
                       font, 0.4, (150, 150, 150), 1, cv2.LINE_AA)

            return main_frame

        except Exception as e:
            # Print error once, then disable to avoid spamming
            if not hasattr(self, '_visualizer_error_shown'):
                print(f"Warning: Visualizer render error: {e}")
                import traceback
                traceback.print_exc()
                self._visualizer_error_shown = True
            return main_frame

    def _handle_visualizer_mouse(self, event: int, x: int, y: int, flags: int, param):
        """Handle mouse events for panel switching and deck visualizer interactions."""
        # Track mouse position for hover effects
        self._mouse_pos = (x, y)

        # Handle drag-line feature for right panel (Ctrl/Shift + click and drag)
        if self._handle_drag_line_mouse(event, x, y, flags):
            return  # Drag line handled the event

        # Check for Load Protocol button click
        if event == cv2.EVENT_LBUTTONDOWN and self.load_protocol_button_rect:
            bx, by, bw, bh = self.load_protocol_button_rect
            if bx <= x <= bx + bw and by <= y <= by + bh:
                print("\nLoad Protocol button clicked...")
                self.open_protocol_dialog()
                return  # Don't process other clicks

        # Update active panel only on click (not hover)
        if event == cv2.EVENT_LBUTTONDOWN:
            self._update_active_panel_from_click(x, y)

        # Handle visualizer-specific interactions only if enabled
        if not self.visualizer_enabled or not self.visualizer_rect:
            return

        ox, oy, ow, oh, scale = self.visualizer_rect

        # Check if in resize handle area (upper-right corner)
        handle_size = 20
        in_resize_handle = (ox + ow - handle_size <= x <= ox + ow and
                           oy <= y <= oy + handle_size)

        # Check if mouse is within overlay bounds
        in_overlay = ox <= x <= ox + ow and oy <= y <= oy + oh

        if event == cv2.EVENT_LBUTTONDOWN:
            if in_resize_handle:
                # Start resize drag
                self.visualizer_dragging = True
                self.visualizer_drag_start = (x, y)
                self.visualizer_drag_start_size = self.visualizer_size
                self.visualizer_drag_mode = 'resize'
            elif in_overlay:
                # Map to visualizer coordinates
                vis_x = int((x - ox) / scale)
                vis_y = int((y - oy) / scale)

                # Check if clicking on a tiprack tip or plate well first
                clicked_on_item = False
                if self.deck_visualizer.hovered_slot:
                    labware = self.deck_visualizer.labware.get(self.deck_visualizer.hovered_slot)
                    if labware and labware.labware_type == 'tiprack':
                        tip_pos = self.deck_visualizer.get_tiprack_tip_at_pos(
                            self.deck_visualizer.hovered_slot, vis_x, vis_y)
                        if tip_pos:
                            clicked_on_item = True
                            # Forward click to visualizer for tip selection
                            self.deck_visualizer.handle_mouse(event, vis_x, vis_y, flags, param)
                            # Check for pending offset change
                            if self.deck_visualizer.pending_offset_change:
                                change = self.deck_visualizer.pending_offset_change
                                self.deck_visualizer.pending_offset_change = None
                                slot = change['slot']
                                col = change['columns']
                                row = change['rows']
                                well_name = f"{chr(ord('A')+row)}{col+1}"
                                self.status_message = f"Tip offset: {slot} starts at {well_name}"
                                print(f"Tip offset set: {slot} -> col={col}, row={row} ({well_name})")

                                # Store the offset override - find the labware_id for this slot
                                labware_info = self.deck_visualizer.labware.get(slot)
                                if labware_info and labware_info.id:
                                    self.tiprack_offset_overrides[labware_info.id] = {
                                        'columns': col,
                                        'rows': row,
                                        'slot': slot
                                    }
                                    print(f"  Stored override for labware_id: {labware_info.id}")

                    elif labware and labware.labware_type == 'plate':
                        well_pos = self.deck_visualizer.get_plate_well_at_pos(
                            self.deck_visualizer.hovered_slot, vis_x, vis_y)
                        if well_pos:
                            clicked_on_item = True
                            # Forward click to visualizer for well selection
                            self.deck_visualizer.handle_mouse(event, vis_x, vis_y, flags, param)
                            # Check for pending offset change
                            if self.deck_visualizer.pending_offset_change:
                                change = self.deck_visualizer.pending_offset_change
                                self.deck_visualizer.pending_offset_change = None
                                slot = change['slot']
                                col = change['columns']
                                row = change['rows']
                                well_name = f"{chr(ord('A')+row)}{col+1}"
                                self.status_message = f"Plate offset: {slot} starts at {well_name}"
                                print(f"Plate offset set: {slot} -> col={col}, row={row} ({well_name})")

                                # Also update interactive source well for seeding protocols
                                self.interactive_source_well = well_name
                                self.interactive_source_slot = slot
                                print(f"  Interactive source well updated: {well_name} in slot {slot}")

                                # Store the offset override - find the labware_id for this slot
                                labware_info = self.deck_visualizer.labware.get(slot)
                                if labware_info and labware_info.id:
                                    # Find the first well the protocol uses for this labware
                                    # to use as baseline for relative offset mode
                                    baseline_row = 0
                                    baseline_col = 0
                                    real_labware_id = labware_info.id
                                    for pcmd in self.protocol_commands:
                                        pcmd_labware = pcmd.get("params", {}).get("labwareId", "")
                                        # Check both real ID and any sim ID that maps to it
                                        maps_to_this = (pcmd_labware == real_labware_id or
                                                        self.id_map.get(pcmd_labware) == real_labware_id)
                                        if maps_to_this and pcmd.get("commandType") in ("aspirate", "dispense", "moveToWell", "blowout"):
                                            first_well = pcmd.get("params", {}).get("wellName", "A1")
                                            baseline_row = ord(first_well[0].upper()) - ord('A')
                                            baseline_col = int(first_well[1:]) - 1
                                            break

                                    self.plate_offset_overrides[labware_info.id] = {
                                        'columns': col,
                                        'rows': row,
                                        'slot': slot,
                                        'direct': False,  # Relative mode: maintains well-to-well offsets
                                        'baseline_col': baseline_col,
                                        'baseline_row': baseline_row
                                    }
                                    baseline_well = f"{chr(ord('A') + baseline_row)}{baseline_col + 1}"
                                    print(f"  Stored plate override for labware_id: {labware_info.id} (relative mode, baseline={baseline_well})")

                if not clicked_on_item:
                    # Forward to deck visualizer for labware dragging
                    self.deck_visualizer.handle_mouse(event, vis_x, vis_y, flags, param)

        elif event == cv2.EVENT_LBUTTONUP:
            self.visualizer_dragging = False
            self.visualizer_drag_start = None
            self.visualizer_drag_start_size = None

            # Forward mouse up to deck visualizer for labware drag completion
            if in_overlay:
                vis_x = int((x - ox) / scale)
                vis_y = int((y - oy) / scale)
                self.deck_visualizer.handle_mouse(event, vis_x, vis_y, flags, param)

                # Check for pending labware move
                if self.deck_visualizer.pending_labware_move:
                    move = self.deck_visualizer.pending_labware_move
                    self.deck_visualizer.pending_labware_move = None
                    from_slot = move['from_slot']
                    to_slot = move['to_slot']
                    self.status_message = f"Moved labware: {from_slot} <-> {to_slot}"
                    print(f"Labware moved: {from_slot} <-> {to_slot}")

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.visualizer_dragging and self.visualizer_drag_start:
                dx = x - self.visualizer_drag_start[0]
                dy = y - self.visualizer_drag_start[1]

                if getattr(self, 'visualizer_drag_mode', None) == 'resize':
                    # Resize based on drag distance (diagonal)
                    drag_dist = (dx + dy) / 2  # Average of x and y movement
                    size_change = drag_dist / 500  # Scale sensitivity
                    new_size = self.visualizer_drag_start_size + size_change
                    self.visualizer_size = max(self.visualizer_min_size,
                                               min(self.visualizer_max_size, new_size))

            if in_overlay:
                # Map to visualizer coordinates (accounting for scale)
                vis_x = int((x - ox) / scale)
                vis_y = int((y - oy) / scale)
                # Forward to deck visualizer's mouse handler for hover effects and labware dragging
                self.deck_visualizer.handle_mouse(event, vis_x, vis_y, flags, param)
            else:
                # Clear hover state when outside overlay
                self.deck_visualizer.hovered_reagent = None
                self.deck_visualizer.hovered_slot = None
                # Cancel any ongoing labware drag if mouse leaves the overlay
                if self.deck_visualizer.dragging_labware:
                    self.deck_visualizer.dragging_labware = None
                    self.deck_visualizer.drag_start_pos = None

    def _handle_drag_line_mouse(self, event: int, x: int, y: int, flags: int) -> bool:
        """
        Handle mouse drag in the right panel to draw lines and send movement commands.

        - Ctrl + drag: Send X/Y movement to Opentrons (yellow line)
        - Shift + drag: Send X/Y movement to microscope (second robot) via ZMQ (magenta line)
        - No modifier + drag: Stream mouse events (MOUSEDOWN, MOUSEX/MOUSEY, MOUSEUP) to microscope (cyan line)

        The line is scaled based on a 2.5mm horizontal field of view.
        Y axis is inverted (dragging up = positive Y movement).
        Returns True if the event was handled, False otherwise.
        """
        # Check if we're in the right panel (second robot video area)
        # Use second_robot_panel_rect as fallback if video rect not yet set
        if self.drag_line_video_rect:
            vx, vy, vw, vh = self.drag_line_video_rect
        elif self.second_robot_panel_rect:
            # Fallback to panel rect if video rect not initialized yet
            vx, vy, vw, vh = self.second_robot_panel_rect
        else:
            return False

        in_video_area = vx <= x <= vx + vw and vy <= y <= vy + vh

        # Check modifier keys
        ctrl_pressed = flags & cv2.EVENT_FLAG_CTRLKEY
        shift_pressed = flags & cv2.EVENT_FLAG_SHIFTKEY

        # Show status when modifier is held but not yet dragging (before mouse down)
        if in_video_area and not self.drag_line_start:
            if ctrl_pressed:
                self.drag_line_status = "Ctrl held: drag to move OPENTRONS"
            elif shift_pressed:
                self.drag_line_status = "Shift held: drag to move MICROSCOPE"
            elif event == cv2.EVENT_MOUSEMOVE:
                # Clear status if no modifier and not dragging
                if self.drag_line_status and not self.drag_line_mode:
                    self.drag_line_status = ""

        if event == cv2.EVENT_LBUTTONDOWN:
            if in_video_area:
                # Clicking on microscope video switches focus to second robot panel
                if self.active_panel != 'second_robot':
                    self.active_panel = 'second_robot'
                self.drag_line_start = (x, y)
                self.drag_line_current = (x, y)
                if ctrl_pressed:
                    self.drag_line_mode = 'opentrons'
                    self.drag_line_status = "Drag to move Opentrons..."
                    return True  # Consume event for Ctrl+drag
                elif shift_pressed:
                    self.drag_line_mode = 'microscope'
                    self.drag_line_status = "Drag to move Microscope..."
                    return True  # Consume event for Shift+drag
                else:
                    # No modifier - stream mouse events to microscope for projector drag
                    self.drag_line_mode = 'mouse_stream'
                    self.drag_line_status = "Mouse streaming..."
                    self.send_second_robot_command("MOUSEDOWN", quiet=True)
                    return True  # Consume event so it doesn't drag the window

        elif event == cv2.EVENT_MOUSEMOVE:
            # Update current position during drag
            if self.drag_line_start and self.drag_line_mode:
                self.drag_line_current = (x, y)
                # Calculate movement in mm
                dx_px = x - self.drag_line_start[0]
                dy_px = y - self.drag_line_start[1]
                # Scale: video width = DRAG_FOV_MM (2.5mm)
                mm_per_pixel = self.DRAG_FOV_MM / vw
                dx_mm = dx_px * mm_per_pixel
                # Invert Y axis: dragging up (negative dy_px) = positive Y movement
                dy_mm = -dy_px * mm_per_pixel

                if self.drag_line_mode == 'mouse_stream':
                    # Single message with both coords for atomic X+Y update
                    rel_x = (x - vx) / vw  # 0 to 1
                    rel_y = (y - vy) / vh  # 0 to 1
                    self.send_second_robot_command(f"MOUSEMOVE{rel_x:.4f},{rel_y:.4f}", quiet=True)
                    self.drag_line_status = f"Mouse: ({rel_x:.2f}, {rel_y:.2f})"
                else:
                    target = "OT" if self.drag_line_mode == 'opentrons' else "Micro"
                    self.drag_line_status = f"{target}: X{dx_mm:+.3f} Y{dy_mm:+.3f} mm"
                return True

        elif event == cv2.EVENT_LBUTTONUP:
            # End drag and send command
            if self.drag_line_start and self.drag_line_mode:
                dx_px = x - self.drag_line_start[0]
                dy_px = y - self.drag_line_start[1]
                # Scale: video width = DRAG_FOV_MM (2.5mm)
                mm_per_pixel = self.DRAG_FOV_MM / vw
                dx_mm = dx_px * mm_per_pixel
                # Invert Y axis: dragging up (negative dy_px) = positive Y movement
                dy_mm = -dy_px * mm_per_pixel

                # Send command based on mode
                if self.drag_line_mode == 'opentrons':
                    self._send_drag_line_opentrons(dx_mm, dy_mm)
                elif self.drag_line_mode == 'microscope':
                    self._send_drag_line_microscope(dx_mm, dy_mm)
                else:  # mouse_stream
                    self.send_second_robot_command("MOUSEUP", quiet=True)
                    self.drag_line_status = "Mouse released"

                # Clear drag state
                self.drag_line_start = None
                self.drag_line_current = None
                self.drag_line_mode = None
                # Keep status briefly visible, will be cleared on next move
                return True

        return False

    def _send_drag_line_opentrons(self, dx_mm: float, dy_mm: float):
        """Send relative X/Y movement command to Opentrons based on drag line."""
        # Only send if there's meaningful movement
        if abs(dx_mm) < 0.001 and abs(dy_mm) < 0.001:
            self.status_message = "No movement (drag was too small)"
            return

        # Build command string like "X0.5 Y-0.3"
        cmd_parts = []
        if abs(dx_mm) >= 0.001:
            cmd_parts.append(f"X{dx_mm:.3f}")
        if abs(dy_mm) >= 0.001:
            cmd_parts.append(f"Y{dy_mm:.3f}")

        cmd_str = " ".join(cmd_parts)
        self.status_message = f"Sent to Opentrons: {cmd_str}"
        print(f"\nDrag-line command to Opentrons: {cmd_str}")

        # Execute through normal command processing (handles combined X Y movements)
        self.execute_manual_command(cmd_str)

    def _send_drag_line_microscope(self, dx_mm: float, dy_mm: float):
        """Send relative X/Y movement command to microscope (second robot) via ZMQ."""
        # Only send if there's meaningful movement
        if abs(dx_mm) < 0.001 and abs(dy_mm) < 0.001:
            self.drag_line_status = "No movement (drag was too small)"
            return

        # Build a single command string for relative movement
        # Format: X0.5 Y-0.3 (same as Opentrons style, microscope handles relative)
        cmd_parts = []
        if abs(dx_mm) >= 0.001:
            cmd_parts.append(f"X{dx_mm:.3f}")
        if abs(dy_mm) >= 0.001:
            cmd_parts.append(f"Y{dy_mm:.3f}")

        cmd_str = " ".join(cmd_parts)
        self.drag_line_status = f"Sent to Microscope: {cmd_str}"
        print(f"\nDrag-line command to Microscope: {cmd_str}")

        # Send via ZMQ as a single command
        self.send_second_robot_command(cmd_str)

    def _draw_drag_line(self, canvas: np.ndarray):
        """Draw the drag line on the canvas during drag operations."""
        # Draw status text even when not dragging (for modifier key hints)
        if self.drag_line_status and self.drag_line_video_rect:
            vx, vy, vw, vh = self.drag_line_video_rect
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_x = vx + 10
            text_y = vy + vh - 10  # Bottom of video area

            # Choose color based on mode or status text
            if self.drag_line_mode == 'opentrons' or 'OPENTRONS' in self.drag_line_status:
                text_color = (0, 255, 255)  # Yellow
            elif self.drag_line_mode == 'microscope' or 'MICROSCOPE' in self.drag_line_status:
                text_color = (255, 0, 255)  # Magenta
            elif self.drag_line_mode == 'mouse_stream':
                text_color = (255, 255, 0)  # Cyan
            else:
                text_color = (0, 255, 0)  # Green default

            # Draw background for readability
            (tw, th), _ = cv2.getTextSize(self.drag_line_status, font, 0.6, 2)
            cv2.rectangle(canvas, (text_x - 5, text_y - th - 5),
                         (text_x + tw + 5, text_y + 5), (0, 0, 0), -1)
            cv2.putText(canvas, self.drag_line_status, (text_x, text_y),
                       font, 0.6, text_color, 2, cv2.LINE_AA)

        # Draw line only when actively dragging
        if not self.drag_line_start or not self.drag_line_current or not self.drag_line_mode:
            return

        # Choose color based on mode
        if self.drag_line_mode == 'opentrons':
            line_color = (0, 255, 255)  # Yellow for Opentrons
            circle_color = (0, 200, 200)
        elif self.drag_line_mode == 'microscope':
            line_color = (255, 0, 255)  # Magenta for Microscope
            circle_color = (200, 0, 200)
        else:  # mouse_stream
            line_color = (255, 255, 0)  # Cyan for mouse streaming
            circle_color = (200, 200, 0)

        start = self.drag_line_start
        end = self.drag_line_current

        # Draw line
        cv2.line(canvas, start, end, line_color, 2, cv2.LINE_AA)

        # Draw circles at start and end points
        cv2.circle(canvas, start, 6, circle_color, -1, cv2.LINE_AA)
        cv2.circle(canvas, end, 6, line_color, -1, cv2.LINE_AA)

        # Draw arrow head at end (not for mouse streaming)
        if self.drag_line_mode != 'mouse_stream':
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = (dx * dx + dy * dy) ** 0.5
            if length > 20:  # Only draw arrow if line is long enough
                # Normalize direction
                ux, uy = dx / length, dy / length
                # Arrow head size
                arrow_len = 15
                arrow_width = 8
                # Arrow head points
                p1 = (int(end[0] - arrow_len * ux + arrow_width * uy),
                      int(end[1] - arrow_len * uy - arrow_width * ux))
                p2 = (int(end[0] - arrow_len * ux - arrow_width * uy),
                      int(end[1] - arrow_len * uy + arrow_width * ux))
                cv2.fillPoly(canvas, [np.array([end, p1, p2])], line_color, cv2.LINE_AA)

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

                comment_upper = comment_text.strip().upper()

                # Check for SET# command in comment - save current position
                if comment_upper.startswith("SET") and len(comment_upper) > 3:
                    loc_id = comment_upper[3:]
                    pos = self.current_position.copy()
                    self.saved_locations[loc_id] = {
                        "x": pos["x"],
                        "y": pos["y"],
                        "z": pos["z"],
                        "pipette": self.active_pipette
                    }
                    print(f"  -> Saved location {loc_id}: X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z']:.1f}")
                    self._log("PROTOCOL", f"SET{loc_id}: Saved position ({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f})")
                    self.current_command_index += 1
                    continue

                # F# - set feedrate (mm/s); F0 resets to default
                if comment_upper.startswith("F") and len(comment_upper) > 1:
                    try:
                        new_feedrate = float(comment_upper[1:])
                        if new_feedrate == 0:
                            self.feedrate = None
                            print(f"  -> Feedrate reset to default")
                        else:
                            self.feedrate = new_feedrate
                            print(f"  -> Feedrate set to {new_feedrate} mm/s")
                        self._log("PROTOCOL", f"F{comment_upper[1:]}: feedrate={'default' if self.feedrate is None else self.feedrate}")
                    except ValueError:
                        print(f"  -> Invalid feedrate: {comment_upper}")
                    self.current_command_index += 1
                    continue

                # Check for G commands - absolute moves or saved location moves
                # G0, G1, etc. - move to saved location
                # GX200 GY150 GZ50 - move to absolute coordinates (space-separated)
                if comment_upper.startswith("G") and len(comment_upper) > 1 and not comment_upper.startswith("GO"):
                    # Parse G commands (may be space-separated for multiple axes)
                    self.feedrate = None
                    g_parts = comment_upper.split()

                    # Start with current position
                    target_x = self.current_position.get("x", 0)
                    target_y = self.current_position.get("y", 0)
                    target_z = self.current_position.get("z", 0)
                    is_saved_location = False
                    loc_id = None

                    for g_part in g_parts:
                        if not g_part.startswith("G"):
                            continue
                        g_cmd = g_part[1:]  # Remove the 'G'

                        # Check if it's GX, GY, or GZ (absolute coordinate)
                        if g_cmd.startswith("X"):
                            try:
                                target_x = float(g_cmd[1:])
                            except ValueError:
                                pass
                        elif g_cmd.startswith("Y"):
                            try:
                                target_y = float(g_cmd[1:])
                            except ValueError:
                                pass
                        elif g_cmd.startswith("Z"):
                            try:
                                target_z = float(g_cmd[1:])
                            except ValueError:
                                pass
                        else:
                            # It's a saved location reference (G0, G1, etc.)
                            loc_id = g_cmd
                            is_saved_location = True

                    # If it's a saved location, get coordinates from there
                    if is_saved_location and loc_id:
                        if loc_id not in self.saved_locations:
                            # Location not set yet — skip silently (e.g. G2 before SET2 on first loop)
                            print(f"  -> G{loc_id}: location not set yet, skipping.")
                            self.current_command_index += 1
                            continue

                        saved = self.saved_locations[loc_id]
                        target_x = saved["x"]
                        target_y = saved["y"]
                        target_z = saved["z"]

                        # Apply trailing X/Y/Z offset parts (e.g. "G0 X4.5 Y-4.5")
                        for part in g_parts:
                            if part.startswith("G"):
                                continue
                            if part.startswith("X"):
                                try: target_x += float(part[1:])
                                except ValueError: pass
                            elif part.startswith("Y"):
                                try: target_y += float(part[1:])
                                except ValueError: pass
                            elif part.startswith("Z"):
                                try: target_z += float(part[1:])
                                except ValueError: pass

                        print(f"  -> Moving to saved location {loc_id}")
                    else:
                        print(f"  -> Moving to absolute coordinates")

                    print(f"     Target: X={target_x:.1f}, Y={target_y:.1f}, Z={target_z:.1f}")
                    self._log("PROTOCOL", f"G command: Moving to ({target_x:.1f}, {target_y:.1f}, {target_z:.1f})")

                    # G/MR commands move the pipette outside the analysis simulation,
                    # so subsequent aspirate/dispense should be in-place (not move to labware)
                    self.manual_move_during_pause = True

                    # Queue safe Z movement sequence: raise Z, move X/Y, lower Z
                    self._queue_safe_z_move(target_x, target_y, target_z, is_protocol_command=True)
                    return  # Exit to let the moves execute

                # CLEAR - unset all saved locations (used at protocol start so stale
                # positions from a previous run don't carry over into this one)
                if comment_upper == "CLEAR":
                    self.saved_locations.clear()
                    print(f"  -> CLEAR: All saved locations cleared.")
                    self._log("PROTOCOL", "CLEAR: saved_locations cleared")
                    self.current_command_index += 1
                    continue

                # Interactive seeding loop support
                # LOOP_START - marks the beginning of the loop (store index)
                if comment_upper == "LOOP_START":
                    self._interactive_loop_start_index = self.current_command_index
                    # NOTE: Do NOT reset interactive_exit_requested here - the user may have
                    # pressed 'E' during a pause AFTER G0, and LOOP_END jumps here before CHECK_EXIT.
                    # The flag should only be checked and cleared by CHECK_EXIT when it takes action.
                    # Reset in-place context so explicit-labware aspirates aren't treated as in-place
                    # on subsequent loop iterations (stale context from previous iteration would match).
                    self._in_place_labware_context = (None, None)
                    print(f"  -> LOOP_START: Loop begins at index {self.current_command_index}")
                    self._log("PROTOCOL", f"LOOP_START: index={self.current_command_index}")
                    self.current_command_index += 1
                    continue

                # CHECK_EXIT - check if user pressed 'E', if so jump to end
                if comment_upper == "CHECK_EXIT":
                    if self.interactive_exit_requested:
                        print(f"  -> CHECK_EXIT: Exit requested, jumping to EXIT_LOOP")
                        self._log("PROTOCOL", "CHECK_EXIT: Exit requested, ending loop")
                        self.interactive_exit_requested = False  # Clear the flag now that we've acted on it
                        # Find the EXIT_LOOP comment or go to end
                        for i in range(self.current_command_index, len(self.protocol_commands)):
                            if self.protocol_commands[i].get("commandType") == "comment":
                                msg = self.protocol_commands[i].get("params", {}).get("message", "").strip().upper()
                                if msg == "EXIT_LOOP":
                                    self.current_command_index = i
                                    print(f"  -> CHECK_EXIT: Found EXIT_LOOP at index {i}, jumping there")
                                    break
                        else:
                            # No EXIT_LOOP found, go to end
                            self.current_command_index = len(self.protocol_commands)
                            print(f"  -> CHECK_EXIT: No EXIT_LOOP found, jumping to end")
                        continue
                    else:
                        print(f"  -> CHECK_EXIT: No exit requested, continuing loop")
                        self.current_command_index += 1
                        continue

                # LOOP_END - jump back to LOOP_START
                if comment_upper == "LOOP_END":
                    if hasattr(self, '_interactive_loop_start_index'):
                        print(f"  -> LOOP_END: Jumping back to index {self._interactive_loop_start_index}")
                        self._log("PROTOCOL", f"LOOP_END: Jumping to index {self._interactive_loop_start_index}")
                        self.current_command_index = self._interactive_loop_start_index
                        continue
                    else:
                        print(f"  -> LOOP_END: No LOOP_START found, continuing")
                        self.current_command_index += 1
                        continue

                # EXIT_LOOP - marker for where to jump when exiting
                if comment_upper == "EXIT_LOOP":
                    print(f"  -> EXIT_LOOP: Loop exit point reached")
                    self._log("PROTOCOL", "EXIT_LOOP: Exiting interactive loop")
                    self.current_command_index += 1
                    continue

                # INPLACE - mark the next aspirate/dispense/blowout as in-place
                # (pipette has been moved by G/MR, so the analyzer's labware location is stale)
                if comment_upper == "INPLACE":
                    self._next_is_in_place = True
                    self.current_command_index += 1
                    continue

                # SR <command> - send command to second robot (microscope) via ZMQ
                # Example comments: "SR E2000" sends "E2000" to microscope
                #                   "SR II1"   sends "II1"   to microscope
                if comment_upper.startswith("SR ") and len(comment_upper) > 3:
                    sr_cmd = comment_text.strip()[3:]  # Use original case from comment_text
                    print(f"  -> SR: Sending to microscope: {sr_cmd}")
                    self._log("PROTOCOL", f"SR: Sending to microscope: {sr_cmd}")
                    if self.ENABLE_MICROSCOPE:
                        self.send_second_robot_command(sr_cmd)
                    else:
                        print(f"  -> WARNING: Microscope not enabled, command not sent")
                    self.current_command_index += 1
                    continue

                # MR <axes> - Move Relative: move pipette by delta from current position
                # Example comments: "MR Z5"        raises pipette 5mm
                #                   "MR X4.5 Y0"   moves X+4.5, Y+0
                #                   "MR Z-5"        lowers pipette 5mm
                if comment_upper.startswith("MR "):
                    parts = comment_upper.split()
                    dx, dy, dz = 0.0, 0.0, 0.0
                    for part in parts[1:]:
                        try:
                            if part.startswith("X"):
                                dx = float(part[1:])
                            elif part.startswith("Y"):
                                dy = float(part[1:])
                            elif part.startswith("Z"):
                                dz = float(part[1:])
                        except ValueError:
                            pass

                    target_x = self.current_position.get("x", 0) + dx
                    target_y = self.current_position.get("y", 0) + dy
                    target_z = self.current_position.get("z", 0) + dz

                    print(f"  -> MR: Relative move dX={dx} dY={dy} dZ={dz} -> ({target_x:.1f}, {target_y:.1f}, {target_z:.1f})")
                    self._log("PROTOCOL", f"MR: dX={dx} dY={dy} dZ={dz} -> ({target_x:.1f}, {target_y:.1f}, {target_z:.1f})")

                    # MR moves the pipette outside the analysis simulation,
                    # so subsequent aspirate/dispense should be in-place
                    self.manual_move_during_pause = True

                    pipette_id = self.instrument_ids.get(self.active_pipette)
                    if pipette_id:
                        cmd = {
                            "commandType": "moveToCoordinates",
                            "params": {
                                "pipetteId": pipette_id,
                                "coordinates": {"x": target_x, "y": target_y, "z": target_z},
                                "forceDirect": True
                            }
                        }
                        if self.feedrate is not None:
                            cmd["params"]["speed"] = self.feedrate
                        self._pending_move_sequence = [("MR: relative move", cmd)]
                        self._pending_move_is_protocol = True
                        self.current_command_index += 1
                        self.pending_g_command_continuation = True
                        self._execute_next_pending_move()
                        return
                    else:
                        print(f"  -> ERROR: No active pipette for MR command")
                        self.current_command_index += 1
                        continue

                # Check if comment contains "pause" - if so, pause protocol
                if "pause" in comment_text.lower():
                    self.protocol_paused = True
                    self.executing_protocol_command = False  # Reset so manual commands don't advance index
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

        # Debug: show if command has result from analyzer
        if "result" in cmd:
            print(f"  Analyzer result keys: {list(cmd['result'].keys())}")
            # Show relevant IDs in the result
            for key in ["labwareId", "pipetteId", "moduleId", "lidId", "stackLabwareIds"]:
                if key in cmd['result']:
                    val = cmd['result'][key]
                    if isinstance(val, str):
                        print(f"    {key}: {val[:16]}...")
                    elif isinstance(val, list):
                        print(f"    {key}: [{', '.join(v[:8]+'...' for v in val[:3])}...]")
        else:
            print(f"  No 'result' in analyzer command!")

        # Add simulated result for ID mapping
        cmd["simulated_result"] = cmd

        # MULTI mode: skip pickUpTip if the pipette already has a tip
        if self.multi_mode and cmd_type == "pickUpTip":
            # Check if the active pipette already has a tip
            if self._pipette_has_tip.get(self.active_pipette, False):
                print(f"  MULTI MODE: Skipping pickUpTip — {self.active_pipette} pipette already has a tip")
                self.current_command_index += 1
                # Continue processing next command
                if self.protocol_auto_advance and not self.protocol_paused:
                    time.sleep(0.1)
                    self.execute_next_protocol_step()
                return

        # Convert aspirate/dispense/blowout to in-place versions when the pipette
        # has been moved by G/MR/manual commands (outside of the analyzer simulation).
        # The analyzer always includes labwareId even for in-place operations (it uses the
        # simulation's current location). We detect true "in-place" commands by checking if
        # the labwareId+wellName match the context from BEFORE the G/MR move — if so, the
        # original Python call didn't specify a location. If they differ (e.g. blow_out to
        # a different well), the call had an explicit location and should move normally.
        original_params = cmd.get("params", {})

        if self._next_is_in_place and cmd_type in ["aspirate", "dispense", "blowout",
                                                     "aspirateInPlace", "dispenseInPlace", "blowOutInPlace"]:
            self._next_is_in_place = False

            if cmd_type in ["aspirateInPlace", "dispenseInPlace", "blowOutInPlace"]:
                # Analyzer already made this InPlace (e.g. aspirate at raw coords).
                # Just consume the flag — no conversion needed.
                print(f"  INPLACE flag consumed by analyzer-generated {cmd_type}")
            else:
                # Analyzer produced a regular command (with sim-inferred labware).
                # Convert to in-place since the source code had no location arg.
                in_place_type = {
                    "aspirate": "aspirateInPlace",
                    "dispense": "dispenseInPlace",
                    "blowout": "blowOutInPlace"
                }[cmd_type]

                pipette_id = original_params.get("pipetteId")
                in_place_params = {
                    "pipetteId": pipette_id,
                    "flowRate": original_params.get("flowRate"),
                }
                if cmd_type in ["aspirate", "dispense"]:
                    in_place_params["volume"] = original_params.get("volume")
                in_place_params = {k: v for k, v in in_place_params.items() if v is not None}

                print(f"  Converting {cmd_type} -> {in_place_type} (INPLACE)")
                cmd = {
                    "commandType": in_place_type,
                    "params": in_place_params,
                    "simulated_result": cmd.get("simulated_result", cmd)
                }
                cmd_type = in_place_type  # Update for prepareToAspirate check below

            # After a blowout or dispense, the plunger is in a post-action state.
            # The robot requires prepareToAspirate before aspirateInPlace.
            if cmd_type == "aspirateInPlace" and self._last_pipette_action in ('blowout', 'blowOutInPlace', 'dispense', 'dispenseInPlace'):
                pipette_id = cmd.get("params", {}).get("pipetteId", original_params.get("pipetteId"))
                print(f"  Sending prepareToAspirate (plunger reset after {self._last_pipette_action})")
                prep_cmd = {
                    "commandType": "prepareToAspirate",
                    "params": {"pipetteId": pipette_id},
                    "simulated_result": {}
                }
                self.command_queue.put(prep_cmd)
                self._skip_next_advance = True  # Don't advance on prepareToAspirate result

        # Reset the in-place flag when an analyzed movement command is executed
        move_commands = ["moveToWell", "moveToCoordinates", "moveToAddressableArea",
                         "moveToAddressableAreaForDropTip", "moveLabware", "pickUpTip"]
        if cmd_type in move_commands:
            if self.manual_move_during_pause:
                print(f"  Resetting in-place mode (movement command: {cmd_type})")
            self.manual_move_during_pause = False

        # Handle pickUpTip: apply runtime tiprack offset overrides
        if cmd_type == "pickUpTip":
            labware_id = cmd.get("params", {}).get("labwareId", "")
            if labware_id in self.tiprack_offset_overrides:
                override = self.tiprack_offset_overrides[labware_id]
                original_well = cmd.get("params", {}).get("wellName", "A1")

                # Parse original well (e.g., "A1" -> row=0, col=0)
                orig_row = ord(original_well[0].upper()) - ord('A')
                orig_col = int(original_well[1:]) - 1  # Convert to 0-indexed

                # Calculate the offset that was applied when protocol was analyzed
                # We need to find the "base" offset from the protocol and apply the difference
                # For now, we'll assume the first pickUpTip for this tiprack sets the baseline
                if 'baseline_col' not in override:
                    # First pickup - store as baseline
                    override['baseline_col'] = orig_col
                    override['baseline_row'] = orig_row
                    override['tip_count'] = 0

                # Calculate how many tips have been used from baseline
                tips_used = override['tip_count']

                # Calculate new well based on override start + tips used
                # For 8-channel ALL mode (row always A), only column matters
                new_col = override['columns'] + tips_used
                new_row = override['rows']  # Usually 0 for ALL mode

                if new_col < 12 and new_row < 8:  # Valid well
                    new_well = f"{chr(ord('A') + new_row)}{new_col + 1}"

                    if new_well != original_well:
                        print(f"  TIPRACK OVERRIDE: {original_well} -> {new_well} (offset col={override['columns']}, tips_used={tips_used})")
                        cmd["params"]["wellName"] = new_well

                    # Increment tip count for next pickup
                    override['tip_count'] = tips_used + 1
                else:
                    print(f"  WARNING: Tiprack override would result in invalid well (col={new_col}, row={new_row})")

            # Track tip origin for return_tip support
            pipette_id = cmd.get("params", {}).get("pipetteId", "")
            well_name = cmd.get("params", {}).get("wellName", "A1")
            if pipette_id and labware_id:
                if not hasattr(self, '_tip_origins'):
                    self._tip_origins = {}
                self._tip_origins[pipette_id] = {
                    'labwareId': labware_id,
                    'wellName': well_name
                }
                print(f"  TIP ORIGIN: Stored pickup location {well_name} for pipette {pipette_id[:8]}...")

        # Handle dropTip: fix return_tip to use the actual pickup location
        if cmd_type == "dropTip":
            pipette_id = cmd.get("params", {}).get("pipetteId", "")
            labware_id = cmd.get("params", {}).get("labwareId", "")
            well_name = cmd.get("params", {}).get("wellName", "A1")

            # Check if we have a stored tip origin for this pipette
            if hasattr(self, '_tip_origins') and pipette_id in self._tip_origins:
                origin = self._tip_origins[pipette_id]
                # If dropping to the same tiprack (return_tip), use the stored origin well
                if labware_id == origin['labwareId'] and well_name != origin['wellName']:
                    print(f"  RETURN_TIP FIX: {well_name} -> {origin['wellName']} (using stored pickup location)")
                    cmd["params"]["wellName"] = origin['wellName']
                # Clear the origin after drop
                del self._tip_origins[pipette_id]

        # Handle plate commands: apply runtime plate offset overrides for aspirate, dispense, moveToWell
        if cmd_type in ["aspirate", "dispense", "moveToWell", "blowout"]:
            labware_id = cmd.get("params", {}).get("labwareId", "")
            original_well = cmd.get("params", {}).get("wellName", "A1")

            # Check for INTERACTIVE well marker - replace with current interactive source well
            if original_well == "INTERACTIVE":
                print(f"  INTERACTIVE WELL: Using {self.interactive_source_well}")
                cmd["params"]["wellName"] = self.interactive_source_well
                original_well = self.interactive_source_well

            if labware_id in self.plate_offset_overrides:
                override = self.plate_offset_overrides[labware_id]
                original_well = cmd.get("params", {}).get("wellName", "A1")

                # Check for 'direct' mode - just use the clicked well directly
                if override.get('direct', False):
                    new_well = f"{chr(ord('A') + override['rows'])}{override['columns'] + 1}"
                    if new_well != original_well:
                        print(f"  PLATE DIRECT: {original_well} -> {new_well} (interactive selection)")
                        cmd["params"]["wellName"] = new_well
                else:
                    # Relative offset mode
                    # Parse original well (e.g., "A1" -> row=0, col=0)
                    orig_row = ord(original_well[0].upper()) - ord('A')
                    orig_col = int(original_well[1:]) - 1  # Convert to 0-indexed

                    # For plates, we need to track which well operations have been done
                    # and apply the offset consistently
                    if 'baseline_col' not in override:
                        # First operation - store as baseline
                        override['baseline_col'] = orig_col
                        override['baseline_row'] = orig_row

                    # Calculate the difference between baseline and current
                    col_diff = orig_col - override['baseline_col']
                    row_diff = orig_row - override['baseline_row']

                    # Apply offset + difference
                    new_col = override['columns'] + col_diff
                    new_row = override['rows'] + row_diff

                    if 0 <= new_col < 12 and 0 <= new_row < 8:  # Valid well for 96-well plate
                        new_well = f"{chr(ord('A') + new_row)}{new_col + 1}"

                        if new_well != original_well:
                            print(f"  PLATE OVERRIDE: {original_well} -> {new_well} (offset col={override['columns']}, row={override['rows']})")
                            cmd["params"]["wellName"] = new_well
                    else:
                        print(f"  WARNING: Plate override would result in invalid well (col={new_col}, row={new_row})")

        # Handle moveToCoordinates: track for SET binding and check for substitution
        if cmd_type == "moveToCoordinates":
            coords = cmd.get("params", {}).get("coordinates", {})
            if coords:
                # Store for potential SET binding
                self.last_protocol_move_coords = coords.copy()

                # Check if these coordinates have a saved substitution
                coord_key = (round(coords.get("x", 0), 1),
                            round(coords.get("y", 0), 1),
                            round(coords.get("z", 0), 1))

                if coord_key in self.coordinate_substitutions:
                    loc_id = self.coordinate_substitutions[coord_key]
                    if loc_id in self.saved_locations:
                        saved = self.saved_locations[loc_id]
                        print(f"  SUBSTITUTING moveToCoordinates with saved location {loc_id}")
                        print(f"    Original: ({coord_key[0]}, {coord_key[1]}, {coord_key[2]})")
                        print(f"    New:      ({saved['x']:.1f}, {saved['y']:.1f}, {saved['z']:.1f})")

                        # Replace coordinates in command
                        cmd["params"]["coordinates"] = {
                            "x": saved["x"],
                            "y": saved["y"],
                            "z": saved["z"]
                        }

        # Safety net: always send prepareToAspirate before aspirateInPlace after blowout/dispense
        # This catches cases not handled by the INPLACE flag path (e.g. loop restarts)
        if cmd.get("commandType") == "aspirateInPlace" and self._last_pipette_action in ('blowout', 'blowOutInPlace', 'dispense', 'dispenseInPlace'):
            if not self._skip_next_advance:  # Don't double-queue if already queued above
                pipette_id = cmd.get("params", {}).get("pipetteId")
                print(f"  Safety net: prepareToAspirate before aspirateInPlace (after {self._last_pipette_action})")
                prep_cmd = {
                    "commandType": "prepareToAspirate",
                    "params": {"pipetteId": pipette_id},
                    "simulated_result": {}
                }
                self.command_queue.put(prep_cmd)
                self._skip_next_advance = True

        # Queue command for execution
        self.command_queue.put(cmd)
        self.command_executing = True
        self.executing_protocol_command = True  # Mark that this is a protocol command
        self.advance_on_command_complete = True  # Advance index when this command completes (survives pause)

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
            return "Commands: X Y Z  G# GX GY GZ  GO GC  SET#  P1 P2 P3  H R Q"

        # Gripper commands
        if cmd == 'G':
            return "G# (saved loc), GX# GY# GZ# (absolute), GO (open), GC (close)"

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
            return "F# - Set feedrate (mm/s), e.g. F50; F0 = default"

        if cmd == 'R' or cmd == 'RUN' or cmd.startswith('RUN'):
            return "R - Restart protocol from beginning"

        if cmd == 'Q':
            return "Q - Quit application"

        if cmd == 'S':
            return "SET# - Save current position, e.g. SET0"

        if cmd.startswith('SET'):
            if len(cmd) > 3:
                return f"SET{cmd[3:]} - Save current position as location {cmd[3:]}"
            return "SET# - Save current position, e.g. SET0"

        # G commands for absolute moves
        if cmd.startswith('G') and cmd not in ['GO', 'GC']:
            g_rest = cmd[1:]
            if g_rest.startswith('X') or g_rest.startswith('Y') or g_rest.startswith('Z'):
                return f"G{g_rest} - Move to absolute {g_rest[0]}={g_rest[1:]}mm"
            elif g_rest and g_rest[0].isdigit():
                loc_id = g_rest
                if loc_id in self.saved_locations:
                    saved = self.saved_locations[loc_id]
                    return f"G{loc_id} - Move to saved location (X={saved['x']:.1f}, Y={saved['y']:.1f}, Z={saved['z']:.1f})"
                return f"G{loc_id} - Move to saved location {loc_id} (not yet saved)"
            return "G# or GX# GY# GZ# - Move to saved location or absolute coords"

        # If we're typing a number after a command, show what it means
        if len(cmd) > 1 and cmd[0] in 'XYZ':
            try:
                float(cmd[1:])
                return f"Move {cmd[0]} axis by {cmd[1:]} mm"
            except:
                pass

        return ""

    def get_microscope_command_suggestions(self) -> str:
        """Get context-sensitive command suggestions for the microscope (second robot)."""
        cmd = self.second_robot_command_input.upper()

        if not cmd:
            # No input - show all available root commands
            return "X Y Z F  LH LL LA LB  I#  PROJ..."

        # Movement commands (same as Opentrons)
        if cmd[0] in 'XYZ':
            if len(cmd) > 1:
                try:
                    float(cmd[1:])
                    return f"Move {cmd[0]} axis by {cmd[1:]} mm"
                except:
                    pass
            return f"{cmd[0]}# - Move {cmd[0]} axis (mm), e.g. {cmd[0]}5 or {cmd[0]}-2.5"

        if cmd == 'F' or (cmd.startswith('F') and len(cmd) > 1):
            return "F# - Set feedrate (mm/s), e.g. F50"

        # Light controls (0 to 1 range)
        if cmd == 'L':
            return "LH# (brightfield) LL# (oblique) LA# LB# (fluorescence) [0-1]"

        if cmd.startswith('LH'):
            return "LH# - Brightfield illuminator (0-1), e.g. LH0.5"

        if cmd == 'LL':
            return "LLA# LLB# LLC# - Oblique illuminators (0-1)"
        if cmd.startswith('LLA'):
            return "LLA# - Oblique illuminator A (0-1), e.g. LLA0.8"
        if cmd.startswith('LLB'):
            return "LLB# - Oblique illuminator B (0-1), e.g. LLB0.5"
        if cmd.startswith('LLC'):
            return "LLC# - Oblique illuminator C (0-1), e.g. LLC0.3"

        if cmd.startswith('LA'):
            return "LA# - Fluorescence LED A (0-1), e.g. LA1"
        if cmd.startswith('LB'):
            return "LB# - Fluorescence LED B (0-1), e.g. LB0.7"

        # Imaging mode
        if cmd == 'I':
            return "I# - Imaging mode: I0=microscope I1=processing I2=both I3=projector"
        if cmd in ['I0', 'I1', 'I2', 'I3']:
            modes = {'I0': 'microscope only', 'I1': 'image processing', 'I2': 'microscope+processing', 'I3': 'projector mode'}
            return f"{cmd} - {modes.get(cmd, 'imaging mode')}"

        # Projector commands
        if cmd == 'P':
            return "PROJ... - Projector commands"
        if cmd == 'PR':
            return "PROJ... - Projector commands"
        if cmd == 'PRO':
            return "PROJ... - Projector commands"
        if cmd == 'PROJ':
            return "PROJI# PROJR PROJM* PROJS* PROJIS - Projector controls"

        if cmd.startswith('PROJI') and not cmd.startswith('PROJIS'):
            if len(cmd) > 5:
                return f"PROJI{cmd[5:]} - Illuminate for {cmd[5:]} seconds"
            return "PROJI# - Illuminate for # seconds, e.g. PROJI5"

        if cmd.startswith('PROJIS'):
            return "PROJIS - Illuminate current video"

        if cmd.startswith('PROJR'):
            return "PROJR - Display chip reference (drag with mouse)"

        if cmd.startswith('PROJM'):
            if len(cmd) > 5:
                return f"PROJM{cmd[5:]} - Set mask '{cmd[5:]}' (drag with mouse)"
            return "PROJM* - Set mask by name, e.g. PROJMcircle"

        if cmd.startswith('PROJS') and not cmd.startswith('PROJIS'):
            if len(cmd) > 5:
                return f"PROJS{cmd[5:]} - Set projector video '{cmd[5:]}'"
            return "PROJS* - Set projector video by name"

        return ""

    def execute_manual_command(self, cmd_text: str):
        """Execute a manual G-code style command.

        Supports multiple space-separated commands on one line.
        Example: X-50 Y-50 F10 moves diagonally at 10mm/s
        """
        original_text = cmd_text.strip()
        cmd_text_lower = original_text.lower()

        if not cmd_text_lower:
            return

        # Log the manual command
        self._log("COMMAND", f"Manual: {original_text}")

        # Handle 'E' command - exit interactive seeding loop
        if cmd_text_lower == 'e':
            self.interactive_exit_requested = True
            self.status_message = "Exit requested - finishing current cycle"
            print("\n*** EXIT REQUESTED - Protocol will exit after current cycle ***")
            self._log("COMMAND", "Interactive exit requested")
            self.command_executing = False
            return

        # Check if this is a single-word command (no spaces) that needs special handling
        # These commands cannot be combined with others
        single_commands = ['go', 'gc', 'p1', 'p2', 'p3', 'h', 'home', 'r', 'run', 'q', 'drop', 'multi', 'end']
        if cmd_text_lower in single_commands or cmd_text_lower.startswith(('pvol', 'prat', 'pa', 'pd', 'set', 'g')):
            # Use original single-command logic for these
            self._execute_single_command(cmd_text_lower, original_text)
            return

        # Parse multiple commands separated by spaces
        commands = cmd_text_lower.split()

        # Variables to accumulate for combined movements
        delta_x = 0.0
        delta_y = 0.0
        delta_z = 0.0
        has_movement = False
        has_feedrate_change = False
        feedrate_for_move = self.feedrate  # Use current feedrate unless F command is present

        try:
            # Parse all commands
            for cmd in commands:
                # Feedrate command
                if cmd.startswith('f') and len(cmd) > 1:
                    try:
                        new_feedrate = float(cmd[1:])
                        if new_feedrate == 0:
                            # F0 = reset to default (robot's default speed)
                            feedrate_for_move = None
                            self.feedrate = None
                            has_feedrate_change = True
                            print(f"Feedrate reset to default (robot speed)")
                        else:
                            feedrate_for_move = new_feedrate
                            self.feedrate = new_feedrate  # Update global feedrate
                            has_feedrate_change = True
                            print(f"Feedrate set to {new_feedrate} mm/s")
                    except ValueError:
                        self.error_message = f"Invalid feedrate: {cmd}"
                        self.command_executing = False
                        return

                # Movement commands
                elif cmd[0] in ['x', 'y', 'z'] and len(cmd) > 1:
                    try:
                        distance = float(cmd[1:])
                        if cmd[0] == 'x':
                            delta_x += distance
                        elif cmd[0] == 'y':
                            delta_y += distance
                        elif cmd[0] == 'z':
                            delta_z += distance
                        has_movement = True
                    except ValueError:
                        self.error_message = f"Invalid movement command: {cmd}"
                        self.command_executing = False
                        return

                else:
                    self.error_message = f"Unknown command in multi-command string: {cmd}"
                    self.command_executing = False
                    return

            # Execute combined movement if any axes were specified
            if has_movement:
                self._execute_combined_movement(delta_x, delta_y, delta_z, feedrate_for_move, original_text)
            elif has_feedrate_change:
                # Just feedrate update, no movement
                speed_str = f"{feedrate_for_move} mm/s" if feedrate_for_move is not None else "default"
                self.status_message = f"Feedrate set to {speed_str}"
                self.command_executing = False
            else:
                # No movement and no feedrate change - shouldn't happen but reset flag
                self.command_executing = False

        except Exception as e:
            self.error_message = f"Command error: {e}"
            print(f"ERROR: {self.error_message}")
            import traceback
            traceback.print_exc()
            self.command_executing = False

    def _execute_combined_movement(self, delta_x: float, delta_y: float, delta_z: float, speed: float, original_text: str):
        """Execute a combined multi-axis movement with specified speed."""
        # Calculate new position
        curr_x = self.current_position.get('x', 0)
        curr_y = self.current_position.get('y', 0)
        curr_z = self.current_position.get('z', 0)

        new_x = curr_x + delta_x
        new_y = curr_y + delta_y
        new_z = curr_z + delta_z

        # Check if we have a valid position from the robot
        if not self.position_initialized:
            self.error_message = "Position not initialized! Home robot first (H command)"
            print(f"\n{'='*70}")
            print(f"SAFETY WARNING: POSITION NOT INITIALIZED")
            print(f"{'='*70}")
            print(f"Command: {original_text}")
            print(f"ERROR: Cannot move until robot position is known!")
            print(f"SOLUTION: First home the robot with 'H' command")
            print(f"         This will initialize the position tracking.")
            print(f"{'='*70}")
            self.command_executing = False
            return

        # Check safety limits
        is_safe, error_msg = self.check_position_safe(x=new_x, y=new_y, z=new_z)
        if not is_safe:
            self.error_message = f"SAFETY LIMIT: {error_msg}"
            print(f"\n{'='*70}")
            print(f"SAFETY LIMIT VIOLATION")
            print(f"{'='*70}")
            print(f"Command: {original_text}")
            print(f"Current: X={curr_x:.1f}, Y={curr_y:.1f}, Z={curr_z:.1f}")
            if delta_x != 0:
                print(f"  X: {delta_x:+.1f}mm")
            if delta_y != 0:
                print(f"  Y: {delta_y:+.1f}mm")
            if delta_z != 0:
                print(f"  Z: {delta_z:+.1f}mm")
            print(f"Would result in: X={new_x:.1f}, Y={new_y:.1f}, Z={new_z:.1f}")
            print(f"ERROR: {error_msg}")
            print(f"{'='*70}")
            self.command_executing = False
            return

        # Build movement description
        move_parts = []
        if delta_x != 0:
            move_parts.append(f"X{delta_x:+.1f}")
        if delta_y != 0:
            move_parts.append(f"Y{delta_y:+.1f}")
        if delta_z != 0:
            move_parts.append(f"Z{delta_z:+.1f}")
        move_desc = " ".join(move_parts)

        # Use moveToCoordinates for pipettes (avoids Z bobbing), robot/moveTo for gripper
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
            # Only add speed if not None (use robot's default otherwise)
            if speed is not None:
                cmd["params"]["speed"] = speed
        else:
            # For pipettes, use moveToCoordinates with forceDirect to avoid Z bobbing
            pipette_id = self.instrument_ids.get(self.active_pipette)
            if not pipette_id:
                self.error_message = f"{self.active_pipette} pipette not found!"
                self.command_executing = False
                return

            cmd = {
                "commandType": "moveToCoordinates",
                "params": {
                    "pipetteId": pipette_id,
                    "coordinates": {
                        "x": new_x,
                        "y": new_y,
                        "z": new_z
                    },
                    "forceDirect": True
                }
            }
            # Only add speed if not None (use robot's default otherwise)
            if speed is not None:
                cmd["params"]["speed"] = speed

        speed_str = f"{speed}mm/s" if speed is not None else "default"
        self.status_message = f"Moving {move_desc}mm @ {speed_str} -> X={new_x:.1f}, Y={new_y:.1f}, Z={new_z:.1f}"
        print(f"\n{'='*70}")
        print(f"EXECUTING COMBINED MOVE:")
        print(f"{'='*70}")
        print(f"Command: {original_text}")
        print(f"Current: X={curr_x:.1f}, Y={curr_y:.1f}, Z={curr_z:.1f}")
        print(f"Delta: {move_desc}mm")
        print(f"New: X={new_x:.1f}, Y={new_y:.1f}, Z={new_z:.1f}")
        print(f"Speed: {speed_str}")
        print(f"{'='*70}")

        # Track manual movement during pause for in-place command conversion
        if self.protocol_paused and self.protocol_commands:
            self.manual_move_during_pause = True
            print("  (Manual move during pause - next aspirate/dispense will be in-place)")

        # Execute
        self.command_executing = True
        self.command_queue.put(cmd)

    def _switch_to_gripper_position(self):
        """Switch active instrument to gripper and calculate its position from P1."""
        if 'gripper' not in self.instrument_ids:
            print("  WARNING: Gripper not found, cannot switch")
            return False

        if 'gripper' not in self.instrument_limits:
            print("  WARNING: Gripper limits not calculated, cannot switch")
            return False

        if 'left' not in self.instrument_ids:
            print("  WARNING: Left pipette not found, cannot calculate gripper position")
            return False

        # Query current P1 position to calculate gripper position
        save_pos_cmd = {
            "commandType": "savePosition",
            "params": {
                "pipetteId": self.instrument_ids["left"]
            }
        }
        result = self._execute_command_sync(save_pos_cmd)

        if "error" not in result and "position" in result.get("result", {}):
            p1_pos = result["result"]["position"]

            # Calculate gripper position from CURRENT P1 position
            gripper_x = p1_pos["x"] + 125
            gripper_y = p1_pos["y"] - 10.4
            gripper_z = 164.0

            self.current_position = {"x": gripper_x, "y": gripper_y, "z": gripper_z}
            self.limits = self.instrument_limits["gripper"]
            self.active_pipette = "gripper"

            print(f"  Switched to gripper - X={gripper_x:.1f}, Y={gripper_y:.1f}, Z={gripper_z:.1f}")
            print(f"  Limits: X={self.limits['x']['max']:.1f}, Y={self.limits['y']['max']:.1f}, Z={self.limits['z']['max']:.1f}")
            return True
        else:
            print("  WARNING: Failed to query P1 position for gripper calculation")
            return False

    def _execute_single_command(self, cmd_text: str, original_text: str):
        """Execute single non-combinable commands (gripper, pipette switching, etc.)."""
        try:
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

            # Drop tip into trash (move to trash A3, then drop)
            elif cmd_text == 'drop':
                pipette_id = self.instrument_ids.get(self.active_pipette)
                if not pipette_id:
                    self.error_message = "No active pipette! Home first (H)"
                    self.command_executing = False
                    return
                # Queue move-to-trash then drop as two sequential commands
                move_cmd = {
                    "commandType": "moveToAddressableAreaForDropTip",
                    "params": {
                        "pipetteId": pipette_id,
                        "addressableAreaName": "movableTrashA3",
                        "offset": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "alternateDropLocation": True,
                        "ignoreTipConfiguration": True
                    }
                }
                drop_cmd = {
                    "commandType": "dropTipInPlace",
                    "params": {
                        "pipetteId": pipette_id
                    }
                }
                self.status_message = "Dropping tip in trash..."
                print(f"\nCommand: {original_text} -> {self.status_message}")
                self.command_executing = True
                self.command_queue.put(move_cmd)
                self.command_queue.put(drop_cmd)
                self._pipette_has_tip[self.active_pipette] = False
                return

            # MULTI mode: run protocols back-to-back on the same run
            elif cmd_text == 'multi':
                self.multi_mode = True
                self.status_message = "MULTI mode ON — protocols will share the current run"
                print(f"\n*** MULTI MODE ENABLED ***")
                print(f"  Load protocols sequentially. Deck setup will be reused.")
                print(f"  Type END to exit MULTI mode and close the run.")
                self.command_executing = False
                return

            elif cmd_text == 'end':
                if not self.multi_mode:
                    self.error_message = "Not in MULTI mode"
                    self.command_executing = False
                    return
                self.multi_mode = False
                # Delete the current run
                if self.run_id:
                    try:
                        requests.delete(
                            f"{self.api_url}/runs/{self.run_id}",
                            headers={"Opentrons-Version": "3"}
                        )
                        print(f"\nDeleted run {self.run_id}")
                    except Exception as e:
                        print(f"\nWarning: Could not delete run: {e}")
                self.run_id = None
                self.id_map = {}
                self._deck_real_results = {}
                self._pipette_has_tip = {}
                self.protocol_commands = []
                self.status_message = "MULTI mode OFF — run ended"
                print(f"*** MULTI MODE DISABLED ***")
                self.command_executing = False
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
                print(f"\nCommand: {original_text} -> Switching to GRIPPER...")
                if self._switch_to_gripper_position():
                    pos = self.current_position
                    self.status_message = f"Activated GRIPPER - X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z']:.1f}"
                else:
                    self.error_message = "Failed to switch to gripper! Home first (H)"
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

            elif cmd_text == 'h' or cmd_text == 'home':
                # Home command - now asynchronous so video stream can continue
                self.status_message = "Homing robot..."
                print(f"\nCommand: {cmd_text} -> Homing robot (async)...")

                # Queue the home command asynchronously
                home_cmd = {"commandType": "home", "params": {}}
                self.command_queue.put(home_cmd)

                # Set flag to run initialization after homing completes
                self.pending_home_initialization = True
                self.command_executing = True
                # Note: command_executing flag stays True until initialization completes
                return

            elif cmd_text == 'r' or cmd_text == 'run':
                # Restart protocol - reload from disk to pick up any changes
                if not self.protocol_path:
                    self.error_message = "No protocol loaded!"
                    self.command_executing = False
                    return

                print(f"\nCommand: {original_text} -> Reloading protocol from disk...")

                # Delete the old run to clear labware/resource conflicts
                if self.run_id:
                    try:
                        print(f"Deleting old run: {self.run_id}")
                        resp = requests.delete(
                            f"{self.api_url}/runs/{self.run_id}",
                            headers={"Opentrons-Version": "4"}
                        )
                        if resp.status_code == 200:
                            print("Old run deleted successfully")
                        else:
                            print(f"Warning: Failed to delete old run (status {resp.status_code})")
                    except Exception as e:
                        print(f"Warning: Error deleting old run: {e}")

                    # Clear run ID and ID map to start fresh
                    self.run_id = None
                    self.id_map = {}
                    self.uploaded_labware_defs = set()

                # Reload protocol from disk (picks up any changes to the file)
                if self.load_protocol(self.protocol_path):
                    self.protocol_paused = True  # Start paused, user must press Tab to begin
                    self.error_message = ""
                    step_count = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")
                    self.status_message = f"Protocol reloaded: {step_count} steps. Press Tab to start."
                    print(f"{self.status_message}")
                    self._log("COMMAND", f"Protocol reloaded from disk ({step_count} steps)")
                else:
                    self.error_message = "Failed to reload protocol!"
                    print(f"ERROR: {self.error_message}")

                self.command_executing = False
                return

            elif cmd_text == 'q':
                # Quit application
                print(f"\nCommand: {original_text} -> Quitting application...")
                self.status_message = "Quitting..."
                self.running = False
                self.command_executing = False
                return

            elif cmd_text.startswith('set'):
                # Save current position (SET# command)
                if len(cmd_text) <= 3:
                    self.error_message = "Usage: SET# (e.g. SET0, SET1)"
                    self.command_executing = False
                    return

                try:
                    loc_id = cmd_text[3:]  # Get everything after 'set'
                    pos = self.current_position.copy()
                    self.saved_locations[loc_id] = {
                        "x": pos["x"],
                        "y": pos["y"],
                        "z": pos["z"],
                        "pipette": self.active_pipette
                    }

                    # If we have a last protocol moveToCoordinates, bind it for auto-substitution
                    if self.last_protocol_move_coords:
                        orig = self.last_protocol_move_coords
                        # Round to 1 decimal for matching
                        orig_key = (round(orig["x"], 1), round(orig["y"], 1), round(orig["z"], 1))
                        self.coordinate_substitutions[orig_key] = loc_id
                        print(f"  Bound to original coords: ({orig_key[0]}, {orig_key[1]}, {orig_key[2]}) -> location {loc_id}")

                    self.status_message = f"Saved location {loc_id}: X={pos['x']:.1f}, Y={pos['y']:.1f}, Z={pos['z']:.1f}"
                    print(f"\nCommand: {original_text} -> {self.status_message}")
                    self._log("COMMAND", f"Saved location {loc_id}: {self.saved_locations[loc_id]}")
                    self.command_executing = False
                    return
                except Exception as e:
                    self.error_message = f"Error saving location: {e}"
                    self.command_executing = False
                    return

            elif cmd_text.startswith('g') and len(cmd_text) > 1 and cmd_text not in ['go', 'gc']:
                # G commands: G0 (saved location), GX200 GY150 GZ50 (absolute coords)
                # Parse G commands (may be space-separated)
                g_parts = cmd_text.upper().split()

                # Start with current position
                target_x = self.current_position.get("x", 0)
                target_y = self.current_position.get("y", 0)
                target_z = self.current_position.get("z", 0)
                is_saved_location = False
                loc_id = None

                for g_part in g_parts:
                    if not g_part.startswith("G"):
                        continue
                    g_cmd = g_part[1:]  # Remove the 'G'

                    if g_cmd.startswith("X"):
                        try:
                            target_x = float(g_cmd[1:])
                        except ValueError:
                            pass
                    elif g_cmd.startswith("Y"):
                        try:
                            target_y = float(g_cmd[1:])
                        except ValueError:
                            pass
                    elif g_cmd.startswith("Z"):
                        try:
                            target_z = float(g_cmd[1:])
                        except ValueError:
                            pass
                    else:
                        # Saved location (G0, G1, etc.)
                        loc_id = g_cmd
                        is_saved_location = True

                if is_saved_location and loc_id:
                    if loc_id not in self.saved_locations:
                        # Location not set yet — skip silently (e.g. G2 before SET2 on first loop)
                        print(f"  -> G{loc_id}: location not set yet, skipping.")
                        self.command_executing = False
                        return
                    saved = self.saved_locations[loc_id]
                    target_x = saved["x"]
                    target_y = saved["y"]
                    target_z = saved["z"]

                    # Apply trailing X/Y/Z offset parts (e.g. "G0 X4.5 Y-4.5")
                    for part in g_parts:
                        if part.startswith("G"):
                            continue
                        if part.startswith("X"):
                            try: target_x += float(part[1:])
                            except ValueError: pass
                        elif part.startswith("Y"):
                            try: target_y += float(part[1:])
                            except ValueError: pass
                        elif part.startswith("Z"):
                            try: target_z += float(part[1:])
                            except ValueError: pass

                    print(f"\nCommand: {original_text} -> Moving to saved location {loc_id}")
                else:
                    print(f"\nCommand: {original_text} -> Moving to absolute coordinates")

                print(f"  Target: X={target_x:.1f}, Y={target_y:.1f}, Z={target_z:.1f}")

                # Queue safe Z movement sequence: raise Z, move X/Y, lower Z
                self._queue_safe_z_move(target_x, target_y, target_z, is_protocol_command=False)
                return

            else:
                self.error_message = f"Unknown command: {cmd_text}"
                print(f"ERROR: {self.error_message}")
                self.command_executing = False

        except Exception as e:
            self.error_message = f"Command error: {e}"
            print(f"ERROR: {self.error_message}")
            import traceback
            traceback.print_exc()
            self.command_executing = False

    def _queue_safe_z_move(self, target_x: float, target_y: float, target_z: float, is_protocol_command: bool = False):
        """
        Queue a safe Z movement sequence: raise to safe Z, move X/Y, then lower to target Z.
        This prevents collisions by ensuring the pipette is at a safe height during horizontal travel.
        """
        curr_x = self.current_position.get("x", 0)
        curr_y = self.current_position.get("y", 0)
        curr_z = self.current_position.get("z", 0)

        # Determine the safe Z height to use (max of current Z, target Z, and safe_z_height)
        travel_z = max(curr_z, target_z, self.safe_z_height)

        # Check if we need to move X/Y at all
        needs_xy_move = abs(curr_x - target_x) > 0.1 or abs(curr_y - target_y) > 0.1

        # Get pipette ID for move commands
        if self.active_pipette == "gripper":
            pipette_id = None
            is_gripper = True
        else:
            pipette_id = self.instrument_ids.get(self.active_pipette)
            is_gripper = False
            if not pipette_id:
                self.error_message = f"{self.active_pipette} pipette not found!"
                self.command_executing = False
                return

        def make_move_cmd(x, y, z):
            """Helper to create a move command."""
            if is_gripper:
                cmd = {
                    "commandType": "robot/moveTo",
                    "params": {
                        "gripperId": "flex_gripper",
                        "mount": "extension",
                        "destination": {"x": x, "y": y, "z": z}
                    }
                }
            else:
                cmd = {
                    "commandType": "moveToCoordinates",
                    "params": {
                        "pipetteId": pipette_id,
                        "coordinates": {"x": x, "y": y, "z": z},
                        "forceDirect": True
                    }
                }
            if self.feedrate is not None:
                cmd["params"]["speed"] = self.feedrate
            return cmd

        # Build the sequence of moves
        move_sequence = []

        if needs_xy_move:
            # Step 1: Raise to safe Z (if not already at or above it)
            if curr_z < travel_z:
                move_sequence.append(("Raising to safe Z", make_move_cmd(curr_x, curr_y, travel_z)))

            # Step 2: Move X/Y at safe Z height
            move_sequence.append(("Moving X/Y at safe Z", make_move_cmd(target_x, target_y, travel_z)))

            # Step 3: Lower to target Z (if different from travel Z)
            if abs(target_z - travel_z) > 0.1:
                move_sequence.append(("Lowering to target Z", make_move_cmd(target_x, target_y, target_z)))
        else:
            # Only Z move needed
            move_sequence.append(("Moving to target Z", make_move_cmd(target_x, target_y, target_z)))

        # Queue all moves
        print(f"  Safe Z move sequence ({len(move_sequence)} steps):")
        for desc, cmd in move_sequence:
            print(f"    - {desc}")

        # Store the sequence for sequential execution
        self._pending_move_sequence = move_sequence
        self._pending_move_is_protocol = is_protocol_command

        # If this is a protocol command, increment the index now
        if is_protocol_command:
            self.current_command_index += 1
            self.pending_g_command_continuation = True

        # Start executing the first move
        self._execute_next_pending_move()

    def _execute_next_pending_move(self):
        """Execute the next move in the pending sequence."""
        if not hasattr(self, '_pending_move_sequence') or not self._pending_move_sequence:
            # Sequence complete
            self.command_executing = False
            if hasattr(self, '_pending_move_is_protocol') and self._pending_move_is_protocol:
                # Continue with protocol after move sequence completes
                pass  # pending_g_command_continuation will handle this
            return

        # Get and remove the first move from the sequence
        desc, cmd = self._pending_move_sequence.pop(0)
        self.status_message = f"G: {desc}"
        self.command_executing = True
        self.command_queue.put(cmd)

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

        # Close ZMQ sockets
        try:
            self.zmq_image_socket.close()
            self.zmq_data_socket.close()
            self.zmq_cmd_socket.close()
            self.zmq_context.term()
        except Exception as e:
            print(f"Warning: Error closing ZMQ sockets: {e}")

        cv2.destroyAllWindows()
        print("Cleanup complete")

    def _compose_dual_panel_display(self, opentrons_frame: np.ndarray) -> np.ndarray:
        """
        Compose the dual-panel display with:
        - Left panel: Deck visualizer with cropped Opentrons video overlaid on top
        - Right panel: Second robot video stream with data overlay
        """
        # Target output dimensions
        output_width = 1600
        output_height = 900

        # Create output canvas
        canvas = np.zeros((output_height, output_width, 3), dtype=np.uint8)

        # Left panel width (for deck + cropped opentrons video)
        left_panel_width = output_width // 2
        right_panel_width = output_width - left_panel_width

        # ===== LEFT PANEL: Cropped Opentrons Video on top, Deck Visualizer below =====

        # First, calculate the cropped Opentrons video size
        ot_h, ot_w = opentrons_frame.shape[:2]
        crop_x1 = ot_w // 3
        crop_x2 = 2 * ot_w // 3
        crop_y1 = ot_h // 3
        crop_y2 = 2 * ot_h // 3
        cropped_ot = opentrons_frame[crop_y1:crop_y2, crop_x1:crop_x2]

        # Scale cropped video to fit in top portion (about 40% of panel width)
        overlay_w = int(left_panel_width * 0.5)
        overlay_h = int(overlay_w * cropped_ot.shape[0] / cropped_ot.shape[1])
        cropped_ot = cv2.resize(cropped_ot, (overlay_w, overlay_h), interpolation=cv2.INTER_AREA)

        # Position video at top of left panel, centered
        ot_overlay_x = (left_panel_width - overlay_w) // 2
        ot_overlay_y = 10

        # Draw video with border
        cv2.rectangle(canvas, (ot_overlay_x - 2, ot_overlay_y - 2),
                     (ot_overlay_x + overlay_w + 2, ot_overlay_y + overlay_h + 2),
                     (0, 255, 255), 2)  # Yellow border
        canvas[ot_overlay_y:ot_overlay_y + overlay_h, ot_overlay_x:ot_overlay_x + overlay_w] = cropped_ot

        # Calculate space remaining for deck (below video)
        video_bottom = ot_overlay_y + overlay_h + 10
        deck_area_height = output_height - video_bottom - 80  # Leave room for status text at bottom

        # Render deck visualizer
        if self.visualizer_enabled:
            # Update animation state
            if self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                cmd = self.protocol_commands[self.current_command_index]
                self.deck_visualizer.update_animation(self.current_command_index, cmd)
            else:
                self.deck_visualizer.update_animation(self.current_command_index, None)

            deck_frame = self.deck_visualizer.render()
        else:
            # Create placeholder deck frame
            deck_frame = np.zeros((700, 800, 3), dtype=np.uint8)
            # Show "Loading..." if we're in the process of loading
            if "Loading" in self.status_message:
                cv2.putText(deck_frame, "Loading protocol...", (250, 340),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 200), 2, cv2.LINE_AA)
                cv2.putText(deck_frame, "Please wait", (300, 380),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 150, 150), 1, cv2.LINE_AA)
            else:
                cv2.putText(deck_frame, "Load protocol to see deck", (200, 350),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2, cv2.LINE_AA)

        # Scale deck to fit in remaining space below video
        deck_h, deck_w = deck_frame.shape[:2]
        deck_scale = min(left_panel_width / deck_w, deck_area_height / deck_h)
        scaled_deck_w = int(deck_w * deck_scale)
        scaled_deck_h = int(deck_h * deck_scale)
        deck_frame = cv2.resize(deck_frame, (scaled_deck_w, scaled_deck_h), interpolation=cv2.INTER_AREA)

        # Position deck centered horizontally, below the video
        deck_x = (left_panel_width - scaled_deck_w) // 2
        deck_y = video_bottom
        canvas[deck_y:deck_y + scaled_deck_h, deck_x:deck_x + scaled_deck_w] = deck_frame

        # Store visualizer rect for mouse mapping (needed for tiprack click functionality)
        # Format: (x, y, width, height, scale)
        self.visualizer_rect = (deck_x, deck_y, scaled_deck_w, scaled_deck_h, deck_scale)

        # Store left panel rect for mouse detection
        self.opentrons_panel_rect = (0, 0, left_panel_width, output_height)

        # Draw Opentrons status overlay on left panel
        self._draw_opentrons_overlay(canvas, left_panel_width, output_height)

        # ===== RIGHT PANEL: Second Robot Video =====

        right_panel_x = left_panel_width

        # Get second robot frame (or create placeholder)
        # No lock needed - polling in main thread now
        if self.second_robot_frame is not None:
            sr_frame = self.second_robot_frame.copy()
        else:
            sr_frame = None

        if sr_frame is None:
            sr_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(sr_frame, "Second Robot", (180, 220),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2, cv2.LINE_AA)
            cv2.putText(sr_frame, "Waiting for connection...", (140, 260),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 1, cv2.LINE_AA)

        # Scale second robot frame to fit right panel
        sr_h, sr_w = sr_frame.shape[:2]
        sr_scale = min(right_panel_width / sr_w, (output_height - 150) / sr_h)  # Leave room for data
        scaled_sr_w = int(sr_w * sr_scale)
        scaled_sr_h = int(sr_h * sr_scale)
        sr_frame = cv2.resize(sr_frame, (scaled_sr_w, scaled_sr_h), interpolation=cv2.INTER_AREA)

        # Position second robot video
        sr_x = right_panel_x + (right_panel_width - scaled_sr_w) // 2
        sr_y = 10
        canvas[sr_y:sr_y + scaled_sr_h, sr_x:sr_x + scaled_sr_w] = sr_frame

        # Store video rect for drag-line feature (used for mouse detection and scaling)
        self.drag_line_video_rect = (sr_x, sr_y, scaled_sr_w, scaled_sr_h)

        # Store right panel rect for mouse detection
        self.second_robot_panel_rect = (right_panel_x, 0, right_panel_width, output_height)

        # Draw drag line if active (Ctrl/Shift + drag in video area)
        self._draw_drag_line(canvas)

        # Draw second robot overlay (data, FPS, command input)
        self._draw_second_robot_overlay(canvas, right_panel_x, right_panel_width, sr_y + scaled_sr_h + 10, output_height)

        # Draw panel indicator (which panel is active)
        self._draw_active_panel_indicator(canvas, left_panel_width, output_height)

        return canvas

    def _compose_single_panel_display(self, opentrons_frame: np.ndarray) -> np.ndarray:
        """
        Compose single-panel display (Opentrons only, no microscope):
        - Top: Cropped Opentrons video
        - Bottom: Deck visualizer
        Creates a tall, narrow window suitable for placing beside the C++ microscope app.
        Width matches the left panel width from dual-panel mode (800px = half of 1600).
        """
        # Target output dimensions - taller to fit larger deck
        output_width = 900   # Wider to fit larger deck
        output_height = 1100  # Taller for larger deck

        # Create output canvas
        canvas = np.zeros((output_height, output_width, 3), dtype=np.uint8)

        # ===== TOP: Cropped Opentrons Video (small) =====
        ot_h, ot_w = opentrons_frame.shape[:2]
        # Crop to center third (most relevant area)
        crop_x1 = ot_w // 3
        crop_x2 = 2 * ot_w // 3
        crop_y1 = ot_h // 3
        crop_y2 = 2 * ot_h // 3
        cropped_ot = opentrons_frame[crop_y1:crop_y2, crop_x1:crop_x2]

        # Scale cropped video to half width (2x smaller)
        video_w = (output_width - 20) // 2
        video_h = int(video_w * cropped_ot.shape[0] / cropped_ot.shape[1])
        cropped_ot = cv2.resize(cropped_ot, (video_w, video_h), interpolation=cv2.INTER_AREA)

        # Position video at top, centered
        video_x = (output_width - video_w) // 2
        video_y = 10

        # Draw video with border
        cv2.rectangle(canvas, (video_x - 2, video_y - 2),
                     (video_x + video_w + 2, video_y + video_h + 2),
                     (0, 255, 255), 2)  # Yellow border
        canvas[video_y:video_y + video_h, video_x:video_x + video_w] = cropped_ot

        # ===== BOTTOM: Deck Visualizer (large) =====
        deck_top = video_y + video_h + 10
        deck_area_height = output_height - deck_top - 80  # More room for larger deck

        # Render deck visualizer
        if self.visualizer_enabled:
            if self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                cmd = self.protocol_commands[self.current_command_index]
                self.deck_visualizer.update_animation(self.current_command_index, cmd)
            else:
                self.deck_visualizer.update_animation(self.current_command_index, None)

            deck_frame = self.deck_visualizer.render()
        else:
            deck_frame = np.zeros((700, 800, 3), dtype=np.uint8)
            if "Loading" in self.status_message:
                cv2.putText(deck_frame, "Loading protocol...", (250, 340),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 200), 2, cv2.LINE_AA)
            else:
                cv2.putText(deck_frame, "Load protocol to see deck", (200, 350),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2, cv2.LINE_AA)

        # Scale deck to fit
        deck_h, deck_w = deck_frame.shape[:2]
        deck_scale = min((output_width - 20) / deck_w, deck_area_height / deck_h)
        scaled_deck_w = int(deck_w * deck_scale)
        scaled_deck_h = int(deck_h * deck_scale)
        deck_frame = cv2.resize(deck_frame, (scaled_deck_w, scaled_deck_h), interpolation=cv2.INTER_AREA)

        # Position deck centered
        deck_x = (output_width - scaled_deck_w) // 2
        deck_y = deck_top
        canvas[deck_y:deck_y + scaled_deck_h, deck_x:deck_x + scaled_deck_w] = deck_frame

        # Store visualizer rect for mouse mapping
        self.visualizer_rect = (deck_x, deck_y, scaled_deck_w, scaled_deck_h, deck_scale)
        self.opentrons_panel_rect = (0, 0, output_width, output_height)

        # ===== STATUS OVERLAY =====
        self._draw_opentrons_overlay(canvas, output_width, output_height)

        return canvas

    def _draw_opentrons_overlay(self, canvas: np.ndarray, panel_width: int, panel_height: int):
        """Draw Opentrons status info on the left panel."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        line_type = cv2.LINE_AA
        small_scale = 0.5
        tiny_scale = 0.4
        thickness = 1

        # Draw "Load Protocol" button at top-left
        btn_x, btn_y = 10, 10
        btn_w, btn_h = 120, 30
        btn_color = (80, 80, 80)  # Dark gray background
        btn_border = (0, 200, 0)  # Green border
        btn_text_color = (0, 255, 0)  # Green text

        # Check if mouse is hovering over button
        if hasattr(self, '_mouse_pos'):
            mx, my = self._mouse_pos
            if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
                btn_color = (60, 100, 60)  # Lighter when hovered
                btn_border = (0, 255, 0)  # Brighter green

        cv2.rectangle(canvas, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), btn_color, -1)
        cv2.rectangle(canvas, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), btn_border, 2)
        cv2.putText(canvas, "Load Protocol", (btn_x + 8, btn_y + 20),
                   font, tiny_scale, btn_text_color, thickness, line_type)

        # Store button rect for click detection
        self.load_protocol_button_rect = (btn_x, btn_y, btn_w, btn_h)

        # Command input at bottom left (highlighted if active)
        input_y = panel_height - 60
        input_color = (0, 255, 255) if self.active_panel == 'opentrons' else (0, 180, 0)
        cv2.putText(canvas, f"OT> {self.command_input}_", (10, input_y),
                   font, small_scale, input_color, thickness, line_type)

        # Context-sensitive help
        suggestions = self.get_command_suggestions()
        if suggestions and self.active_panel == 'opentrons':
            cv2.putText(canvas, suggestions[:60], (10, input_y + 20),
                       font, tiny_scale, (0, 200, 0), thickness, line_type)

        # Status message at very bottom
        status_color = (0, 255, 0) if not self.error_message else (0, 0, 255)
        status_text = (self.error_message if self.error_message else self.status_message)[:80]
        cv2.putText(canvas, status_text, (10, panel_height - 10),
                   font, tiny_scale, status_color, thickness, line_type)

        # Position info (bottom right of left panel)
        pos_x = panel_width - 180
        pos_y = panel_height - 80

        curr_x = self.current_position.get('x', 0)
        curr_y = self.current_position.get('y', 0)
        curr_z = self.current_position.get('z', 0)

        x_color = (0, 0, 255) if (curr_x < 20 or curr_x > self.limits['x']['max'] - 20) else (0, 255, 0)
        y_color = (0, 0, 255) if (curr_y < 20 or curr_y > self.limits['y']['max'] - 20) else (0, 255, 0)
        z_color = (0, 0, 255) if (curr_z < 20 or not self.position_initialized) else (0, 255, 0)

        cv2.putText(canvas, f"X:{curr_x:.1f}", (pos_x, pos_y), font, tiny_scale, x_color, thickness, line_type)
        cv2.putText(canvas, f"Y:{curr_y:.1f}", (pos_x + 60, pos_y), font, tiny_scale, y_color, thickness, line_type)
        cv2.putText(canvas, f"Z:{curr_z:.1f}", (pos_x + 120, pos_y), font, tiny_scale, z_color, thickness, line_type)

        # Protocol status
        if self.protocol_commands:
            current_step = sum(1 for c in self.protocol_commands[:self.current_command_index] if c["commandType"] != "comment")
            total_steps = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")
            protocol_text = f"Step {current_step}/{total_steps}"
            if self.protocol_paused:
                protocol_text += " PAUSED"
            cv2.putText(canvas, protocol_text, (pos_x, pos_y + 20),
                       font, tiny_scale, (0, 255, 0), thickness, line_type)

    def _draw_second_robot_overlay(self, canvas: np.ndarray, panel_x: int, panel_width: int, data_y: int, panel_height: int):
        """Draw second robot data and command input on the right panel."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        line_type = cv2.LINE_AA
        small_scale = 0.5
        tiny_scale = 0.4
        thickness = 1

        # Data lines (stacked green text)
        y = data_y
        cv2.putText(canvas, f"FPS: {self.second_robot_fps:.1f}", (panel_x + 10, y),
                   font, small_scale, (0, 255, 0), thickness, line_type)
        y += 25

        # Connection status
        status_text = "Connected" if self.second_robot_connected else "Disconnected"
        status_color = (0, 255, 0) if self.second_robot_connected else (0, 0, 255)
        cv2.putText(canvas, status_text, (panel_x + 100, data_y),
                   font, small_scale, status_color, thickness, line_type)

        # Data from second robot
        for line in self.second_robot_data_lines[:8]:  # Max 8 lines
            cv2.putText(canvas, line[:50], (panel_x + 10, y),
                       font, tiny_scale, (0, 255, 0), thickness, line_type)
            y += 20

        # Command input at bottom (highlighted if active)
        input_y = panel_height - 60
        input_color = (0, 255, 255) if self.active_panel == 'second_robot' else (0, 180, 0)
        cv2.putText(canvas, f"SR> {self.second_robot_command_input}_", (panel_x + 10, input_y),
                   font, small_scale, input_color, thickness, line_type)

        # Context-sensitive command suggestions
        if self.active_panel == 'second_robot':
            suggestions = self.get_microscope_command_suggestions()
            if suggestions:
                # Truncate if too long for panel
                max_chars = panel_width // 7  # Approximate char width
                if len(suggestions) > max_chars:
                    suggestions = suggestions[:max_chars - 3] + "..."
                cv2.putText(canvas, suggestions, (panel_x + 10, input_y + 20),
                           font, tiny_scale, (0, 200, 0), thickness, line_type)

    def _draw_active_panel_indicator(self, canvas: np.ndarray, left_panel_width: int, panel_height: int):
        """Draw indicator showing which panel is active for input."""
        # Draw dividing line between panels
        cv2.line(canvas, (left_panel_width, 0), (left_panel_width, panel_height), (80, 80, 80), 2)

        # Draw active indicator at top
        if self.active_panel == 'opentrons':
            cv2.rectangle(canvas, (0, 0), (left_panel_width, 5), (0, 255, 255), -1)
        else:
            cv2.rectangle(canvas, (left_panel_width, 0), (canvas.shape[1], 5), (0, 255, 255), -1)

    def _update_active_panel_from_click(self, x: int, y: int):
        """Update which panel is active based on mouse click position."""
        if self.opentrons_panel_rect:
            ox, oy, ow, oh = self.opentrons_panel_rect
            if ox <= x < ox + ow and oy <= y < oy + oh:
                if self.active_panel != 'opentrons':
                    self.active_panel = 'opentrons'
                    print("Switched to Opentrons panel")
                return True  # Click was in a panel

        if self.second_robot_panel_rect:
            sx, sy, sw, sh = self.second_robot_panel_rect
            if sx <= x < sx + sw and sy <= y < sy + sh:
                if self.active_panel != 'second_robot':
                    self.active_panel = 'second_robot'
                    print("Switched to Second Robot panel")
                return True  # Click was in a panel

        return False  # Click was not in either panel

    def run(self):
        """Main GUI loop."""
        print("Starting Opentrons Control GUI...")
        print("Press ESC to quit, or type Q + Enter")

        # ===== FEATURE TOGGLES FOR DEBUGGING =====
        # Normal operation: all True except AUTO_HOME
        # For ZMQ testing: set all to False (minimal mode matching robot_socket.py)
        ENABLE_OPENTRONS_VIDEO = True       # Read frames from Opentrons camera
        ENABLE_COMMAND_PROCESSING = True    # Process command queue results
        ENABLE_KEYBOARD_INPUT = True        # Handle keyboard input
        ENABLE_FULL_DISPLAY = True          # Full display (single or dual panel based on ENABLE_MICROSCOPE)
        ENABLE_AUTO_HOME = False            # Auto-home on startup

        print(f"\n=== FEATURE TOGGLES ===")
        print(f"  Opentrons video: {ENABLE_OPENTRONS_VIDEO}")
        print(f"  Command processing: {ENABLE_COMMAND_PROCESSING}")
        print(f"  Keyboard input: {ENABLE_KEYBOARD_INPUT}")
        print(f"  Full display: {ENABLE_FULL_DISPLAY}")
        print(f"  Auto-home: {ENABLE_AUTO_HOME}")
        print(f"  Microscope: {self.ENABLE_MICROSCOPE}")
        print(f"========================\n")

        cv2.namedWindow('Opentrons Control', cv2.WINDOW_NORMAL)
        cv2.setMouseCallback('Opentrons Control', self._handle_visualizer_mouse)

        # Auto-home on startup
        if ENABLE_AUTO_HOME:
            print("\nAuto-homing on startup...")
            self.status_message = "Auto-homing on startup..."
            self._execute_single_command('h', 'H')

        while self.running:
            # MINIMAL TEST MODE: Skip everything except ZMQ and display
            # Only available when microscope is enabled (need ZMQ socket)
            if self.ENABLE_MICROSCOPE and not ENABLE_COMMAND_PROCESSING and not ENABLE_OPENTRONS_VIDEO and not ENABLE_KEYBOARD_INPUT and not ENABLE_FULL_DISPLAY:
                # Use BLOCKING receive like robot_socket.py for lowest latency
                # This waits until a frame arrives - no polling overhead
                img_bytes = self.zmq_image_socket.recv()  # BLOCKING
                self.zmq_diag_frames += 1
                img = np.frombuffer(img_bytes, dtype=np.uint8)
                img = img.reshape((self.second_robot_frame_size[1], self.second_robot_frame_size[0], 3))
                cv2.imshow('Opentrons Control', img)

                # FPS diagnostics
                now = time.time()
                diag_elapsed = now - self.zmq_diag_start
                if diag_elapsed >= 2.0:
                    #print(f"[ZMQ] FPS: {self.zmq_diag_frames/diag_elapsed:.2f}")
                    self.zmq_diag_start = now
                    self.zmq_diag_frames = 0

                if cv2.waitKey(1) & 0xFF == 27:
                    break
                continue

            # Check for completed commands (non-blocking)
            if ENABLE_COMMAND_PROCESSING:
                try:
                    result = self.result_queue.get_nowait()
                    if "error" in result:
                        self.error_message = f"Command error: {result['error']}"
                        print(f"\nCommand error: {self.error_message}")
                        self.command_executing = False  # Command finished (with error)
                        self.pending_home_initialization = False  # Cancel initialization on error
                        # Pause protocol on error - user can unpause with Tab to continue
                        if self.protocol_commands:
                            self.protocol_paused = True
                            self.executing_protocol_command = False
                            self.advance_on_command_complete = False  # Don't auto-advance after error
                            step_num = sum(1 for c in self.protocol_commands[:self.current_command_index + 1] if c["commandType"] != "comment")
                            self.status_message = f"PAUSED on step {step_num} error. Tab=resume (skip error), Enter=retry"
                            print(f"Protocol paused due to error. Press Tab to skip and continue, or Enter to retry.")
                    elif result.get("status") == "succeeded":
                        print(f"\nCommand completed successfully")
                        self.error_message = ""

                        # Track which pipette was just used by looking at the RESULT, not the protocol command
                        # This ensures we sync to whichever pipette actually just moved
                        result_params = result.get("params", {})

                        # Check if this command involved a pipette (look at the actual executed command)
                        result_cmd_type = result.get("commandType", "")
                        if "pipetteId" in result_params:
                            pipette_id = result_params["pipetteId"]
                            # Find which mount this pipette is on
                            for mount, pid in self.instrument_ids.items():
                                if pid == pipette_id and mount in ["left", "right"]:
                                    # ALWAYS update active pipette to match what just moved
                                    if self.active_pipette != mount:
                                        print(f"\nCommand used {mount} pipette (ID: {pipette_id}) - syncing active pipette")
                                        self.active_pipette = mount
                                        # Update limits to match this pipette
                                        if mount in self.instrument_limits:
                                            self.limits = self.instrument_limits[mount]
                                            print(f"  Active pipette: {mount}, limits: X={self.limits['x']['max']:.1f}, Y={self.limits['y']['max']:.1f}, Z={self.limits['z']['max']:.1f}")
                                    # Track tip state
                                    if result_cmd_type == "pickUpTip":
                                        self._pipette_has_tip[mount] = True
                                        print(f"  Tip tracking: {mount} pipette now HAS tip")
                                    elif result_cmd_type in ("dropTip", "dropTipInPlace"):
                                        self._pipette_has_tip[mount] = False
                                        print(f"  Tip tracking: {mount} pipette tip DROPPED")
                                    # Track last pipette action for prepareToAspirate logic
                                    if result_cmd_type in ("aspirate", "aspirateInPlace", "dispense", "dispenseInPlace",
                                                           "blowout", "blowOutInPlace", "pickUpTip", "dropTip", "dropTipInPlace"):
                                        self._last_pipette_action = result_cmd_type
                                    break

                        # Track gripper usage from moveLabware commands
                        # Check the protocol command to see if it used the gripper
                        if self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                            current_cmd = self.protocol_commands[self.current_command_index]
                            cmd_type = current_cmd.get("commandType", "")
                            cmd_params = current_cmd.get("params", {})

                            # moveLabware with gripperStrategy uses the gripper
                            if cmd_type == "moveLabware" and "strategy" in cmd_params:
                                strategy = cmd_params.get("strategy", "")
                                if strategy == "usingGripper" or cmd_params.get("useGripper"):
                                    if self.active_pipette != "gripper":
                                        print(f"\nCommand used gripper (moveLabware) - syncing to gripper")
                                        self._switch_to_gripper_position()

                            # robot/moveTo with mount='extension' uses the gripper
                            if cmd_type == "robot/moveTo":
                                mount = cmd_params.get("mount", "")
                                if mount == "extension":
                                    if self.active_pipette != "gripper":
                                        print(f"\nCommand used gripper (robot/moveTo) - syncing to gripper")
                                        self._switch_to_gripper_position()

                        # Also track loadPipette commands from protocol
                        if self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                            completed_cmd = self.protocol_commands[self.current_command_index]
                            cmd_type = completed_cmd.get("commandType", "")

                            if cmd_type == "loadPipette":
                                cmd_params = completed_cmd.get("params", {})
                                mount = cmd_params.get("mount")
                                if mount in ["left", "right"]:
                                    # Get the actual pipette ID from the result
                                    pipette_id = result.get("result", {}).get("pipetteId")
                                    if pipette_id:
                                        old_id = self.instrument_ids.get(mount, "none")
                                        print(f"\nProtocol loaded {mount} pipette (ID: {pipette_id})")
                                        print(f"  Updating instrument_ids[{mount}]: {old_id[:8] if old_id != 'none' else 'none'}... -> {pipette_id[:8]}...")
                                        self.instrument_ids[mount] = pipette_id
                                        # ALWAYS activate the pipette that was just loaded (unless gripper is active)
                                        if self.active_pipette != 'gripper':
                                            print(f"  Activating {mount} pipette for manual commands")
                                            self.active_pipette = mount
                                            # Update limits to match this pipette
                                            if mount in self.instrument_limits:
                                                self.limits = self.instrument_limits[mount]
                                                print(f"  Switched to {mount} pipette limits")

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

                        # Check if there are more moves in a safe Z sequence
                        if hasattr(self, '_pending_move_sequence') and self._pending_move_sequence:
                            # Execute the next move in the sequence
                            self._execute_next_pending_move()
                            continue  # Skip the normal protocol advancement logic

                        # Handle G command continuation (from protocol comments)
                        # The index was already advanced when we processed the G comment
                        if self.pending_g_command_continuation:
                            self.pending_g_command_continuation = False
                            if self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                                if self.protocol_auto_advance and not self.protocol_paused:
                                    time.sleep(0.1)
                                    self.execute_next_protocol_step()
                            continue  # Skip the normal protocol advancement logic

                        # Advance to next protocol step ONLY if this was a protocol command
                        # Use advance_on_command_complete which survives pause (unlike executing_protocol_command)
                        # This prevents re-executing the same command after pause/unpause
                        # Skip advance if this was a helper command (e.g. prepareToAspirate before aspirateInPlace)
                        if self._skip_next_advance:
                            self._skip_next_advance = False
                            self.command_executing = False
                        elif self.advance_on_command_complete and self.protocol_commands and self.current_command_index < len(self.protocol_commands):
                            self.current_command_index += 1
                            self.advance_on_command_complete = False  # Reset flag
                            self.executing_protocol_command = False  # Also reset this flag
                            # Count completed steps
                            step_num = sum(1 for c in self.protocol_commands[:self.current_command_index] if c["commandType"] != "comment")
                            total_steps = sum(1 for c in self.protocol_commands if c["commandType"] != "comment")

                            # Auto-advance to next step if enabled and not paused
                            if self.protocol_auto_advance and not self.protocol_paused:
                                self.status_message = f"Step {step_num}/{total_steps} complete. Auto-advancing..."
                                # Automatically execute next step after a brief pause
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

            # --- Timing instrumentation ---
            _t0 = time.time()

            # Poll for ZMQ frames from second robot
            self._poll_zmq_frame()  # With CONFLATE, gets at most 1 (the latest)

            _t1 = time.time()

            # Grab latest Opentrons frame from background thread (non-blocking)
            with self._ot_frame_lock:
                opentrons_frame = self._ot_latest_frame
            if opentrons_frame is None:
                opentrons_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

            _t2 = time.time()

            # Compose display based on microscope mode
            if self.ENABLE_MICROSCOPE:
                frame = self._compose_dual_panel_display(opentrons_frame)
            else:
                frame = self._compose_single_panel_display(opentrons_frame)

            _t3 = time.time()

            # Display main control window
            cv2.imshow('Opentrons Control', frame)

            _t4 = time.time()

            # Print timing every 2 seconds
            if not hasattr(self, '_timing_start'):
                self._timing_start = time.time()
                self._timing_count = 0
                self._timing_zmq = 0
                self._timing_compose = 0
                self._timing_imshow = 0
            self._timing_count += 1
            self._timing_zmq += (_t1 - _t0)
            self._timing_compose += (_t3 - _t2)
            self._timing_imshow += (_t4 - _t3)
            if time.time() - self._timing_start >= 2.0:
                n = self._timing_count
                #print(f"[LOOP] {n/2.0:.1f} FPS | zmq: {self._timing_zmq/n*1000:.1f}ms | compose: {self._timing_compose/n*1000:.1f}ms | imshow: {self._timing_imshow/n*1000:.1f}ms | total: {2000/n:.0f}ms")
                self._timing_start = time.time()
                self._timing_count = 0
                self._timing_zmq = 0
                self._timing_compose = 0
                self._timing_imshow = 0

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC - immediate quit
                print("\nESC pressed - quitting immediately...")
                break
            elif key == 13:  # Enter - handle based on active panel
                if self.active_panel == 'opentrons':
                    # Opentrons Enter handling
                    if self.command_input:
                        if self.command_executing:
                            self.user_command_queue.append(self.command_input)
                            print(f"Command queued: {self.command_input} (queue length: {len(self.user_command_queue)})")
                            self.status_message = f"Command queued: {self.command_input}"
                        else:
                            self.command_executing = True
                            self.execute_manual_command(self.command_input)
                        self.command_input = ""
                    elif self.pending_command:
                        print("\nExecuting pending command...")
                        cmd_data = self.pending_command
                        self.command_executing = True
                        self.command_queue.put(cmd_data["cmd"])
                        self.pending_command = None
                        self.status_message = "Command executing..."
                    else:
                        # Enter without input = advance protocol step
                        if self.error_message and self.protocol_commands:
                            print("\nSkipping failed command, advancing to next step...")
                            self.current_command_index += 1
                            self.error_message = ""
                        self.execute_next_protocol_step()
                else:
                    # Second robot Enter handling - send command
                    if self.second_robot_command_input:
                        self.send_second_robot_command(self.second_robot_command_input)
                        self.second_robot_command_input = ""
            elif key == 10:  # Ctrl+Enter (on some systems)
                if self.active_panel == 'opentrons':
                    if self.error_message and self.protocol_commands:
                        print("\nSkipping failed command, advancing to next step...")
                        self.current_command_index += 1
                        self.error_message = ""
                    self.execute_next_protocol_step()
            elif key == 9:  # Tab
                self.protocol_paused = not self.protocol_paused
                if self.protocol_paused:
                    self.executing_protocol_command = False  # Reset so manual commands don't advance index
                    self.status_message = "Protocol PAUSED"
                else:
                    # If resuming after an error, skip the failed command
                    if self.error_message and self.protocol_commands:
                        failed_cmd = self.protocol_commands[self.current_command_index]
                        failed_cmd_type = failed_cmd.get("commandType", "")

                        # Smart skip: if we failed on pickUpTip, skip all commands until dropTip
                        # since they all require the tip that wasn't picked up
                        if failed_cmd_type == "pickUpTip":
                            skipped = 0
                            while self.current_command_index < len(self.protocol_commands):
                                cmd = self.protocol_commands[self.current_command_index]
                                cmd_type = cmd.get("commandType", "")
                                self.current_command_index += 1
                                skipped += 1
                                if cmd_type == "dropTip":
                                    break
                            print(f"\nSkipped {skipped} commands (pickUpTip failed -> skipping to after dropTip)")
                            self.status_message = f"Skipped {skipped} cmds (no tip)"
                        else:
                            print("\nSkipping failed command, resuming protocol...")
                            self.current_command_index += 1
                            self.status_message = "Protocol RESUMED (skipped error)"
                        self.error_message = ""
                    else:
                        self.status_message = "Protocol RESUMED"
                print(f"\n{self.status_message}")
                self._log("COMMAND", self.status_message)

                # If unpausing and auto-advance is enabled, start executing protocol
                if not self.protocol_paused and self.protocol_auto_advance and self.protocol_commands:
                    if not self.command_executing:
                        self.execute_next_protocol_step()
            elif key == 12:  # Ctrl+L - Load protocol
                print("\nOpening protocol file dialog...")
                self.open_protocol_dialog()
            elif key == 21:  # Ctrl+U - Load media change CSV (U for Upload)
                print("\nOpening media change CSV dialog...")
                self.open_csv_dialog()
            elif key == 8:  # Backspace - handle based on active panel
                if self.active_panel == 'opentrons':
                    self.command_input = self.command_input[:-1]
                else:
                    self.second_robot_command_input = self.second_robot_command_input[:-1]
            elif 32 <= key <= 126:  # Printable characters (including +, -, =, etc.)
                # Add to appropriate command input based on active panel
                if self.active_panel == 'opentrons':
                    self.command_input += chr(key).upper()
                else:
                    self.second_robot_command_input += chr(key).upper()

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
