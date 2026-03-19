import json
import time
from io import BytesIO

import numpy as np
import RPi.GPIO as GPIO
import smbus  # I2C
import spidev  # SPI
import zmq
from PIL import Image

from UV_projector.controller import DLPC1438, Mode


def decode_image_to_projector_array(raw_image_bytes):
    image = Image.open(BytesIO(raw_image_bytes)).convert("L")
    return np.transpose(np.asarray(image, dtype=np.uint8))


def parse_proj_time(data, default=1.0):
    try:
        return max(float(data.get("proj_time", default)), 0.0)
    except (TypeError, ValueError):
        return default


context = zmq.Context()
recv_socket = context.socket(zmq.PULL)
recv_socket.bind("tcp://*:5555")
send_socket = context.socket(zmq.PUSH)
send_socket.connect("tcp://10.81.83.127:5556")

poller = zmq.Poller()
poller.register(recv_socket, zmq.POLLIN)

GPIO.setmode(GPIO.BCM)

DMD = None
exposure_active = False
quitting = False

# At most one staged frame is kept. If a newer one arrives before swap, it replaces older staged data.
pending_duration = None
current_deadline = None
prev_time = time.monotonic()

try:
    i2c = smbus.SMBus(1)
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 125000000
    spi.mode = 3

    DMD = DLPC1438(i2c, spi)
    mode = i2c.read_i2c_block_data(DMD.addr, 0x06, 1)
    print(f"we are in mode: {mode}")

    DMD.configure_external_print(LED_PWM=1000)
    DMD.switch_mode(Mode.EXTERNALPRINT)
    DMD.set_background(intensity=0, both_buffers=True)

    while not quitting:
        events = dict(poller.poll(timeout=20))
        if recv_socket in events:
            while True:
                try:
                    parts = recv_socket.recv_multipart(flags=zmq.NOBLOCK)
                except zmq.Again:
                    break

                msg_text = parts[0].decode()
                data = json.loads(msg_text)
                action = data.get("action")
                image_flag = data.get("image")

                if action == "quit":
                    quitting = True
                    break

                if action != "illum" or not image_flag:
                    print(f"Ignoring unsupported message: action={action}, image={image_flag}")
                    continue

                if len(parts) < 2:
                    print("Ignoring illum message with no image payload.")
                    continue

                proj_time = parse_proj_time(data)
                img_array = decode_image_to_projector_array(parts[1])
                DMD.send_pixeldata_to_buffer(img_array, 0, 0)
                pending_duration = proj_time

                if not exposure_active:
                    DMD.swap_buffer()
                    print("New exposure", time.monotonic()-prev_time)
                    prev_time = time.monotonic()
                    DMD.expose_pattern(exposed_frames=-1, dark_frames=0)
                    exposure_active = True
                    current_deadline = time.monotonic() + pending_duration
                    pending_duration = None

        now = time.monotonic()
        if exposure_active and current_deadline is not None and now >= current_deadline:
            if pending_duration is not None:
                DMD.swap_buffer()
                print("New frame", time.monotonic()-prev_time)
                prev_time = time.monotonic()
                current_deadline = current_deadline + pending_duration
                pending_duration = None
                send_socket.send_string("done")
            else:
                DMD.stop_exposure()
                exposure_active = False
                current_deadline = None
                send_socket.send_string("done")

    if exposure_active:
        DMD.stop_exposure()
        exposure_active = False

    DMD.switch_mode(Mode.STANDBY)

except KeyboardInterrupt:
    pass
finally:
    if DMD is not None and exposure_active:
        DMD.stop_exposure()
    if DMD is not None:
        try:
            DMD.switch_mode(Mode.STANDBY)
        except Exception:
            pass
    recv_socket.close(0)
    send_socket.close(0)
    context.term()
    GPIO.cleanup()
