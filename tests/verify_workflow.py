import requests
import time
import json
import sys

BASE_URL = "https://rdp.hajicexo.my.id"
# BASE_URL = "http://localhost:8000" # For local testing if needed

def test_workflow():
    print(f"Testing workflow on {BASE_URL}...")
    
    # 1. Download
    video_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ" # Use a known short video if possible
    print(f"Submitting download for: {video_url}")
    try:
        resp = requests.post(f"{BASE_URL}/download", json={"url": video_url, "preset": "default"}, timeout=30)
        resp.raise_for_status()
        job_data = resp.json()
        job_id = job_data["job_id"]
        print(f"Job created: {job_id}")
    except Exception as e:
        print(f"Download request failed: {e}")
        return

    # 2. Poll Status
    print("Waiting for Stage 1 (Download & Analyze) to complete...")
    max_retries = 60
    for i in range(max_retries):
        try:
            resp = requests.get(f"{BASE_URL}/job/{job_id}", timeout=10)
            resp.raise_for_status()
            status_data = resp.json()
            status = status_data["status"]
            progress = status_data.get("progress_percent", 0)
            print(f"Status: {status} ({progress}%)")
            
            if status == "completed":
                print("Stage 1 completed successfully.")
                break
            elif status == "failed":
                print(f"Job failed: {status_data.get('error_message')}")
                return
        except Exception as e:
            print(f"Error checking status: {e}")
        
        time.sleep(10)
    else:
        print("Timeout waiting for Stage 1")
        return

    # 3. Analyze
    print(f"Testing /analyze for job: {job_id}")
    try:
        resp = requests.get(f"{BASE_URL}/analyze?job_id={job_id}", timeout=30)
        resp.raise_for_status()
        analysis_data = resp.json()
        print("Analysis successful.")
        
        # In this API, /analyze starts a background task if not cached. 
        # But if Stage 1 is 'completed', it might already be cached or ready.
        if analysis_data.get("status") == "processing":
             print("Analysis is processing in background, waiting...")
             time.sleep(10)
             # Poll again
             resp = requests.get(f"{BASE_URL}/analyze?job_id={job_id}", timeout=30)
             analysis_data = resp.json()
        
        topics = analysis_data.get("topics", [])
        if not topics:
            print("No topics found in analysis.")
            return
        print(f"Found {len(topics)} topics.")
    except Exception as e:
        print(f"Analyze failed: {e}")
        return

    # 4. Clip
    print(f"Requesting clip for job {job_id}, topic index 0")
    try:
        resp = requests.post(f"{BASE_URL}/clip", json={"job_id": job_id, "topics": [0]}, timeout=30)
        resp.raise_for_status()
        clip_data = resp.json()
        clip_id = clip_data["clip_id"]
        print(f"Clip requested: {clip_id}")
    except Exception as e:
        print(f"Clip request failed: {e}")
        return

    # 5. Poll Clip Status
    print("Waiting for Stage 2 (Clipping) to complete...")
    for i in range(30):
        try:
            resp = requests.get(f"{BASE_URL}/clip/{clip_id}", timeout=10)
            resp.raise_for_status()
            clip_status_data = resp.json()
            status = clip_status_data["status"]
            print(f"Clip Status: {status}")
            
            if status == "completed":
                print(f"Clip completed! URL: {clip_status_data.get('url')}")
                print("All endpoints tested successfully.")
                break
            elif status == "failed":
                print(f"Clip failed: {clip_status_data.get('error')}")
                return
        except Exception as e:
            print(f"Error checking clip status: {e}")
        
        time.sleep(10)
    else:
        print("Timeout waiting for Stage 2")
        return

if __name__ == "__main__":
    test_workflow()
