import os
import shutil
from pathlib import Path

def reset_environment():
    print("Resetting environment...")
    
    # 1. Database
    db_path = Path("data/job_history.db")
    if db_path.exists():
        print(f"Deleting database: {db_path}")
        db_path.unlink()
    
    # 2. Logs
    log_path = Path("data/pipeline.log")
    if log_path.exists():
        print(f"Deleting logs: {log_path}")
        log_path.unlink()
        
    # 3. Data subdirectories (like test-job-123)
    data_dir = Path("data")
    if data_dir.exists():
        for item in data_dir.iterdir():
            if item.is_dir():
                print(f"Deleting data subdirectory: {item}")
                shutil.rmtree(item)

    # 4. Output files
    output_dir = Path("output")
    if output_dir.exists():
        print(f"Cleaning output directory: {output_dir}")
        for item in output_dir.iterdir():
            if item.is_dir():
                print(f"Deleting job directory: {item}")
                shutil.rmtree(item)
            else:
                print(f"Deleting file: {item}")
                item.unlink()
    else:
        output_dir.mkdir(exist_ok=True)
                
    print("Environment reset complete.")

if __name__ == "__main__":
    reset_environment()
