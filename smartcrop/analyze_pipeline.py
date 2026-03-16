"""
Analyze Pipeline: AI-powered topic analysis and FFmpeg clipping.

Flow:
1. /analyze: Read SRT from completed job → Send to AI → Return topics with virality scores
2. /clip: Take selected topics → Cut segments from result.mp4 (portrait) → Merge → Return URL
"""

import os
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any

# Use try/except for requests since it may not be installed locally
try:
    import requests  # type: ignore[import]
except ImportError:
    requests = None  # type: ignore[assignment]

DB_PATH = os.environ.get('PORTRAITGEN_DB_PATH', 'data/job_history.db')
DATA_DIR = os.path.dirname(DB_PATH) or '.'
LOG_FILE = os.path.join(DATA_DIR, 'pipeline.log')
FFMPEG_THREADS = int(os.environ.get('PORTRAITGEN_FFMPEG_THREADS', '3'))
FFMPEG_PRESET = os.environ.get('PORTRAITGEN_FFMPEG_PRESET', 'veryfast')


def log_event(msg: str) -> None:
    """Log to pipeline.log and stdout."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.utcnow().isoformat()}] [ANALYZE] {msg}\n")
            f.flush()
    except Exception:
        pass
    try:
        print(f"[ANALYZE] {msg}", flush=True)
    except OSError:
        pass


def _get_stderr_tail(stderr: str, max_chars: int = 500) -> str:
    """Safely get the tail of stderr string."""
    if not stderr:
        return ""
    if len(stderr) <= max_chars:
        return stderr
    return stderr[len(stderr) - max_chars:]


def analyze_srt(job_id: str, srt_path: str) -> dict:
    """
    Send SRT content to Sumopod AI for topic analysis.
    Returns parsed JSON with topics, scores, segments.
    """
    if requests is None:
        raise RuntimeError("requests library not installed")

    sumopod_url = 'https://ai.sumopod.com/v1/chat/completions'
    api_key = os.environ.get('SUMOPOD_API_KEY')

    if not api_key:
        raise RuntimeError('SUMOPOD_API_KEY not set')

    # Read SRT content
    with open(srt_path, 'r', encoding='utf-8') as f:
        srt_content = f.read()

    if not srt_content.strip():
        raise RuntimeError('SRT file is empty')

    log_event(f"Analyzing SRT for job {job_id} ({len(srt_content)} chars)")

    prompt = f"""Kamu adalah analis konten video profesional. Berikut adalah transkrip subtitle (SRT) dari sebuah video. 
Analisis transkrip ini dan identifikasi topik-topik utama yang dibahas.

Untuk setiap topik:
1. Beri virality score 0-10 (seberapa viral/menarik topik ini untuk sosial media)
2. Buat draft judul yang catchy untuk sosial media (bahasa sesuai konten)
3. Buat draft caption yang engaging (bahasa sesuai konten)
4. Buat draft hashtag yang relevan
5. Identifikasi segment waktu (detik mulai dan detik akhir) dimana topik ini dibahas

ATURAN PENTING:
- Urutkan berdasarkan virality score tertinggi
- Waktu dalam format detik (misal: 65.5 artinya menit 1 detik 5.5)
- Satu topik bisa tersebar di beberapa segment
- TOTAL DURASI semua segment dalam satu topik HARUS antara 60 detik (1 menit) sampai 180 detik (3 menit)
- Jika pembahasan topik lebih dari 3 menit, pilih bagian yang PALING MENARIK saja,
- jangan sampai lebih dari 180 detik sama sekali, batas maksimal aman 179 detik
- Jika pembahasan topik kurang dari 1 menit, gabungkan dengan konteks sekitarnya agar minimal 1 menit
- Pastikan setiap segment dimulai dan diakhiri di titik yang natural (awal/akhir kalimat)

