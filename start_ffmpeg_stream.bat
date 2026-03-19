@echo off
REM Capture the Microscope window and stream via UDP
REM Run this AFTER the C++ application is showing the Microscope window

echo Starting FFmpeg capture of Microscope window...
echo Streaming to UDP port 5565
echo Press Ctrl+C to stop

ffmpeg -f gdigrab -framerate 30 -i title="Microscope" -c:v mjpeg -q:v 3 -f mjpeg udp://127.0.0.1:5565

pause
