import os
import sys
from pathlib import Path

# Fix path
sys.path.insert(0, str(Path(__file__).parent.parent))

from smartcrop.local_whisper import get_whisper_service

def test_transcription():
    audio_path = Path("test_audio.mp3")
    output_srt = Path("test_output.srt")
    
    # Create a dummy silent audio if it doesn't exist for a basic smoke test
    if not audio_path.exists():
        import subprocess
        print("Creating dummy audio for test...")
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono:d=5', '-c:a', 'libmp3lame', str(audio_path)], check=True)

    print("--- Starting Local Whisper Test ---")
    service = get_whisper_service()
    service.transcribe(audio_path, output_srt)
    
    if output_srt.exists():
        print(f"SUCCESS: SRT generated at {output_srt}")
        with open(output_srt, 'r') as f:
            print("Content preview:")
            print(f.read()[:200])
    else:
        print("FAILED: SRT not generated")

if __name__ == "__main__":
    test_transcription()
