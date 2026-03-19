#!/usr/bin/env python3
"""
LZ4 compressed video receiver over TCP.

Expects C++ sender to:
1. Compress BGR frame with LZ4
2. Send 4-byte size header (little-endian)
3. Send compressed data

LZ4 is extremely fast (GB/s) and provides ~2-3x compression on image data.
"""

import socket
import cv2
import numpy as np
import time
import struct

try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    print("LZ4 not installed. Run: pip install lz4")
    HAS_LZ4 = False

# Configuration
TCP_IP = "127.0.0.1"
TCP_PORT = 5562
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


def lz4_receiver():
    """Receive and display LZ4-compressed frames over TCP."""
    if not HAS_LZ4:
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle

    print(f"Connecting to {TCP_IP}:{TCP_PORT}...")

    try:
        sock.connect((TCP_IP, TCP_PORT))
    except ConnectionRefusedError:
        print("Connection refused - make sure C++ sender is running")
        return

    print("Connected! Receiving LZ4-compressed frames...")

    # Stats
    diag_start = time.time()
    diag_frames = 0
    diag_bytes_compressed = 0
    diag_bytes_raw = 0
    decompress_times = []

    while True:
        try:
            # Read 4-byte header (compressed size)
            header = receive_exact(sock, 4)
            if header is None:
                print("Connection closed")
                break

            compressed_size = struct.unpack('<I', header)[0]

            # Read compressed data
            compressed_data = receive_exact(sock, compressed_size)
            if compressed_data is None:
                print("Connection closed during frame")
                break

            diag_bytes_compressed += compressed_size

            # Decompress
            decompress_start = time.time()
            raw_data = lz4.frame.decompress(compressed_data)
            decompress_time = time.time() - decompress_start
            decompress_times.append(decompress_time)
            if len(decompress_times) > 100:
                decompress_times.pop(0)

            diag_bytes_raw += len(raw_data)

            # Convert to image
            img = np.frombuffer(raw_data, dtype=np.uint8)
            img = img.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))

            diag_frames += 1
            cv2.imshow("LZ4 Video", img)

        except Exception as e:
            print(f"Error: {e}")
            break

        # Stats every 2 seconds
        now = time.time()
        elapsed = now - diag_start
        if elapsed >= 2.0:
            fps = diag_frames / elapsed
            bandwidth_mbps = (diag_bytes_compressed * 8 / 1024 / 1024) / elapsed
            compression_ratio = diag_bytes_raw / diag_bytes_compressed if diag_bytes_compressed > 0 else 0
            avg_decompress_ms = sum(decompress_times) / len(decompress_times) * 1000 if decompress_times else 0

            print(f"FPS: {fps:.1f} | "
                  f"Bandwidth: {bandwidth_mbps:.1f} Mbps | "
                  f"Compression: {compression_ratio:.1f}x | "
                  f"Decompress: {avg_decompress_ms:.1f}ms")

            diag_start = now
            diag_frames = 0
            diag_bytes_compressed = 0
            diag_bytes_raw = 0

        if cv2.waitKey(1) & 0xFF == 27:
            break

    sock.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    print("LZ4 Lossless Video Receiver")
    print("=" * 50)
    print(f"Uncompressed frame size: {FRAME_SIZE / 1024:.1f} KB")
    print(f"Expected compressed size: ~{FRAME_SIZE / 1024 / 2.5:.1f} KB (2-3x compression)")
    print()
    lz4_receiver()
