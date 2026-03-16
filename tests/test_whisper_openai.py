try:
    print("Testing openai-whisper import...")
    import whisper
    print("Whisper import successful!")
    model = whisper.load_model("tiny")
    print("Model loaded successfully!")
except Exception as e:
    print(f"Whisper import FAILED: {e}")
    import traceback
    traceback.print_exc()
