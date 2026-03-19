#!/usr/bin/env python3
"""
Simple UDP receiver test - check if anything is arriving on port 5564.
"""

import socket
import time

UDP_PORT = 5564

print(f"Listening for UDP packets on port {UDP_PORT}...")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", UDP_PORT))
sock.settimeout(5.0)

try:
    while True:
        try:
            data, addr = sock.recvfrom(65536)
            print(f"Received {len(data)} bytes from {addr}")
        except socket.timeout:
            print("No data received in 5 seconds...")
except KeyboardInterrupt:
    print("Stopped")

sock.close()
