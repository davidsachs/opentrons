import zmq
import cv2
import json
import numpy as np
import time
import threading
import queue


class RobotSocket:
    def __init__(self, host="localhost"):
        self.context = zmq.Context()

        # Image socket - SUB to match C++ PUB on port 5557
        self.image_socket = self.context.socket(zmq.SUB)
        self.image_socket.setsockopt(zmq.CONFLATE, 1)
        self.image_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.image_socket.connect(f"tcp://{host}:5557")

        # Data socket - SUB to match C++ PUB on port 5558
        # Sends JSON: {"x": ..., "y": ..., "z": ...}
        self.data_socket = self.context.socket(zmq.SUB)
        self.data_socket.setsockopt(zmq.CONFLATE, 1)
        self.data_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.data_socket.connect(f"tcp://{host}:5558")

        # Command socket - PUSH to match C++ PULL on port 5559
        self.cmd_socket = self.context.socket(zmq.PUSH)
        self.cmd_socket.connect(f"tcp://{host}:5559")

        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}

    def get_obs(self):
        """Get latest image and position from the microscope.

        Blocks until the next JPEG frame arrives.
        Non-blocking poll for position data (uses last known if none available).

        Returns:
            image: numpy array (H, W, 3) BGR uint8
            position: dict with "x", "y", "z" floats (mm)
        """
        # Block on next image frame
        jpg_bytes = self.image_socket.recv()
        image = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

        # Non-blocking poll for latest position
        try:
            data = self.data_socket.recv(flags=zmq.DONTWAIT)
            self.position = json.loads(data.decode("utf-8"))
        except zmq.Again:
            pass

        return image, dict(self.position)

    def send_action(self, action):
        """Send an action to the robot as X/Y/Z move commands.

        Args:
            action: array-like with 3 elements [x_mm, y_mm, z_mm]
        """
        x, y, z = float(action[0]), float(action[1]), float(action[2])
        cmd = f"X{x:.4f} Y{y:.4f} Z{z:.4f}\n"
        self.cmd_socket.send_string(cmd)

    def send_command(self, cmd):
        """Send a raw command string (e.g. 'HX', 'GO4', 'X5')."""
        if not cmd.endswith("\n"):
            cmd += "\n"
        self.cmd_socket.send_string(cmd)

    def close(self):
        self.image_socket.close()
        self.data_socket.close()
        self.cmd_socket.close()
        self.context.term()


if __name__ == '__main__':
    robot = RobotSocket()

    diag_start = time.time()
    diag_frames = 0

    cmd_queue = queue.Queue()

    def input_thread():
        while True:
            cmd = input("Enter command: ")
            cmd_queue.put(cmd)
            if cmd.lower() == "quit":
                break
    threading.Thread(target=input_thread, daemon=True).start()

    while True:
        image, position = robot.get_obs()
        diag_frames += 1

        if image is not None:
            cv2.imshow("Video Stream", image)

        # Exit if esc pressed
        if cv2.waitKey(1) & 0xFF == 27:
            break

        # Process any commands
        while not cmd_queue.empty():
            cmd = cmd_queue.get().upper()
            print("Command received:", cmd)
            robot.send_command(cmd)
            if cmd == "QUIT":
                break

        # Print FPS every 2 seconds
        now = time.time()
        diag_elapsed = now - diag_start
        if diag_elapsed >= 2.0:
            print(f"[ZMQ] FPS: {diag_frames/diag_elapsed:.2f}  pos: {position}")
            diag_start = now
            diag_frames = 0

    robot.close()
    cv2.destroyAllWindows()
