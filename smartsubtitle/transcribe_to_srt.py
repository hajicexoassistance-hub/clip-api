import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'smartanalyze')))
from asr_sumopod_service import ASRService

def write_srt(word_timings, srt_path, words_per_line=3):
    """Convert word timings to SRT file, grouping by N words per line."""
    def ts_to_srt(ts):
        # ASS: h:mm:ss.xx, SRT: hh:mm:ss,ms
        h, m, s = ts.split(":")
        s, ms = s.split(".")
        return f"{int(h):02}:{int(m):02}:{int(float(s)):02},{int(ms)*10:03}"
    idx = 1
    with open(srt_path, "w", encoding="utf-8") as f:
        for i in range(0, len(word_timings), words_per_line):
            group = word_timings[i:i+words_per_line]
            start = group[0]['start']
            end = group[-1]['end']
            text = ' '.join([w['text'] for w in group])
            f.write(f"{idx}\n{ts_to_srt(start)} --> {ts_to_srt(end)}\n{text}\n\n")
            idx += 1

def main():
    if len(sys.argv) < 3:
        print("Usage: python transcribe_to_srt.py <audio_file> <output_srt>")
        sys.exit(1)
    audio_file = sys.argv[1]
    output_srt = sys.argv[2]
    asr = ASRService()
    result = asr.transcribe(audio_file)
    word_timings = asr.get_word_timings(result)
    write_srt(word_timings, output_srt, words_per_line=3)
    print(f"SRT saved to {output_srt}")

if __name__ == "__main__":
    main()