Balas HANYA dalam format JSON berikut (tanpa markdown, tanpa backtick, murni JSON):
{{
  "topics": [
    {{
      "topic": "Deskripsi singkat topik",
      "score": 9,
      "draft_judul": "Judul catchy untuk sosmed",
      "draft_caption": "Caption engaging...",
      "draft_hashtag": "#tag1 #tag2 #tag3",
      "segments": [
        {{"order": 1, "start": 12.0, "end": 45.5}},
        {{"order": 2, "start": 120.0, "end": 180.0}}
      ]
    }}
  ]
}}

Transkrip SRT:
{srt_content}
"""

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': 'seed-2-0-mini-free',
        'messages': [
            {'role': 'system', 'content': 'Kamu adalah analis konten video profesional. Selalu balas dalam format JSON valid.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.7,
        'max_tokens': 4096
    }

    max_retries = 3
    timeout = 300
    ai_content = None

    for attempt in range(max_retries):
        try:
            log_event(f"Sending to Sumopod AI for analysis (attempt {attempt+1}/{max_retries}, model: seed-2-0-mini-free)...")
            resp = requests.post(sumopod_url, headers=headers, json=payload, timeout=timeout)
            log_event(f"Sumopod analysis response status: {resp.status_code}")
            resp.raise_for_status()
            
            response_data = resp.json()
            ai_content = response_data['choices'][0]['message']['content']
            if ai_content:
                break
        except (requests.exceptions.RequestException, Exception) as e:
            log_event(f"Analysis attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                log_event(f"Retrying analysis in {wait_time}s...")
                import time
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"AI analysis failed after {max_retries} attempts: {e}")

    if not ai_content:
        raise RuntimeError("AI analysis returned empty content")

    log_event(f"AI response length: {len(ai_content)} chars")

    # Clean and parse JSON from AI response
    ai_content = ai_content.strip()
    # Remove markdown code blocks if present
    if ai_content.startswith('```'):
        lines = ai_content.split('\n')
        lines = [l for l in lines if not l.strip().startswith('```')]
        ai_content = '\n'.join(lines)

    try:
        analysis: dict[str, Any] = json.loads(ai_content)
    except json.JSONDecodeError as e:
        log_event(f"Failed to parse AI JSON: {str(e)}\nRaw: {_get_stderr_tail(ai_content)}")
        raise RuntimeError(f"AI returned invalid JSON: {str(e)}")

    # Filter out bad entries, sort by score descending and inject IDs
    if 'topics' in analysis and isinstance(analysis['topics'], list):
        analysis['topics'] = [t for t in analysis['topics'] if isinstance(t, dict)]
        analysis['topics'] = sorted(
            analysis['topics'],
            key=lambda t: t.get('score', 0),
            reverse=True
        )
        for i, topic in enumerate(analysis['topics']):
            topic['id'] = i

    return analysis


def clip_raw_video(job_id: str, raw_video_path: str, segments: list, output_path: str) -> str:
    """
    Stage 2 Step 1: Cut & Merge segments from raw video using a single-pass filter_complex.
    This is extremely robust against problematic source codecs (AV1/AAC).
    """
    if not segments:
        raise RuntimeError("No segments provided for clipping")

    log_event(f"Clipping {len(segments)} segments from RAW video {raw_video_path}")

    # Build filter_complex string
    v_filters = []
    a_filters = []
    inputs = ""
    for i, seg in enumerate(segments):
        start = float(seg['start'])
        end = float(seg['end'])
        # [0:v]trim=start=S:end=E,setpts=PTS-STARTPTS[vI];
        v_filters.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
        # [0:a]atrim=start=S:end=E,asetpts=PTS-STARTPTS,aresample=async=1[aI];
        a_filters.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aresample=async=1[a{i}]")
        inputs += f"[v{i}][a{i}]"

    filter_complex = ";".join(v_filters + a_filters)
    filter_complex += f";{inputs}concat=n={len(segments)}:v=1:a=1[outv][outa]"

    cmd = [
        'ffmpeg', '-y',
        '-i', str(raw_video_path),
        '-filter_complex', filter_complex,
        '-map', '[outv]',
        '-map', '[outa]',
        '-c:v', 'libx264', '-crf', '18', '-preset', 'ultrafast',
        '-c:a', 'aac', '-b:a', '192k',
        '-threads', str(FFMPEG_THREADS),
        '-movflags', '+faststart',
        str(output_path)
    ]

    log_event(f"Running robust single-pass clipping...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        log_event(f"FFmpeg robust clipping failed: {_get_stderr_tail(result.stderr)}")
        raise RuntimeError(f"FFmpeg robust clipping error: {result.stderr}")

    return str(output_path)


def produce_clip(job_id: str, output_dir: str, selected_indices: list, analysis_data: dict, clip_id: str = None) -> dict:
    """
    Stage 2 Main Workflow:
    Raw Cut -> Re-transcribe Clip -> Portrait Render -> Output.
    """
    from .api_pipeline import extract_audio, transcribe_audio, process_video  # Local import to avoid circular dep

    job_dir = Path(output_dir) / job_id
    # Find rawvideo.mp4 or similar
    import glob
    raw_files = glob.glob(str(job_dir / 'rawvideo.*'))
    if not raw_files:
        raise RuntimeError(f"Raw video not found in {job_dir}")
    raw_video_path = raw_files[0]

    topics = analysis_data.get('topics', [])
    selected_segments = []
    metadata = {"title": [], "caption": [], "hashtags": set()}

    for idx in selected_indices:
        if 0 <= idx < len(topics):
            topic = topics[idx]
            metadata["title"].append(topic.get('draft_judul', ''))
            metadata["caption"].append(topic.get('draft_caption', ''))
            for tag in topic.get('draft_hashtag', '').split():
                metadata["hashtags"].add(tag)
            for seg in topic.get('segments', []):
                selected_segments.append(seg)

    # Sort & Merge
    selected_segments.sort(key=lambda s: s['start'])
    merged = []
    for s in selected_segments:
        if merged and s['start'] < merged[-1]['end']:
            merged[-1]['end'] = max(merged[-1]['end'], s['end'])
        else:
            merged.append(s)

    if not clip_id:
        clip_id = str(uuid.uuid4())[:8]
    selected_raw_path = job_dir / f"temp_selected_{clip_id}.mp4"
    final_clip_filename = f"clip_{clip_id}.mp4"
    
    log_event(f"Stage 2: Cutting raw video for clip {clip_id}")
    clip_raw_video(job_id, raw_video_path, merged, str(selected_raw_path))

    log_event(f"Stage 2: Re-transcribing clip {clip_id} for accuracy")
    # Extract audio of the clip
    clip_audio = extract_audio(f"{job_id}_clip_{clip_id}", selected_raw_path, job_dir)
    # Transcribe the short clip
    clip_srt = transcribe_audio(f"{job_id}_clip_{clip_id}", clip_audio, job_dir)

    log_event(f"Stage 2: Final Portrait Rendering for {clip_id}")
    # We call process_video with custom output filename.
    # It will automatically create a matching .ass file.
    final_portrait, duration = process_video(job_id, selected_raw_path, clip_srt, job_dir, output_filename=final_clip_filename)
    
    # R2 UPLOAD & CLEANUP
    r2_url = None
    try:
        from .storage_service import get_storage_service
        storage = get_storage_service()
        if storage.client:
            log_event(f"Stage 2: Uploading {final_clip_filename} to R2...")
            remote_path = f"jobs/{job_id}/{final_clip_filename}"
            r2_url = storage.upload_file(str(final_portrait), remote_path)
            
            # If upload successful, delete local final portrait
            storage.delete_local_file(final_portrait)
            # Also delete the .ass file if it exists
            ass_file = final_portrait.with_suffix('.ass')
            storage.delete_local_file(ass_file)
    except Exception as e:
        log_event(f"Stage 2: R2 Upload/Cleanup FAILED: {e}")

    # Cleanup temp files for this clip
    try:
        selected_raw_path.unlink(missing_ok=True)
        clip_audio.unlink(missing_ok=True)
        # We can also remove the intermediate SRT since it's burned in
        clip_srt.unlink(missing_ok=True)
    except: pass

    return {
        'clip_id': clip_id,
        'clip_filename': final_clip_filename,
        'r2_url': r2_url,
        'draft_judul': ' | '.join([t for t in metadata["title"] if t]),
        'draft_caption': '\n\n'.join([c for c in metadata["caption"] if c]),
        'draft_hashtag': ' '.join(sorted(metadata["hashtags"])),
        'segments_used': len(merged)
    }


def clip_video(job_id: str, video_path: str, segments: list, output_path: str) -> str:
    """
    Cut segments from result.mp4 (portrait video with subtitles) and merge them.
    Returns the output path string.
    """
    if not segments:
        raise RuntimeError("No segments provided for clipping")

    log_event(f"Clipping {len(segments)} segments from {video_path}")

    temp_dir = Path(output_path).parent / f"_temp_clip_{job_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    segment_files: list[Path] = []

    try:
        for i, seg in enumerate(segments):
            start = float(seg['start'])
            end = float(seg['end'])
            duration = end - start

            if duration <= 0:
                log_event(f"Skipping invalid segment {i}: start={start}, end={end}")
                continue

            seg_file = temp_dir / f"seg_{i:04d}.mp4"

            # Optimized for speed: use -c copy and fast seeking
            cut_cmd = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-t', str(duration),
                '-i', str(video_path),
                '-c', 'copy',
                '-threads', str(FFMPEG_THREADS),
                str(seg_file)
            ]

            log_event(f"Cutting segment {i+1}/{len(segments)}: {start:.1f}s - {end:.1f}s (Fast Copy)")
            result = subprocess.run(cut_cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                log_event(f"FFmpeg copy-cut error for segment {i}: {_get_stderr_tail(result.stderr)}")
                # Fallback to re-encode if copy fails (e.g. format issues)
                log_event("Retrying with re-encode fallback...")
                cut_cmd_fallback = [
                    'ffmpeg', '-y', '-ss', str(start), '-i', str(video_path), '-t', str(duration),
                    '-c:v', 'libx264', '-crf', '20', '-preset', FFMPEG_PRESET,
                    '-c:a', 'aac', '-b:a', '192k', '-threads', str(FFMPEG_THREADS),
                    str(seg_file)
                ]
                result = subprocess.run(cut_cmd_fallback, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    continue

            if seg_file.exists() and seg_file.stat().st_size > 0:
                segment_files.append(seg_file)

        if not segment_files:
            raise RuntimeError("No valid segments were cut")

        # Single segment: just copy
        if len(segment_files) == 1:
            shutil.copy2(str(segment_files[0]), str(output_path))
            log_event(f"Single segment, copied directly to {output_path}")
        else:
            # Create concat list
            concat_file = temp_dir / 'concat.txt'
            with open(str(concat_file), 'w', encoding='utf-8') as f:
                for sf in segment_files:
                    f.write(f"file '{sf.resolve()}'\n")

            merge_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                '-movflags', '+faststart',
                str(output_path)
            ]

            log_event(f"Merging {len(segment_files)} segments (Fast Copy)...")
            result = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                log_event(f"FFmpeg concat-copy error: {_get_stderr_tail(result.stderr)}")
                # Last resort fallback: re-encode merge
                merge_cmd_fallback = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_file),
                    '-c:v', 'libx264', '-crf', '20', '-preset', FFMPEG_PRESET,
                    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(output_path)
                ]
                subprocess.run(merge_cmd_fallback, check=True, timeout=600)

        log_event(f"Clip created: {output_path}")

    finally:
        # Cleanup temp files
        try:
            shutil.rmtree(str(temp_dir), ignore_errors=True)
        except Exception:
            pass

    return str(output_path)


def render_clip(job_id: str, output_dir: str, selected_indices: list, analysis_data: dict, clip_id: str = None) -> dict:
    """
    DEPRECATED: Compatibility wrapper for new produce_clip.
    """
    return produce_clip(job_id, output_dir, selected_indices, analysis_data, clip_id=clip_id)
