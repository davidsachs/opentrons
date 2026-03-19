import cv2
import zmq
import numpy as np
import time

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1280, 960
PORT = 5555

def sender():
    # 1. Setup ZeroMQ (The "Pro" Telemetry Layer)
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    # TCP is perfectly fine for LAN/Localhost latency when using CONFLATE
    socket.bind(f"tcp://*:{PORT}") 
    
    print(f"Streaming Telemetry at {WIDTH}x{HEIGHT} on port {PORT}...")

    # Physics (Bouncing Ball)
    x, y = WIDTH // 2, HEIGHT // 2
    dx, dy = 15, 15

    try:
        while True:
            # 2. Generate Frame
            frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
            
            x += dx; y += dy
            if x <= 20 or x >= WIDTH-20: dx = -dx
            if y <= 20 or y >= HEIGHT-20: dy = -dy
            
            # Visuals
            cv2.circle(frame, (x, y), 20, (0, 0, 255), -1)
            cv2.putText(frame, f"SEND: {time.time():.2f}", (50, 100), 
                        cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 4)
            
            # 3. Compress to JPEG (The "Compression" Requirement)
            # Quality 50-70 is the sweet spot for speed vs looks.
            ret, jpg_buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            
            # 4. Send instantly
            # We send the raw JPEG bytes. No headers, no handshakes.
            socket.send(jpg_buffer)

            # Local preview
            cv2.imshow("Sender (ZMQ)", frame)
            
            # Cap at ~30 FPS
            if cv2.waitKey(30) & 0xFF == ord('q'):
                break
                
    finally:
        socket.close()
        context.term()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    sender()