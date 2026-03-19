import cv2
import zmq
import numpy as np
import time

# --- CONFIGURATION ---
SENDER_IP = "127.0.0.1" # Change to '192.168.X.X' if on another PC
PORT = 5555

def receiver():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    
    # --- THE MAGIC FLAGS ---
    # CONFLATE=1: "Keep only the LAST message in the buffer"
    # This guarantees that whenever we ask for data, we get the absolute newest frame.
    # We never process old data. This eliminates "lag" entirely.
    socket.setsockopt(zmq.CONFLATE, 1)
    
    socket.connect(f"tcp://{SENDER_IP}:{PORT}")
    socket.subscribe(b'') # Subscribe to all topics

    print(f"Listening on {SENDER_IP}:{PORT}...")
    print("Waiting for stream...")

    window_name = "Receiver (Zero Latency)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            # 1. Receive Data (Blocking, but instant due to CONFLATE)
            jpg_buffer = socket.recv()
            
            # 2. Decode JPEG
            # frombuffer is zero-copy, very fast
            np_arr = np.frombuffer(jpg_buffer, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                # Latency Check
                cv2.putText(frame, f"REC: {time.time():.2f}", (50, 200), 
                            cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 4)
                
                cv2.imshow(window_name, frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        pass
    finally:
        socket.close()
        context.term()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    receiver()