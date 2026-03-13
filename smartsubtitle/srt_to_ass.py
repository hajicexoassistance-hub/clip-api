import sys
import re
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'smartsubtitle')))
from subtitle_service import generate_ass

def parse_srt(srt_path):
    """Parse SRT file to word_timings format for generate_ass."""
    with open(srt_path, encoding="utf-8") as f:
        content = f.read()
    # Split into blocks by double newlines
    blocks = re.split(r'\n{2,}|\r\n{2,}', content)
    word_timings = []
    for block in blocks:
        block = block.strip()
        if not block: continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) >= 2:
            # Flexible regex for SRT timestamp (supports comma or dot, and varying spaces)
            m = re.search(r"(\d+):(\d+):(\d+)[,\.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,\.](\d+)", lines[0] if len(lines[0]) > 10 else lines[1])
            if m:
                # Convert SRT (ms) to ASS (10ms units)
                s_h, s_m, s_s, s_ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                e_h, e_m, e_s, e_ms = int(m.group(5)), int(m.group(6)), int(m.group(7)), int(m.group(8))
                
                # Normalize ms to 3 digits then take first 2 for ASS
                if len(m.group(4)) == 3: s_ass_ms = s_ms // 10
                elif len(m.group(4)) == 2: s_ass_ms = s_ms
                else: s_ass_ms = s_ms * 10
                
                if len(m.group(8)) == 3: e_ass_ms = e_ms // 10
                elif len(m.group(8)) == 2: e_ass_ms = e_ms
                else: e_ass_ms = e_ms * 10

                start = f"{s_h}:{s_m:02}:{s_s:02}.{s_ass_ms:02}"
                end = f"{e_h}:{e_m:02}:{e_s:02}.{e_ass_ms:02}"
                
                # Text is everything after the timestamp line
                text_start_idx = 1 if re.search(r"-->", lines[0]) else 2
                text = ' '.join(lines[text_start_idx:])
                words = text.split()
                if not words: continue
                
                # Interpolate word timings
                total_ms = (e_h*3600000 + e_m*60000 + e_s*1000 + e_ms) - (s_h*3600000 + s_m*60000 + s_s*1000 + s_ms)
                word_duration = total_ms // len(words)
                
                for i, w in enumerate(words):
                    w_start_ms = (s_h*3600000 + s_m*60000 + s_s*1000 + s_ms) + (i * word_duration)
                    w_end_ms = w_start_ms + word_duration
                    
                    def ms_to_ass(ms):
                        h = ms // 3600000
                        m = (ms % 3600000) // 60000
                        s = (ms % 60000) // 1000
                        cs = (ms % 1000) // 10
                        return f"{h}:{m:02}:{s:02}.{cs:02}"
                    
                    word_timings.append({
                        "start": ms_to_ass(w_start_ms),
                        "end": ms_to_ass(w_end_ms),
                        "text": w
                    })
    return word_timings

def main():
    if len(sys.argv) < 3:
        print("Usage: python srt_to_ass.py <input.srt> <output.ass>")
        sys.exit(1)
    srt_path = sys.argv[1]
    ass_path = sys.argv[2]
    word_timings = parse_srt(srt_path)
    ass = generate_ass(word_timings, options={
        "resolution": "1080x1920"
    })
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    print(f"ASS saved to {ass_path}")

if __name__ == "__main__":
    main()
