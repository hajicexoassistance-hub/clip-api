import sys
import os
import subprocess

def download_video(url, output_path):
    cmd = [
        "yt-dlp",
        "-f", "bestvideo+bestaudio/best",
        "-o", output_path,
        url
    ]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python download_ytdlp.py <video_url> <output_path>")
        sys.exit(1)
    download_video(sys.argv[1], sys.argv[2])
