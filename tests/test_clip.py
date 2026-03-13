#!/usr/bin/env python3
import urllib.request
import json

url = "http://localhost:8000/clip?api_key=pga_live_7d9f4b2c8e6a412cba89f3c1d2e4a5b6"
payload = {"job_id": "55435945-f1b1-44df-a310-dd1c07c2e09a", "topics": [0]}
data = json.dumps(payload).encode("utf-8")

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

try:
    resp = urllib.request.urlopen(req, timeout=300)
    result = json.loads(resp.read().decode())
    print(json.dumps(result, indent=2, ensure_ascii=False))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
