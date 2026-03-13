import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_endpoints():
    print(f"Testing endpoints on {BASE_URL}...")
    
    # 1. Test /jobs (should be empty after reset)
    print("\n[1] Testing /jobs...")
    try:
        resp = requests.get(f"{BASE_URL}/jobs")
        resp.raise_for_status()
        jobs = resp.json()
        print(f"SUCCESS: Found {len(jobs)} jobs.")
    except Exception as e:
        print(f"FAILED: {e}")

    # 2. Test /download
    video_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
    print(f"\n[2] Testing /download for {video_url}...")
    try:
        resp = requests.post(f"{BASE_URL}/download", json={"url": video_url, "preset": "default"})
        resp.raise_for_status()
        job_data = resp.json()
        job_id = job_data["job_id"]
        print(f"SUCCESS: Job created with ID: {job_id}")
    except Exception as e:
        print(f"FAILED: {e}")
        return

    # 3. Test /job/{id}
    print(f"\n[3] Testing /job/{job_id}...")
    try:
        resp = requests.get(f"{BASE_URL}/job/{job_id}")
        resp.raise_for_status()
        status_data = resp.json()
        print(f"SUCCESS: Job status: {status_data['status']}")
    except Exception as e:
        print(f"FAILED: {e}")

    # 4. Test /job/by-url
    print(f"\n[4] Testing /job/by-url for {video_url}...")
    try:
        resp = requests.get(f"{BASE_URL}/job/by-url", params={"url": video_url})
        resp.raise_for_status()
        url_job_data = resp.json()
        print(f"SUCCESS: Found job ID {url_job_data['job_id']} for URL.")
    except Exception as e:
        print(f"FAILED: {e}")

    # 5. Wait for Stage 1 to complete (limited wait for test)
    print("\n[5] Waiting for Stage 1 (Download & Analyze) to complete (max 2 mins)...")
    start_time = time.time()
    completed = False
    while time.time() - start_time < 120:
        resp = requests.get(f"{BASE_URL}/job/{job_id}")
        status_data = resp.json()
        status = status_data["status"]
        progress = status_data.get("progress_percent", 0)
        print(f"Status: {status} ({progress}%)")
        if status == "completed":
            completed = True
            break
        elif status == "failed":
            print(f"Job failed: {status_data.get('error_message')}")
            break
        time.sleep(10)
    
    if not completed:
        print("Stage 1 didn't complete in time, but endpoint response was verified.")
        return

    # 6. Test /analyze
    print(f"\n[6] Testing /analyze for job {job_id}...")
    try:
        resp = requests.get(f"{BASE_URL}/analyze", params={"job_id": job_id})
        resp.raise_for_status()
        analysis_data = resp.json()
        print("SUCCESS: Analysis data retrieved.")
        topics = analysis_data.get("topics", [])
        print(f"Found {len(topics)} topics.")
    except Exception as e:
        print(f"FAILED: {e}")
        return

    if not topics:
        print("No topics found, cannot test /clip.")
        return

    # 7. Test /clip
    print(f"\n[7] Testing /clip for job {job_id}, topic 0...")
    try:
        resp = requests.post(f"{BASE_URL}/clip", json={"job_id": job_id, "topics": [0]})
        resp.raise_for_status()
        clip_data = resp.json()
        clip_id = clip_data["clip_id"]
        print(f"SUCCESS: Clip requested with ID: {clip_id}")
    except Exception as e:
        print(f"FAILED: {e}")
        return

    # 8. Test /clip/{id}
    print(f"\n[8] Testing /clip/{clip_id}...")
    try:
        resp = requests.get(f"{BASE_URL}/clip/{clip_id}")
        resp.raise_for_status()
        clip_status_data = resp.json()
        print(f"SUCCESS: Clip status: {clip_status_data['status']}")
    except Exception as e:
        print(f"FAILED: {e}")

    # 9. Test /api/logs
    print("\n[9] Testing /api/logs...")
    try:
        resp = requests.get(f"{BASE_URL}/api/logs", params={"lines": 10})
        resp.raise_for_status()
        logs_data = resp.json()
        print(f"SUCCESS: Retrieved {len(logs_data.get('logs', []))} log lines.")
    except Exception as e:
        print(f"FAILED: {e}")

    print("\nEndpoint testing finished.")

if __name__ == "__main__":
    test_endpoints()
