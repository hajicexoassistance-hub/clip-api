
import os
import time
from pathlib import Path

DB_PATH = os.environ.get('PORTRAITGEN_DB_PATH', 'data/job_history.db')
DATA_DIR = os.path.dirname(DB_PATH) or '.'
LOG_FILE = os.path.join(DATA_DIR, 'pipeline.log')

def log_event(msg):
    from datetime import datetime
    print(f"[DEBUG] {msg}")

def cleanup_expired_files(output_dir, expire_days=1):
    print(f"Testing cleanup for {output_dir}...")
    if not os.path.exists(output_dir):
        print("Dir does not exist")
        return
    
    cutoff = time.time() - (expire_days * 86400)
    try:
        print("Calling os.listdir...")
        files = os.listdir(output_dir)
        print(f"Found {len(files)} items")
        for filename in files:
            file_path = os.path.join(output_dir, filename)
            print(f"Checking {file_path}")
            if os.path.isfile(file_path):
                mtime = os.path.getmtime(file_path)
                print(f"Mtime: {mtime}, Cutoff: {cutoff}")
            elif os.path.isdir(file_path):
                print(f"Is directory: {file_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    cleanup_expired_files("output")
