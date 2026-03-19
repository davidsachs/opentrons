import cv2

# The URL you used in Chrome
URL = "http://10.90.158.110:8080/stream.mjpg"
cap = cv2.VideoCapture(URL)

while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow('Flex Feed', frame)
    
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()