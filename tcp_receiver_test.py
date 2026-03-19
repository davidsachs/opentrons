#!/usr/bin/env python3
"""
Raw TCP video receiver test - lower latency alternative to ZMQ.

The C++ sender would need to be modified to send over TCP instead of ZMQ PUB.
For testing, this includes a simple sender thread.
"""

import socket
import cv2
import numpy as np
import time
import threading
import struct

# Configuration
TCP_IP = "127.0.0.1"
TCP_PORT = 5560
FRAME_WIDTH = 1280
FRAME_HEIGHT = 960
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 3  # BGR

def tcp_receiver():
    """Receive frames over raw TCP."""
    # Create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 10 * 1024 * 1024)  # 10MB buffer
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's algorithm

    print(f"Connecting to {TCP_IP}:{TCP_PORT}...")

    try:
        sock.connect((TCP_IP, TCP_PORT))
    except ConnectionRefusedError:
        print("Connection refused - make sure sender is running")
        return

    print(f"Connected! Expected frame size: {FRAME_SIZE} bytes")
    sock.setblocking(True)  # Use blocking for TCP

    # FPS tracking
    diag_start = time.time()
    diag_frames = 0

    # Receive buffer
    buffer = bytearray()

    while True:
        try:
            # Read frame size header (4 bytes)
            while len(buffer) < 4:
                chunk = sock.recv(65536)
                if not chunk:
                    print("Connection closed")
                    return
                buffer.extend(chunk)

            # Parse frame size
            frame_size = struct.unpack('<I', buffer[:4])[0]
            buffer = buffer[4:]

            # Read frame data
            while len(buffer) < frame_size:
                chunk = sock.recv(65536)
                if not chunk:
                    print("Connection closed")
                    return
                buffer.extend(chunk)

            # Extract frame
            frame_data = buffer[:frame_size]
            buffer = buffer[frame_size:]

            # Decode and display
            diag_frames += 1
            img = np.frombuffer(frame_data, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
            cv2.imshow("TCP Video", img)

        except Exception as e:
            print(f"Error: {e}")
            break

        # FPS diagnostics
        now = time.time()
        diag_elapsed = now - diag_start
        if diag_elapsed >= 2.0:
            print(f"[TCP] FPS: {diag_frames/diag_elapsed:.2f}")
            diag_start = now
            diag_frames = 0

        if cv2.waitKey(1) & 0xFF == 27:
            break

    sock.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    print("Raw TCP Video Receiver")
    print("=" * 40)
    print("This requires modifying the C++ sender to use TCP.")
    print("For now, testing ZMQ performance improvements...")
    print()

    # For now, let's test if we can improve ZMQ performance
    # by using a different pattern or settings
    import zmq

    context = zmq.Context()

    # Try PULL socket instead of SUB (different pattern, might have less overhead)
    # Note: sender would need to use PUSH instead of PUB
    print("Testing ZMQ with optimizations...")

    # Use the existing ZMQ SUB socket but with optimizations
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.RCVHWM, 1)  # Only buffer 1 message
    socket.setsockopt(zmq.RCVBUF, 0)  # Let OS manage buffer
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.connect("tcp://localhost:5557")

    diag_start = time.time()
    diag_frames = 0

    print("Receiving frames...")

    while True:
        try:
            # Try blocking receive (like original robot_socket.py that got 11fps)
            img_bytes = socket.recv()
            diag_frames += 1
            img = np.frombuffer(img_bytes, dtype=np.uint8)
            img = img.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
            cv2.imshow("ZMQ Optimized", img)
        except Exception as e:
            print(f"Error: {e}")

        now = time.time()
        diag_elapsed = now - diag_start
        if diag_elapsed >= 2.0:
            print(f"[ZMQ OPT] FPS: {diag_frames/diag_elapsed:.2f}")
            diag_start = now
            diag_frames = 0

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cv2.destroyAllWindows()
