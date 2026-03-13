
import requests
import time
import json
import sys

BASE_URL = "http://rdp.hajicexo.my.id" # Or local if running there
# Since I am running ON the machine, I'll use localhost for reliability
BASE_URL = "http://localhost:8000"
API_KEY = "test"
VIDEO_URL = "https://www.youtube.com/watch?v=nfuEPpY9b6c"

def log(m):
    print(f"[*] {m}")

def test_workflow():
    headers = {"X-API-Key": API_KEY}
    
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
        time.sleep(10)

    # 3. ANALYZE
    log("Phase 3: Requesting Analysis")
    resp = requests.get(f"{BASE_URL}/analyze", params={"job_id": job_id}, headers=headers)
    if resp.status_code != 200:
        log(f"Analyze request failed: {resp.text}")
        return
    log("Analyze started (background)")

    # Analysis is usually fast since Stage 1 already transcribed it.
    # We poll the results endpoint to see when it's ready.
    log("Waiting for analysis result...")
    analysis_data = None
    for _ in range(30):
        # We check the jobs table or just wait for analysis.json to be readable by the server
        # Actually /analyze in current app.py returns immediately, but the pipeline already saved analysis.json
        # Wait, app.py /analyze actually returns the topics? Let's check.
        # Looking at app.py: it calls analyze_srt and returns results. 
        # But wait, it's NOT a background task in the code I saw earlier? 
        # Line 332: def analyze_job(background_tasks: BackgroundTasks, job_id: str = Query(...)):
        # It calls analyze_srt(job_id, srt_path) directly and returns.
        if resp.status_code == 200:
            analysis_data = resp.json()
            break
        time.sleep(5)
    
    if not analysis_data or "topics" not in analysis_data:
        log("No topics found in analysis")
        return
    
    log(f"Found {len(analysis_data['topics'])} topics.")
    first_topic_idx = analysis_data["topics"][0]["id"]
    log(f"Selecting first topic (Index {first_topic_idx}): {analysis_data['topics'][0]['topic']}")

    # 4. CLIP
    log("Phase 4: Requesting Clip")
    resp = requests.post(f"{BASE_URL}/clip", json={"job_id": job_id, "topics": [first_topic_idx]}, headers=headers)
    if resp.status_code != 200:
        log(f"Clip request failed: {resp.text}")
        return
    
    log("Clip rendering started...")
    
    # 5. POLL CLIP RESULTS
    log("Polling for final clip results...")
    while True:
        r = requests.get(f"{BASE_URL}/job/{job_id}/results", headers=headers)
        if r.status_code == 200:
            results = r.json()
            if results:
                log("CLIP SUCCESS!")
                log(json.dumps(results, indent=2))
                break
        
        # Also check pipeline status for errors
        r2 = requests.get(f"{BASE_URL}/job/{job_id}", headers=headers)
        if r2.json().get("status") == "failed":
            log(f"Clipping Failed: {r2.json().get('error_message')}")
            break
            
        time.sleep(10)

if __name__ == "__main__":
    test_workflow()
