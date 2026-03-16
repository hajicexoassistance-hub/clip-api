try:
    print("Testing torch import...")
    import torch
    print(f"Torch version: {torch.__version__}")
    print("Torch import successful!")
except Exception as e:
    print(f"Torch import FAILED: {e}")
    import traceback
    traceback.print_exc()
