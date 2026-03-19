#!/usr/bin/env python3
"""
FFmpeg UDP MJPEG receiver.

1. Start the C++ application (shows Microscope window)
2. Run start_ffmpeg_stream.bat (captures window, streams to UDP)
3. Run this script to receive and display
"""

import cv2
import time

# OpenCV can read MJPEG over UDP directly
UDP_URL = "udp://127.0.0.1:5565"

print("FFmpeg UDP MJPEG Receiver")
print("=" * 50)
print(f"Connecting to: {UDP_URL}")
print()
print("Make sure:")
print("  1. C++ Microscope window is visible")
print("  2. start_ffmpeg_stream.bat is running")
print()

cap = cv2.VideoCapture(UDP_URL)

if not cap.isOpened():
    print("Failed to open UDP stream")
    print("Trying with ffmpeg backend...")
    cap = cv2.VideoCapture(UDP_URL, cv2.CAP_FFMPEG)

if not cap.isOpened():
    print("Still failed. Make sure FFmpeg stream is running.")
    exit(1)

print("Connected! Receiving frames...")

diag_start = time.time()
diag_frames = 0

while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to read frame, retrying...")
        continue

    diag_frames += 1
    cv2.imshow("FFmpeg UDP Video", frame)

    now = time.time()
    elapsed = now - diag_start
    if elapsed >= 2.0:
        fps = diag_frames / elapsed
        print(f"FPS: {fps:.1f}")
        diag_start = now
        diag_frames = 0

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
