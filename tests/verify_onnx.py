import cv2
import numpy as np
from smartcrop.subject_detect import detect_subject
import os

def test_detection():
    # Create a dummy frame with a white rectangle representing a person
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # A "person-like" rectangle at x=300
    cv2.rectangle(frame, (250, 200), (350, 600), (255, 255, 255), -1)
    
    # Also test with a real frame if possible
    video_path = r"output\42c933f2-ef50-4176-8467-0f0c25803aa0\rawvideo.mp4"
    if os.path.exists(video_path):
        cap = cv2.VideoCapture(video_path)
        ret, real_frame = cap.read()
        cap.release()
        if ret:
            print("Testing on REAL frame from video...")
            res = detect_subject(real_frame)
            print(f"Result (Real Frame): {res}")
    
    print("Testing on DUMMY frame...")
    res = detect_subject(frame)
    print(f"Result (Dummy Frame): {res}")

if __name__ == "__main__":
    test_detection()
