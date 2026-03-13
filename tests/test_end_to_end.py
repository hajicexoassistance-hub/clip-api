import requests
import time

API_URL = "http://localhost:8000"
VIDEO_URL = "https://www.youtube.com/watch?v=aPySstYrxtg"
PRESET = "default"

def submit_job():
    resp = requests.get(f"{API_URL}/download", params={"url": VIDEO_URL, "preset": PRESET})
    resp.raise_for_status()
    data = resp.json()
    print("Job submitted:", data)
    return data["job_id"]

def poll_job(job_id):
    while True:
        resp = requests.get(f"{API_URL}/job/{job_id}")
        resp.raise_for_status()
        data = resp.json()
        print("Job status:", data["status"], "progress:", data["progress_percent"])
        if data["status"] in ("completed", "failed", "error"):
            return data
        time.sleep(5)

def download_result(result_url, out_path):
    if not result_url:
        print("No result URL available.")
        return
    r = requests.get(result_url)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    print(f"Downloaded result to {out_path}")

if __name__ == "__main__":
    job_id = submit_job()
    result = poll_job(job_id)
    if result["status"] == "completed" and result["result_url"]:
        download_result(result["result_url"], f"output_{job_id}.mp4")
    else:
        print("Job did not complete successfully.")
