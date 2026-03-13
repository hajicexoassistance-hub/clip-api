import requests
import json

BASE_URL = "http://localhost:8000"

def verify_clip_status_endpoint():
    print(f"Verifying /job/{{job_id}}/clip-status on {BASE_URL}...")
    
    # Get the last job ID
    try:
        resp = requests.get(f"{BASE_URL}/jobs?limit=1")
        resp.raise_for_status()
        jobs = resp.json()
        if not jobs:
            print("No jobs found to test with.")
            return
        job_id = jobs[0]["job_id"]
        print(f"Using job_id: {job_id}")
    except Exception as e:
        print(f"Failed to get job ID: {e}")
        return

    # Test the new endpoint
    try:
        resp = requests.get(f"{BASE_URL}/job/{job_id}/clip-status")
        resp.raise_for_status()
        data = resp.json()
        print("\nEndpoint Response Check:")
        print(json.dumps(data, indent=2))
        
        # Verify required fields
        required_fields = ["job_id", "stage1_status", "total_topics", "completed", "failed", "rendering", "is_finished", "clips"]
        for field in required_fields:
            if field in data:
                print(f"  [OK] Field '{field}' exists.")
            else:
                print(f"  [FAIL] Field '{field}' is missing!")
                
    except Exception as e:
        print(f"Endpoint test failed: {e}")

if __name__ == "__main__":
    verify_clip_status_endpoint()
