import os
import time
from pathlib import Path
from faster_whisper import WhisperModel

class LocalWhisperService:
    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LocalWhisperService, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_size=None, device=None, compute_type=None):
        if self._model is not None:
            return

        self.model_size = model_size or os.environ.get('PORTRAITGEN_WHISPER_MODEL', 'medium')
        self.device = device or os.environ.get('PORTRAITGEN_WHISPER_DEVICE', 'cpu')
        self.compute_type = compute_type or os.environ.get('PORTRAITGEN_WHISPER_COMPUTE', 'int8')
        
        print(f"[WHISPER] Initializing Local Faster-Whisper Model: {self.model_size} on {self.device} ({self.compute_type})")
        start_time = time.time()
        # This will download the model on first use
        self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        print(f"[WHISPER] Model loaded in {time.time() - start_time:.2f}s")

    def transcribe(self, audio_path, output_srt_path):
        """
        Transcribe audio to SRT format using local faster-whisper.
        """
        print(f"[WHISPER] Transcribing {audio_path}...")
        start_time = time.time()
        
        segments, info = self._model.transcribe(str(audio_path), beam_size=5)
        
        # Generator to list for processing
        segments = list(segments)
        
        with open(output_srt_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                start = self._format_timestamp(segment.start)
                end = self._format_timestamp(segment.end)
                f.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")
        
        print(f"[WHISPER] Transcription complete in {time.time() - start_time:.2f}s. Language: {info.language}")
        return output_srt_path

    def _format_timestamp(self, seconds):
        milliseconds = int((seconds - int(seconds)) * 1000)
        seconds = int(seconds)
        minutes = seconds // 60
        hours = minutes // 60
        minutes = minutes % 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def get_whisper_service():
    # Defensive import/init to allow fallback in pipeline if something fails
    try:
        return LocalWhisperService()
    except Exception as e:
        print(f"[WHISPER] Failed to initialize Faster-Whisper: {e}")
        raise
