"""
Scene detection using PySceneDetect.
"""
from scenedetect import detect, ContentDetector

def detect_scenes(video_path, threshold=30):
    """Detect scenes in a video file with robust error handling."""
    try:
        scenes = detect(video_path, ContentDetector(threshold=threshold))
        result = []
        for s in scenes:
            start = s[0].get_seconds()
            end = s[1].get_seconds()
            result.append((start, end))
        
        if not result:
            return []
        return result
    except Exception as e:
        # Fallback to empty list so caller can handle with duration
        print(f"Warning: Scene detection failed: {e}")
        return []
