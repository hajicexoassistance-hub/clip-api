
import requests
import time
import json
import os
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
# We don't need a real API key since it's disabled for testing, but we'll try to find it
API_KEY = "any_key" 
VIDEO_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ" # Big Buck Bunny on YouTube

def log(m):
    print(f"[*] {m}", flush=True)

def test_workflow():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # 1. DOWNLOAD
    log(f"Phase 1: Requesting download for {VIDEO_URL}")
    resp = requests.post(f"{BASE_URL}/download", json={"url": VIDEO_URL}, headers=headers)
    if resp.status_code != 200:
        log(f"Download request failed: {resp.text}")
        return
    
    job_id = resp.json()["job_id"]
    log(f"Job ID: {job_id}")
    
    # 2. POLL DOWNLOAD (Stage 1)
    log("Polling Stage 1 progress...")
    while True:
        r = requests.get(f"{BASE_URL}/job/{job_id}", headers=headers)
        status = r.json()
        prog = status.get("progress_percent", 0)
        curr_status = status.get("status", "unknown")
        log(f"Progress: {prog}% | Status: {curr_status}")
        
        if curr_status == "completed":
            log("Stage 1 Completed!")
            break
        if curr_status == "failed":
            log(f"Stage 1 Failed: {status.get('error_message')}")
            return
        time.sleep(5)

    # 3. Wait for Auto-Sequencer
    log("Waiting for Auto-Sequencer to start rendering clips...")
    # The auto-sequencer starts after Stage 1. We poll and check for analysis_jobs.
    # Since the API doesn't have a direct 'list all clips for job' endpoint yet in the results, 
    # we can check /job/{job_id}/results (which I recall exists in app.py)
    
    for _ in range(60): # 5 minutes max
        r = requests.get(f"{BASE_URL}/job/{job_id}/results", headers=headers)
        if r.status_code == 200:
            data = r.json()
            clips = data.get("clips", [])
            if clips and len(clips) > 0:
                log(f"Found {len(clips)} clips in progress/completed.")
                # Look for at least one 'completed'
                completed = [c for c in clips if c.get('status') == 'completed']
                if completed:
                    log("SUCCESS: At least one clip completed!")
                    log(json.dumps(completed, indent=2))
                    return
                
                # Check for failure in clips
                failed = [c for c in clips if c.get('status') == 'failed']
                if failed:
                    log("ERROR: One or more clips failed.")
                    log(json.dumps(failed, indent=2))
                    return
            else:
                log("No clips found yet, waiting...")
        
        # Also check main job status
        r_job = requests.get(f"{BASE_URL}/job/{job_id}", headers=headers)
        if r_job.json().get("status") == "failed":
             log(f"Job Failed later: {r_job.json().get('error_message')}")
             return

        time.sleep(10)

if __name__ == "__main__":
    test_workflow()
