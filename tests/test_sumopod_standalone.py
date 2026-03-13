import os
import requests
import json
from dotenv import load_dotenv

def test_sumopod():
    load_dotenv()
    api_key = os.getenv('SUMOPOD_API_KEY')
    api_url = "https://ai.sumopod.com/v1/audio/transcriptions"
    
    # Try to find a recent mp3 file in output directory
    output_dir = 'output'
    mp3_files = [f for f in os.listdir(output_dir) if f.endswith('.mp3')]
    if not mp3_files:
        print("No MP3 files found in output directory to test with.")
        return

    audio_path = os.path.join(output_dir, mp3_files[0])
    print(f"Testing with file: {audio_path}")
    print(f"API URL: {api_url}")
    print(f"API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")

    headers = {'Authorization': f'Bearer {api_key}'}
    files = {'file': (os.path.basename(audio_path), open(audio_path, 'rb'), 'audio/mpeg')}
    data = {'model': 'whisper-1', 'response_format': 'srt'}

    try:
        resp = requests.post(api_url, files=files, headers=headers, data=data, timeout=60)
        print(f"Status Code: {resp.status_code}")
        print("--- Response Text ---")
        print(resp.text)
        print("--- End Response ---")
        
        if resp.status_code == 200:
            try:
                json_data = resp.json()
                print("--- Decoded JSON ---")
                print(json.dumps(json_data, indent=2))
            except:
                print("Response is not JSON")
    except Exception as e:
        print(f"Error during request: {e}")

if __name__ == "__main__":
    test_sumopod()
