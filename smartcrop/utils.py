"""
Utility functions for video frame extraction.
"""
import cv2

def get_frame(video, time):
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
    ret, frame = cap.read()
    cap.release()
    return frame
