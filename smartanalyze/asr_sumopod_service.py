"""
ASRService for Sumopod Whisper-compatible API
"""
import requests
import os
from dotenv import load_dotenv

class ASRService:
    def __init__(self, api_key=None, api_url=None, model=None):
        # Load from .env if not provided
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
        self.api_key = api_key or os.getenv("SUMOPOD_API_KEY")
        self.api_url = (api_url or os.getenv("SUMOPOD_API_URL") or "https://ai.sumopod.com/v1").rstrip("/")
        self.model = model or os.getenv("SUMOPOD_MODEL") or "whisper-1"

    def transcribe(self, audio_path, response_format="verbose_json"):
        url = f"{self.api_url}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {
            "file": (os.path.basename(audio_path), open(audio_path, "rb"), "audio/mpeg"),
        }
        data = {
            "model": self.model,
            "response_format": response_format
        }
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json()

    def get_word_timings(self, asr_result):
        """
        Convert verbose_json result to word-level timings for subtitle_service.generate_ass
        Returns: list of dicts: [{"start": str, "end": str, "text": str}]
        """
        segments = asr_result.get("segments", [])
        word_timings = []
        for seg in segments:
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            text = seg.get("text", "").strip()
            # Optionally split by word for finer granularity
            words = text.split()
            if not words:
                continue
            # Distribute segment time equally to words
            dur = (end - start) / max(1, len(words))
            for i, w in enumerate(words):
                w_start = start + i * dur
                w_end = w_start + dur
                # Format as ASS timestamp (h:mm:ss.xx)
                def fmt(ts):
                    h = int(ts // 3600)
                    m = int((ts % 3600) // 60)
                    s = ts % 60
                    return f"{h}:{m:02}:{s:05.2f}"
                word_timings.append({
                    "start": fmt(w_start),
                    "end": fmt(w_end),
                    "text": w
                })
        return word_timings
