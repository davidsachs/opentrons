#!/usr/bin/env python3
"""
FFmpeg-based video receiver - alternative to ZMQ.

This creates a named pipe that FFmpeg writes to, and Python reads from.
Very low latency since FFmpeg is optimized for real-time video.

Usage:
1. First start the C++ sender (to create the video)
2. Run this script
3. In another terminal, run FFmpeg to capture and pipe:

For screen capture (captures the Microscope window):
  ffmpeg -f gdigrab -framerate 30 -i title="Microscope" -f rawvideo -pix_fmt bgr24 -s 1280x960 - | python ffmpeg_receiver_test.py

Or to test with a webcam:
  ffmpeg -f dshow -i video="Your Webcam Name" -f rawvideo -pix_fmt bgr24 -s 1280x960 - | python ffmpeg_receiver_test.py
"""

import sys
import cv2
import numpy as np
import time

FRAME_WIDTH = 1280
FRAME_HEIGHT = 960
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 3

print("FFmpeg Raw Video Receiver")
print("=" * 50)
print(f"Reading raw BGR frames from stdin")
print(f"Frame size: {FRAME_WIDTH}x{FRAME_HEIGHT} ({FRAME_SIZE} bytes)")
print()
print("Pipe video data to this script, e.g.:")
print("  ffmpeg -f gdigrab -framerate 30 -i title=\"Microscope\" -f rawvideo -pix_fmt bgr24 -s 1280x960 - | python ffmpeg_receiver_test.py")
print()

# Read from stdin in binary mode
if sys.platform == 'win32':
    import msvcrt
    import os
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)

stdin = sys.stdin.buffer

diag_start = time.time()
diag_frames = 0

while True:
    # Read exactly one frame
    data = stdin.read(FRAME_SIZE)

    if len(data) < FRAME_SIZE:
        print(f"Incomplete frame ({len(data)} bytes), exiting...")
        break

    # Convert to numpy array
    img = np.frombuffer(data, dtype=np.uint8)
    img = img.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))

    diag_frames += 1
    cv2.imshow("FFmpeg Video", img)

    # Stats every 2 seconds
    now = time.time()
    elapsed = now - diag_start
    if elapsed >= 2.0:
        fps = diag_frames / elapsed
        print(f"FPS: {fps:.1f}")
        diag_start = now
        diag_frames = 0

    if cv2.waitKey(1) & 0xFF == 27:
        break

cv2.destroyAllWindows()
