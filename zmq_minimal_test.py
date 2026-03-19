#!/usr/bin/env python3
"""
Minimal ZMQ receiver test - isolate where the slowdown is.
"""

import zmq
import time
import sys

PORT = 5557
FRAME_SIZE = 1280 * 960 * 3

print("Minimal ZMQ Receiver Test")
print("=" * 50)

context = zmq.Context()
socket = context.socket(zmq.SUB)

# Try different socket options
print("Testing with CONFLATE=1...")
socket.setsockopt(zmq.CONFLATE, 1)
socket.setsockopt_string(zmq.SUBSCRIBE, "")
socket.connect(f"tcp://127.0.0.1:{PORT}")

# Warm up
print("Warming up (5 frames)...")
for i in range(5):
    data = socket.recv()
    print(f"  Frame {i+1}: {len(data)} bytes")

# Benchmark raw receive speed
print("\nBenchmarking raw recv() speed (no processing)...")
start = time.perf_counter()
count = 0
bytes_received = 0

while time.perf_counter() - start < 5.0:
    data = socket.recv()
    count += 1
    bytes_received += len(data)

elapsed = time.perf_counter() - start
fps = count / elapsed
bandwidth = bytes_received / elapsed / 1024 / 1024

print(f"\nResults (5 second test):")
print(f"  Frames received: {count}")
print(f"  FPS: {fps:.2f}")
print(f"  Bandwidth: {bandwidth:.2f} MB/s")
print(f"  Avg frame size: {bytes_received / count / 1024:.1f} KB")

# Now test with numpy reshape (no display)
print("\nTesting with numpy reshape (no display)...")
import numpy as np

start = time.perf_counter()
count = 0

while time.perf_counter() - start < 5.0:
    data = socket.recv()
    img = np.frombuffer(data, dtype=np.uint8)
    img = img.reshape((960, 1280, 3))
    count += 1

elapsed = time.perf_counter() - start
print(f"  FPS with numpy: {count / elapsed:.2f}")

# Now test with cv2.imshow
print("\nTesting with cv2.imshow...")
import cv2

start = time.perf_counter()
count = 0

while time.perf_counter() - start < 5.0:
    data = socket.recv()
    img = np.frombuffer(data, dtype=np.uint8)
    img = img.reshape((960, 1280, 3))
    cv2.imshow("Test", img)
    cv2.waitKey(1)
    count += 1

elapsed = time.perf_counter() - start
print(f"  FPS with imshow: {count / elapsed:.2f}")

cv2.destroyAllWindows()
print("\nDone!")
