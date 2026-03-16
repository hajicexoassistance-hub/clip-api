import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Fix path to include the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env explicitly to ensure credentials are available
load_dotenv()

from smartcrop.storage_service import get_storage_service

def test_r2_upload():
    test_file = Path("test_upload.txt")
    test_file.write_text("This is a test upload to Cloudflare R2.")
    
    print("--- Starting R2 Upload Test ---")
    try:
        storage = get_storage_service()
        if not storage.client:
            print("FAILED: R2 Client not initialized. Check .env")
            return

        remote_path = "tests/test_upload.txt"
        url = storage.upload_file(str(test_file), remote_path)
        print(f"SUCCESS: Uploaded to {url}")
        
        # Cleanup local test file
        test_file.unlink()
        print("Local test file cleaned up.")
    except Exception as e:
        print(f"FAILED: R2 Test failed with error: {e}")

if __name__ == "__main__":
    test_r2_upload()
