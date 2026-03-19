#!/usr/bin/env python3
"""
GStreamer MJPEG receiver - low latency video over UDP.

This receives RTP JPEG stream from the C++ sender.
GStreamer is designed for real-time video with minimal latency.
"""

import cv2
import time

# GStreamer pipeline to receive RTP JPEG over UDP
# udpsrc: receive UDP packets on port 5564
# application/x-rtp: specify RTP format
# rtpjpegdepay: extract JPEG from RTP packets
# jpegdec: decode JPEG
# videoconvert: convert to BGR for OpenCV
# appsink: output to OpenCV

GST_PIPELINE = (
    "udpsrc port=5564 caps=\"application/x-rtp,encoding-name=JPEG,payload=26\" ! "
    "rtpjpegdepay ! "
    "jpegdec ! "
    "videoconvert ! "
    "appsink drop=true max-buffers=1 sync=false"
)

print("GStreamer MJPEG Receiver")
print("=" * 50)
print(f"Pipeline: {GST_PIPELINE}")
print()

# Try to open with GStreamer backend
cap = cv2.VideoCapture(GST_PIPELINE, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    print("ERROR: Failed to open GStreamer pipeline")
    print("Make sure GStreamer is installed and OpenCV was built with GStreamer support")
    print()
    print("To check GStreamer support:")
    print("  python -c \"import cv2; print(cv2.getBuildInformation())\" | grep -i gstreamer")
    exit(1)

print("GStreamer pipeline opened successfully!")
print("Receiving frames...")
print()

# Stats
diag_start = time.time()
diag_frames = 0

while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to read frame")
        continue

    diag_frames += 1
    cv2.imshow("GStreamer Video", frame)

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

cap.release()
cv2.destroyAllWindows()
