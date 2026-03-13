import sys
import os
import subprocess

def extract_audio(input_video, output_audio):
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", output_audio
    ]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_audio.py <input_video> <output_audio>")
        sys.exit(1)
    extract_audio(sys.argv[1], sys.argv[2])
