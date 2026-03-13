"""
Configuration for smart crop app.
"""

SCENE_THRESHOLD = 30
TARGET_RATIO_W = 9
TARGET_RATIO_H = 16
YOLO_MODEL = "models/yolov8n.pt"
PRIORITY_CLASSES = [
    "person",
    "dog",
    "cat",
    "car"
]
