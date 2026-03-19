#!/usr/bin/env python3
"""
PNG lossless compressed video receiver over TCP.

PNG is lossless and supported natively by OpenCV.
Compression is slower than LZ4 but no extra libraries needed on C++ side.

Protocol:
1. 4-byte header: compressed size (little-endian uint32)
2. PNG-encoded image data
"""

import socket
import cv2
import numpy as np
import time
import struct

# Configuration
TCP_IP = "127.0.0.1"
TCP_PORT = 5563
FRAME_WIDTH = 1280
FRAME_HEIGHT = 960
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 3  # Uncompressed BGR size


def receive_exact(sock, size):
    """Receive exactly 'size' bytes from socket."""
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def png_receiver():
    """Receive and display PNG-compressed frames over TCP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    print(f"Connecting to {TCP_IP}:{TCP_PORT}...")

    try:
        sock.connect((TCP_IP, TCP_PORT))
    except ConnectionRefusedError:
        print("Connection refused - make sure C++ sender is running with PNG mode")
        return

    print("Connected! Receiving PNG-compressed frames...")

    # Stats
    diag_start = time.time()
    diag_frames = 0
    diag_bytes_compressed = 0
    decode_times = []

    while True:
        try:
            # Read 4-byte header (compressed size)
            header = receive_exact(sock, 4)
            if header is None:
                print("Connection closed")
                break

            compressed_size = struct.unpack('<I', header)[0]

            # Read compressed PNG data
            compressed_data = receive_exact(sock, compressed_size)
            if compressed_data is None:
                print("Connection closed during frame")
                break

            diag_bytes_compressed += compressed_size

            # Decode PNG
            decode_start = time.time()
            img = cv2.imdecode(np.frombuffer(compressed_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            decode_time = time.time() - decode_start
            decode_times.append(decode_time)
            if len(decode_times) > 100:
                decode_times.pop(0)

            if img is None:
                print("Failed to decode frame")
                continue

            diag_frames += 1
            cv2.imshow("PNG Lossless Video", img)

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            break

        # Stats every 2 seconds
        now = time.time()
        elapsed = now - diag_start
        if elapsed >= 2.0:
            fps = diag_frames / elapsed
            bandwidth_mbps = (diag_bytes_compressed * 8 / 1024 / 1024) / elapsed
            avg_frame_kb = diag_bytes_compressed / diag_frames / 1024 if diag_frames > 0 else 0
            compression_ratio = FRAME_SIZE / (diag_bytes_compressed / diag_frames) if diag_frames > 0 else 0
            avg_decode_ms = sum(decode_times) / len(decode_times) * 1000 if decode_times else 0

            print(f"FPS: {fps:.1f} | "
                  f"Bandwidth: {bandwidth_mbps:.1f} Mbps | "
                  f"Avg frame: {avg_frame_kb:.0f} KB | "
                  f"Compression: {compression_ratio:.1f}x | "
                  f"Decode: {avg_decode_ms:.1f}ms")

            diag_start = now
            diag_frames = 0
            diag_bytes_compressed = 0

        if cv2.waitKey(1) & 0xFF == 27:
            break

    sock.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    print("PNG Lossless Video Receiver")
    print("=" * 50)
    print(f"Uncompressed frame size: {FRAME_SIZE / 1024:.1f} KB")
    print("PNG typically achieves 2-5x compression on natural images")
    print()
    png_receiver()
