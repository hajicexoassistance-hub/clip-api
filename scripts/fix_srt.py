import json
import sys

srt_path = sys.argv[1]
with open(srt_path, encoding='utf-8') as f:
    data = f.read()
try:
    obj = json.loads(data)
    if isinstance(obj, dict) and 'text' in obj:
        srt_text = obj['text']
        with open(srt_path, 'w', encoding='utf-8') as f2:
            f2.write(srt_text)
        print('SRT fixed:', srt_path)
    else:
        print('No text field found in JSON')
except Exception as e:
    print('Not a JSON file or error:', e)
