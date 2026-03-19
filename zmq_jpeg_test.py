#!/usr/bin/env python3
"""
Test ZMQ with JPEG compression to reduce latency.

JPEG frames are ~10x smaller than raw BGR, which means:
- Faster network transmission
- Smaller ZMQ buffers
- Lower latency

This receiver expects the C++ sender to encode JPEG before sending.
For testing, we'll also create a simple JPEG forwarder that reads from
the existing raw stream and re-publishes as JPEG.
"""

import zmq
import cv2
import numpy as np
import time
import threading

# Configuration
RAW_PORT = 5557      # Existing raw video port
JPEG_PORT = 5561     # New JPEG video port
FRAME_WIDTH = 1280
FRAME_HEIGHT = 960
JPEG_QUALITY = 80    # 0-100, higher = better quality but larger size

def jpeg_forwarder():
    """Read raw frames and republish as JPEG (for testing without modifying C++ sender)."""
    context = zmq.Context()

    # Subscribe to raw frames
    raw_socket = context.socket(zmq.SUB)
    raw_socket.setsockopt_string(zmq.SUBSCRIBE, "")
    raw_socket.connect(f"tcp://localhost:{RAW_PORT}")

    # Publish JPEG frames
    jpeg_socket = context.socket(zmq.PUB)
    jpeg_socket.bind(f"tcp://*:{JPEG_PORT}")

    print(f"JPEG forwarder: {RAW_PORT} (raw) -> {JPEG_PORT} (jpeg)")

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]

    while True:
        try:
            # Receive raw frame
            img_bytes = raw_socket.recv()
            img = np.frombuffer(img_bytes, dtype=np.uint8)
            img = img.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))

            # Encode to JPEG
            success, encoded = cv2.imencode('.jpg', img, encode_params)
            if success:
                # Send JPEG
                jpeg_socket.send(encoded.tobytes(), zmq.NOBLOCK)
        except Exception as e:
            print(f"Forwarder error: {e}")


def jpeg_receiver():
    """Receive and display JPEG frames."""
    context = zmq.Context()

    socket = context.socket(zmq.SUB)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.connect(f"tcp://localhost:{JPEG_PORT}")

    print(f"JPEG receiver connected to port {JPEG_PORT}")

    diag_start = time.time()
    diag_frames = 0
    diag_bytes = 0

    while True:
        # Blocking receive
        jpeg_bytes = socket.recv()
        diag_bytes += len(jpeg_bytes)

        # Decode JPEG
        img = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

        if img is not None:
            diag_frames += 1
            cv2.imshow("JPEG Video", img)

        # FPS and bandwidth diagnostics
        now = time.time()
        diag_elapsed = now - diag_start
        if diag_elapsed >= 2.0:
            fps = diag_frames / diag_elapsed
            bandwidth_mbps = (diag_bytes * 8 / 1024 / 1024) / diag_elapsed
            avg_frame_kb = (diag_bytes / diag_frames / 1024) if diag_frames > 0 else 0
            print(f"[JPEG] FPS: {fps:.2f}, Bandwidth: {bandwidth_mbps:.2f} Mbps, Avg frame: {avg_frame_kb:.1f} KB")
            diag_start = now
            diag_frames = 0
            diag_bytes = 0

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    print("ZMQ JPEG Streaming Test")
    print("=" * 50)
    print(f"Raw BGR frame size: {FRAME_WIDTH * FRAME_HEIGHT * 3 / 1024:.1f} KB")
    print(f"Expected JPEG size: ~{FRAME_WIDTH * FRAME_HEIGHT * 3 / 1024 / 10:.1f} KB (10x compression)")
    print()

    # Start forwarder in background thread
    forwarder_thread = threading.Thread(target=jpeg_forwarder, daemon=True)
    forwarder_thread.start()

    # Wait a moment for forwarder to start
    time.sleep(0.5)

    # Run receiver in main thread
    jpeg_receiver()
