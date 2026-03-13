import urllib.request

def ensure_yolo_model():
    model_path = os.path.join(os.path.dirname(__file__), "models", "yolov8n.pt")
    if os.path.exists(model_path):
        print("Model YOLOv8n sudah tersedia.")
        return model_path
    url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
    print("Mengunduh model YOLOv8n...")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    urllib.request.urlretrieve(url, model_path)
    print("Model YOLOv8n berhasil diunduh.")
    return model_path
"""
Main pipeline for landscape to portrait smart crop video converter.
"""


import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import config
import scene_detect
import subject_detect
import crop_calc
import ffmpeg_builder
import utils
import subprocess
import sys
import os



from filter_presets import get_available_filters

def main():
    if len(sys.argv) < 3:
        print("Usage: python main.py <input_video> <output_video> [filter_preset]")
        print("Available filter presets:", ', '.join(get_available_filters()))
        return
    input_video = sys.argv[1]
    output_video = sys.argv[2]
    filter_preset = sys.argv[3] if len(sys.argv) > 3 else None

    # Pastikan model YOLOv8n tersedia
    ensure_yolo_model()

    # 1. Scene detection
    scenes = scene_detect.detect_scenes(input_video, threshold=config.SCENE_THRESHOLD)
    print(f"Detected {len(scenes)} scenes.")

    # 2. For each scene, ambil frame tengah, detect subject, hitung crop
    import cv2
    cap = cv2.VideoCapture(input_video)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    # Hitung crop width minimum dari semua scene
    temp_scene_data = []
    for start, end in scenes:
        mid = (start + end) / 2
        frame = utils.get_frame(input_video, mid)
        if frame is None:
            print(f"Warning: failed to get frame at {mid}s")
            continue
        center_x = subject_detect.detect_subject(frame)
        if center_x is None:
            center_x = width // 2  # fallback: center crop
        x, crop_w = crop_calc.calc_crop(center_x, width, height)
        temp_scene_data.append((start, end, x, crop_w))

    min_crop_w = min([d[3] for d in temp_scene_data])
    # Paksa width crop minimum menjadi genap
    if min_crop_w % 2 != 0:
        min_crop_w -= 1
    # Paksa semua crop width = min_crop_w (genap)
    scene_data = []
    for start, end, x, crop_w in temp_scene_data:
        # Rehitung x agar crop tetap center
        new_x = max(0, min(x + (crop_w - min_crop_w) // 2, width - min_crop_w))
        scene_data.append((start, end, new_x, min_crop_w))

    # 3. Build ffmpeg filter
    filter_str = ffmpeg_builder.build_filter(scene_data, height, filter_preset)

    # 4. Render video (dengan audio)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_video,
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "128k",
        "-preset", "veryfast",
        output_video
    ]
    print("Running FFmpeg...")
    subprocess.run(cmd)
    print(f"Done. Output: {output_video}")

if __name__ == "__main__":
    main()
