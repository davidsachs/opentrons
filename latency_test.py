#!/usr/bin/env python3
"""
Latency measurement test.

This measures the visible latency by:
1. Displaying a timestamp on the C++ side (already visible in microscope window)
2. Measuring when we receive that frame on Python side

For a quick visual test:
- Wave your hand in front of the camera
- Compare the delay between the C++ window and Python window
- This gives a rough sense of the end-to-end latency

For precise measurement, we'd need synchronized clocks or embedded timestamps.
"""

import zmq
import cv2
import numpy as np
import time

# Configuration
PORT = 5557
FRAME_WIDTH = 1280
FRAME_HEIGHT = 960

context = zmq.Context()

socket = context.socket(zmq.SUB)
socket.setsockopt_string(zmq.SUBSCRIBE, "")
socket.connect(f"tcp://localhost:{PORT}")

print("Latency Test - Compare this window to the C++ Microscope window")
print("=" * 60)
print("Wave your hand and observe the delay between windows.")
print("Lower delay = lower latency.")
print()

# Add timestamp to received frames to help visualize
diag_start = time.time()
diag_frames = 0
frame_times = []

while True:
    recv_start = time.time()
    img_bytes = socket.recv()  # Blocking
    recv_time = time.time() - recv_start

    diag_frames += 1
    img = np.frombuffer(img_bytes, dtype=np.uint8)
    img = img.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))

    # Add receive timestamp overlay
    timestamp = f"Recv: {time.time():.3f}"
    recv_ms = f"ZMQ recv: {recv_time*1000:.1f}ms"
    cv2.putText(img, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(img, recv_ms, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Track recv times
    frame_times.append(recv_time)
    if len(frame_times) > 100:
        frame_times.pop(0)

    cv2.imshow("Python Receiver (compare to C++ window)", img)

    # Stats every 2 seconds
    now = time.time()
    if now - diag_start >= 2.0:
        fps = diag_frames / (now - diag_start)
        avg_recv = sum(frame_times) / len(frame_times) * 1000 if frame_times else 0
        max_recv = max(frame_times) * 1000 if frame_times else 0
        min_recv = min(frame_times) * 1000 if frame_times else 0
        print(f"FPS: {fps:.1f} | recv() time: avg={avg_recv:.1f}ms, min={min_recv:.1f}ms, max={max_recv:.1f}ms")
        diag_start = now
        diag_frames = 0

    if cv2.waitKey(1) & 0xFF == 27:
        break

cv2.destroyAllWindows()
