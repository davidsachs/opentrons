#!/usr/bin/env python3
"""
FFmpeg pipe receiver - captures Microscope window directly.

This spawns FFmpeg as a subprocess and reads raw frames from its stdout.
Very low latency since there's no network involved.

Just run this script while the C++ Microscope window is visible.
"""

import subprocess
import cv2
import numpy as np
import time
import sys

# FFmpeg command to capture the Microscope window
# -f gdigrab: Windows screen capture
# -framerate 30: Target 30fps capture
# -i title="Microscope": Capture window with this title
# -f rawvideo: Output raw frames
# -pix_fmt bgr24: BGR format for OpenCV
# -: Output to stdout
FFMPEG_CMD = [
    'ffmpeg',
    '-f', 'gdigrab',
    '-framerate', '30',
    '-i', 'title=Microscope',
    '-f', 'rawvideo',
    '-pix_fmt', 'bgr24',
    '-'
]

print("FFmpeg Pipe Receiver")
print("=" * 50)
print("Capturing window titled 'Microscope'")
print()

# Start FFmpeg
try:
    proc = subprocess.Popen(
        FFMPEG_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # Hide FFmpeg output
        bufsize=10**8  # Large buffer
    )
except FileNotFoundError:
    print("ERROR: FFmpeg not found. Make sure it's installed and in PATH.")
    sys.exit(1)

print("FFmpeg started, detecting frame size...")

# Read first chunk to detect frame size
# gdigrab captures the full window including title bar
# We need to figure out the actual size

# First, let's try to get window info
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

def get_window_rect(title):
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        return rect.right - rect.left, rect.bottom - rect.top
    return None

size = get_window_rect("Microscope")
if size:
    width, height = size
    print(f"Detected window size: {width}x{height}")
else:
    # Default to expected size
    width, height = 1280, 960
    print(f"Could not detect window, using default: {width}x{height}")

frame_size = width * height * 3
print(f"Frame size: {frame_size} bytes")
print()

diag_start = time.time()
diag_frames = 0

while True:
    # Read one frame
    raw = proc.stdout.read(frame_size)

    if len(raw) < frame_size:
        print(f"Incomplete frame ({len(raw)} bytes), FFmpeg may have stopped")
        break

    # Convert to numpy/OpenCV format
    frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))

    diag_frames += 1
    cv2.imshow("FFmpeg Capture", frame)

    now = time.time()
    elapsed = now - diag_start
    if elapsed >= 2.0:
        fps = diag_frames / elapsed
        print(f"FPS: {fps:.1f}")
        diag_start = now
        diag_frames = 0

    if cv2.waitKey(1) & 0xFF == 27:
        break

proc.terminate()
cv2.destroyAllWindows()
print("Done")
