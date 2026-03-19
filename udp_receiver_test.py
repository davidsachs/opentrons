#!/usr/bin/env python3
"""
UDP video receiver test - lower latency alternative to ZMQ.

This receives raw BGR frames over UDP. Since frames are ~3.7MB and UDP max packet
is ~65KB, we need to chunk the data. The sender must also be modified to use UDP.

For now, this tests receiving from a simple UDP sender.
"""

import socket
import cv2
import numpy as np
import time

# Configuration
UDP_IP = "0.0.0.0"  # Listen on all interfaces
UDP_PORT = 5560
FRAME_WIDTH = 1280
FRAME_HEIGHT = 960
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 3  # BGR

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 10 * 1024 * 1024)  # 10MB buffer
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

print(f"UDP receiver listening on {UDP_IP}:{UDP_PORT}")
print(f"Expected frame size: {FRAME_SIZE} bytes ({FRAME_SIZE/1024/1024:.2f} MB)")

# FPS tracking
diag_start = time.time()
diag_frames = 0

# Frame assembly buffer (for chunked frames)
frame_buffer = bytearray(FRAME_SIZE)
frame_offset = 0
current_frame_id = -1

while True:
    try:
        # Receive data (non-blocking)
        data, addr = sock.recvfrom(65536)  # Max UDP packet size

        # Simple protocol: first 4 bytes = frame_id, next 4 bytes = offset, rest = data
        if len(data) > 8:
            frame_id = int.from_bytes(data[0:4], 'little')
            offset = int.from_bytes(data[4:8], 'little')
            chunk = data[8:]

            # New frame?
            if frame_id != current_frame_id:
                current_frame_id = frame_id
                frame_offset = 0

            # Copy chunk to buffer
            end = offset + len(chunk)
            if end <= FRAME_SIZE:
                frame_buffer[offset:end] = chunk

                # Complete frame?
                if end == FRAME_SIZE:
                    diag_frames += 1
                    img = np.frombuffer(frame_buffer, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
                    cv2.imshow("UDP Video", img)

    except BlockingIOError:
        pass  # No data available
    except Exception as e:
        print(f"Error: {e}")

    # FPS diagnostics
    now = time.time()
    diag_elapsed = now - diag_start
    if diag_elapsed >= 2.0:
        print(f"[UDP] FPS: {diag_frames/diag_elapsed:.2f}")
        diag_start = now
        diag_frames = 0

    if cv2.waitKey(1) & 0xFF == 27:
        break

sock.close()
cv2.destroyAllWindows()
