import os
import subprocess
import json
import requests
import sys
import numpy as np
from pathlib import Path

# Fix path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

DB_PATH = os.environ.get('PORTRAITGEN_DB_PATH', 'data/job_history.db')
DATA_DIR = os.path.dirname(DB_PATH)
LOG_FILE = os.path.join(DATA_DIR, 'pipeline.log')
PORTRAITGEN_FFMPEG_THREADS = os.getenv("PORTRAITGEN_FFMPEG_THREADS", "8")
USE_GPU_VAL = os.getenv("PORTRAITGEN_USE_GPU", "false").lower()
USE_GPU = "legacy" if USE_GPU_VAL == "legacy" else (USE_GPU_VAL == "true")
BLUR_STRENGTH = os.environ.get('PORTRAITGEN_BLUR', '3')
OUTPUT_SCALE = os.environ.get('PORTRAITGEN_OUTPUT_SCALE', '720x1280')  # default vertical for socials
FFMPEG_PRESET = os.environ.get('PORTRAITGEN_FFMPEG_PRESET', 'veryfast')

def log_event(msg):
    from datetime import datetime
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {msg}\n")
            f.flush()
    except Exception:
        pass
    try:
        print(f"[PIPELINE] {msg}", flush=True)
    except OSError:
        pass # Ignore print errors in background processes

def is_valid_url(url):
    import re
    yt_pattern = r'^https?://(www\.)?(youtube\.com|youtu\.be)/.+$'
    return re.match(yt_pattern, url)

def cleanup_expired_files(output_dir, db_path=None, expire_days=1):
    import sqlite3, time, os
    if db_path is None:
        db_path = DB_PATH
    
    log_event(f"Cleanup start: older than {expire_days} days")
    try:
        log_event("Cleanup: calculating cutoff")
        cutoff = time.time() - (expire_days * 86400)
        
        log_event(f"Cleanup: checking if exists: {output_dir}")
        exists = os.path.exists(output_dir)
        log_event(f"Cleanup: exists={exists}")
        
        if not exists:
            return
        
        log_event(f"Cleanup: listing directory")
        files = os.listdir(output_dir)
        log_event(f"Cleanup: items found={len(files)}")
        
        count = 0
        for filename in files:
            file_path = os.path.join(output_dir, filename)
            log_event(f"Cleanup: stat {filename}")
            if os.path.isfile(file_path):
                mtime = os.path.getmtime(file_path)
                if mtime < cutoff:
                    log_event(f"Cleanup: remove {filename}")
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        log_event(f"Cleanup: error removing {filename}: {e}")
            elif os.path.isdir(file_path):
                log_event(f"Cleanup: skip dir {filename}")
                
        log_event(f"Cleanup finished: {count} removed")
    except Exception as e:
        log_event(f"Cleanup global error: {e}")

def download_video(job_id, url, output_dir):
    # Download as rawvideo with original extension
    output_template = str(Path(output_dir) / 'rawvideo.%(ext)s')
    # Force mp4 for best compatibility
    ytdlp_cmd = [
        sys.executable, '-m', 'yt_dlp',
        '--js-runtimes', 'node',
        '-f', "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
        '--no-playlist',
        '--retries', '1',
        '--fragment-retries', '1',
        '--no-part',  # Avoid .part files which cause WinError 32 on some Windows systems
        '-o', output_template,
        url
    ]
    try:
        result = subprocess.run(ytdlp_cmd, check=True, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        log_event("yt-dlp timed out")
        raise RuntimeError("yt-dlp timed out")
    except subprocess.CalledProcessError as e:
        log_event(f"yt-dlp failed: {e.stderr}")
        raise RuntimeError(f"yt-dlp error: {e.stderr}")
    # Find the downloaded file (matches rawvideo.* pattern)
    import glob, time
    pattern = str(Path(output_dir) / 'rawvideo.*')
    timeout = 60  # seconds
    poll_interval = 1
    elapsed = 0
    video_file = None
    while elapsed < timeout:
        files = [f for f in glob.glob(pattern) if not f.endswith('.part')]
        if files:
            candidate = Path(files[0])
            if candidate.exists() and candidate.stat().st_size > 0:
                video_file = candidate
                break
        time.sleep(poll_interval)
        elapsed += poll_interval
    if not video_file:
        log_event(f"yt-dlp did not produce any valid file for job {job_id}")
        raise RuntimeError("yt-dlp did not produce any valid file")
    return video_file

def extract_audio(job_id, video_file, output_dir):
    # Ekstrak langsung ke MP3 (Sumopod menerima MP3)
    # Optimasi: Mono (ac 1), 16kHz (ar 16000), Low Bitrate (ab 32k) untuk transkripsi lebih cepat & upload ringan
    audio_file_mp3 = Path(output_dir) / 'audio.mp3'
    ffmpeg_mp3_cmd = [
        'ffmpeg', '-y', '-i', str(video_file), '-vn', '-sn', '-dn',
        '-ac', '1', '-ar', '16000',
        '-af', 'aresample=async=1',
        '-codec:a', 'libmp3lame', '-b:a', '32k',
        '-threads', str(PORTRAITGEN_FFMPEG_THREADS),
        str(audio_file_mp3)
    ]
    try:
        subprocess.run(ffmpeg_mp3_cmd, check=True, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        log_event("ffmpeg mp3 convert timed out")
        raise RuntimeError("ffmpeg mp3 convert timed out")
    except subprocess.CalledProcessError as e:
        log_event(f"ffmpeg mp3 convert failed: {e.stderr}. Trying fallback to silence.")
        # Fallback: Create silent audio if source has no audio stream
        # Get duration first
        try:
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_file)]
            dur = subprocess.check_output(dur_cmd).decode().strip()
            silence_cmd = [
                'ffmpeg', '-y', '-f', 'lavfi', '-i', f'anullsrc=r=16000:cl=mono:d={dur}',
                '-c:a', 'libmp3lame', '-b:a', '32k', str(audio_file_mp3)
            ]
            subprocess.run(silence_cmd, check=True, capture_output=True, timeout=30)
        except Exception as e2:
            log_event(f"Silence fallback failed: {e2}")
            raise RuntimeError(f"ffmpeg mp3 error: {e.stderr}")
            
    if not audio_file_mp3.exists() or audio_file_mp3.stat().st_size == 0:
        log_event(f"MP3 file missing or empty: {audio_file_mp3}")
        raise RuntimeError(f"MP3 file missing or empty: {audio_file_mp3}")
    return audio_file_mp3

def transcribe_audio(job_id, audio_file, output_dir):
    sumopod_url = 'https://ai.sumopod.com/v1/audio/transcriptions'
    api_key = os.environ.get('SUMOPOD_API_KEY')
    srt_file = Path(output_dir) / 'subtitle.srt'
    
    if not api_key:
        raise RuntimeError('No API key for Sumopod')

    audio_path = Path(audio_file)
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise RuntimeError(f'Audio source missing for transcription: {audio_path}')

    headers = {'Authorization': f'Bearer {api_key}'}
    data = {'model': 'whisper-1', 'response_format': 'srt'}
    
    max_retries = 3
    timeout = 1200
    srt_text = None

    for attempt in range(max_retries):
        try:
            with open(str(audio_path), 'rb') as f:
                files = {'file': (os.path.basename(str(audio_path)), f, 'audio/mpeg')}
                log_event(f"[DEBUG] Transcription attempt {attempt+1}/{max_retries} for {job_id} (timeout={timeout}s)")
                
                resp = requests.post(sumopod_url, files=files, headers=headers, data=data, timeout=timeout)
                log_event(f"[DEBUG] Sumopod response status: {resp.status_code}")
                resp.raise_for_status()
                
                # Sumopod returns JSON with SRT in the "text" field
                try:
                    srt_json = resp.json()
                    if isinstance(srt_json, dict) and 'text' in srt_json:
                        srt_text = srt_json['text']
                        if isinstance(srt_text, str):
                            srt_text = srt_text.replace("\\n", "\n")
                    else:
                        srt_text = resp.text
                except Exception:
                    srt_text = resp.text
                
                if srt_text:
                    break # Success!
                    
        except (requests.exceptions.RequestException, Exception) as e:
            log_event(f"[DEBUG] Transcription attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                log_event(f"[DEBUG] Retrying in {wait_time}s...")
                import time
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Transcription failed after {max_retries} attempts: {e}")

    if not srt_text:
        raise RuntimeError("Transcription result is empty")
    
    log_event(f"[DEBUG] Final SRT Text length: {len(srt_text)}")
    with open(str(srt_file), 'w', encoding='utf-8') as out:
        out.write(srt_text)
        out.flush()
        os.fsync(out.fileno())
    
    # Give OS a moment to settle the file write
    import time
    time.sleep(1)
    return srt_file

def srt_to_ass(srt_file, ass_file):
    # Konversi SRT ke ASS dengan script srt_to_ass.py
    import sys
    subprocess.run([
        sys.executable, str(Path(__file__).parent.parent / 'smartsubtitle' / 'srt_to_ass.py'),
        str(srt_file), str(ass_file)
    ], check=True)
    return ass_file

def process_video(job_id, video_file, srt_file, output_dir, preset_name='default', output_filename='result.mp4'):
    import scene_detect
    import subject_detect
    import crop_calc
    import ffmpeg_builder
    import utils
    import config

    portrait_file = Path(output_dir) / output_filename
    log_event(f"[DEBUG] Akan encode ke portrait_file: {portrait_file}")
    
    # 1. Get basic info
    ffprobe_cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,duration', '-of', 'json', str(video_file)
    ]
    probe = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True, timeout=60)
    info = json.loads(probe.stdout)
    if not info.get('streams'):
        raise RuntimeError("Could not find video stream in ffprobe output")
        
    width = info['streams'][0]['width']
    height = info['streams'][0]['height']
    duration = float(info['streams'][0].get('duration', 0))
    log_event(f"Resolution: {width}x{height}, Duration: {duration}s")

    # 2. Scene Detection (CLI logic)
    log_event("Mendeteksi scene...")
    try:
        scenes = scene_detect.detect_scenes(str(video_file), threshold=config.SCENE_THRESHOLD)
    except Exception as e:
        log_event(f"Scene detection fatal error: {e}")
        scenes = []
        
    if not scenes:
        log_event("No scenes detected or error occurred, using full duration as single scene")
        scenes = [(0, duration)]
    
    log_event(f"Detected {len(scenes)} scenes")
    
    # 3. Subject Detection per scene (Multi-frame optimized)
    log_event(f"Menganalisis {len(scenes)} scene (Multi-frame sampling untuk stabilitas)...")
    temp_scene_data = []
    
    for start, end in scenes:
        # Peningkatan: Ambil 3 frame (awal, tengah, akhir) per scene untuk akurasi lebih tinggi
        duration_scene = end - start
        if duration_scene < 0.5:
            sample_times = [(start + end) / 2]
        else:
            sample_times = [start + 0.1, (start + end) / 2, end - 0.1]
            
        detected_centers = []
        frames_collected = []
        for t in sample_times:
            frame = utils.get_frame(str(video_file), t)
            if frame is not None:
                frames_collected.append(frame)
                # Downscale for performance
                import cv2
                small_frame = cv2.resize(frame, (640, int(640 * height / width)))
                center_x_small = subject_detect.detect_subject(small_frame)
                if center_x_small is not None:
                    detected_centers.append(int(center_x_small * width / 640))
        
        if detected_centers:
            # Peningkatan: Gunakan logika Active Speaker jika lebih dari satu sampel tersedia
            center_x = subject_detect.detect_speaker(frames_collected)
            if center_x is None:
                center_x = int(np.median(detected_centers))
        else:
            center_x = width // 2
            
        x, crop_w = crop_calc.calc_crop(center_x, width, height)
        temp_scene_data.append((start, end, x, crop_w))

    # Standardize crop width and center X across all scenes for stability
    min_crop_w = min([d[3] for d in temp_scene_data])
    if min_crop_w % 2 != 0: min_crop_w -= 1
    
    scene_data = []
    for start, end, x, crop_w in temp_scene_data:
        new_x = max(0, min(x + (crop_w - min_crop_w) // 2, width - min_crop_w))
        scene_data.append((start, end, new_x, min_crop_w))

    # 4. Build Filter (CLI logic adapted)
    # Using ffmpeg_builder logic but merging with your existing blur & subtitle requirements
    filter_str = ffmpeg_builder.build_filter(scene_data, height, filter_name=None)
    
    # 5. ASS subtitle
    # Use unique ASS name to avoid collision during parallel rendering
    ass_base = output_filename.replace('.mp4', '')
    ass_file = Path(output_dir) / f'{ass_base}.ass'
    srt_to_ass(srt_file, ass_file)
    ass_path = str(ass_file.resolve().absolute())
    if os.name == 'nt':
        ass_path_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    else:
        ass_path_escaped = ass_path
    
    # Optional downscale
    scale_filter = ""
    if OUTPUT_SCALE:
        try:
            target_w, target_h = [int(val) for val in OUTPUT_SCALE.lower().split('x')]
            if height > target_h or width > target_w:
                scale_filter = f",scale={target_w}:{target_h}"
        except Exception: pass

    # Inject ASS, setsar=1 (fix playback), and scaling into the final output of the built filter
    # The built filter ends with [outv]. We'll map that to our Final filter.
    final_filter = filter_str.replace("[outv]", f"[vfinal];[vfinal]ass='{ass_path_escaped}'{scale_filter},setsar=1,format=yuv420p[final]")

    # 6. Render with CPU optimizations (ultrafast preset)
    # Gunakan NVENC jika GPU diaktifkan, atau h264_mf untuk GPU lama (Legacy)
    if USE_GPU == "legacy":
        v_encoder = "h264_mf"
        v_params = ["-b:v", "6M", "-quality", "100"] 
    elif USE_GPU:
        v_encoder = "h264_nvenc"
        v_params = ["-profile:v", "high", "-level", "4.1", "-preset", "p4", "-tune", "hq", "-b:v", "6M", "-rc", "vbr", "-cq", "20"]
    else:
        v_encoder = "libx264"
        v_params = ["-profile:v", "high", "-level", "4.1", "-crf", "20", "-preset", "veryfast"]
    
    ffmpeg_burn_cmd = [
        'ffmpeg', "-y",
        "-i", str(video_file),
        "-filter_complex", final_filter,
        "-map", "[final]",
        "-map", "0:a?",
        "-c:v", v_encoder
    ] + v_params + [
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-threads", PORTRAITGEN_FFMPEG_THREADS,
        str(portrait_file)
    ]
    
    log_event(f"[DEBUG] Jalankan FFmpeg: {' '.join(ffmpeg_burn_cmd)}")
    log_file_path = os.path.join(DATA_DIR, 'pipeline.log')
    try:
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(f"\n--- FFmpeg started for {job_id} ---\n")
            f.flush()
            result = subprocess.run(ffmpeg_burn_cmd, stdout=f, stderr=subprocess.STDOUT, text=True, timeout=7200)
            f.write(f"\n--- FFmpeg finished for {job_id} with code {result.returncode} ---\n")
            
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed with code {result.returncode}. Check pipeline.log for details.")
                
        return portrait_file, duration
    except Exception as e:
        log_event(f"FFmpeg render error: {e}")
        raise

def run_pipeline(job_id, url, output_dir, preset='default', progress_callback=None):
    cleanup_expired_files(output_dir)
    if not is_valid_url(url):
        return {'error_message': 'URL tidak valid atau bukan YouTube.'}
    
    def update_progress(percent, status):
        if progress_callback:
            progress_callback(percent, status)
        log_event(f"Progress {percent}%: {status}")

    result = {
        'video': None,

        'srt': None,
        'audio': None,
        'title': None,
        'duration': None,
        'error_message': None
    }
    output_dir = Path(output_dir)
    
    # Create job-specific directory
    job_dir = Path(output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    
    update_progress(5, "Memulai job")
    log_event(f"Job {job_id} started for url={url}")
    
    try:
        update_progress(10, "Mengunduh video dari YouTube")
        video_file = download_video(job_id, url, job_dir)
        
        update_progress(30, "Mengekstrak audio")
        audio_file = extract_audio(job_id, video_file, job_dir)
        result['audio'] = str(audio_file)
        
        update_progress(50, "Mentranskripsi audio (AI)")
        srt_file = transcribe_audio(job_id, audio_file, job_dir)
        result['srt'] = str(srt_file)
        
        update_progress(70, "Rendering video portrait & subtitle (FFmpeg)")
        portrait_file, duration = process_video(job_id, video_file, srt_file, job_dir, preset)
        result['video'] = str(portrait_file)
        result['duration'] = duration
        
        update_progress(95, "Mengambil informasi video")
        title = get_video_title(url)
        result['title'] = title
        
        update_progress(100, "Selesai")
        log_event(f"Job {job_id} finished successfully")
        # Cleanup source video to save space (keep outputs)
        try:
            Path(video_file).unlink(missing_ok=True)
        except Exception as e:
            log_event(f"[DEBUG] Cleanup source video failed: {e}")
    except Exception as e:
        log_event(f"Job {job_id} failed: {str(e)}")
        result['error_message'] = str(e)
    return result

def run_pipeline_stage1(job_id, url, output_dir, preset='default', progress_callback=None):
    """
    Stage 1: Download -> Extract Audio -> Transcribe -> AI Analyze.
    Stops before rendering portrait.
    """
    def log(m): log_event(f"[STAGE1-{job_id}] {m}")
    
    try:
        log("Function entered")
        # cleanup_expired_files(output_dir)  # Removed...
        
        if not is_valid_url(url):
            log("Invalid URL")
            return {'error_message': 'URL tidak valid atau bukan YouTube.'}
        
        def update_progress(percent, status):
            if progress_callback:
                try:
                    progress_callback(percent, status)
                except Exception as e:
                    log(f"Callback error: {e}")
            log_event(f"Progress {percent}%: {status}")

        result = {
            'video': None, 'srt': None, 'audio': None, 'title': None,
            'duration': None, 'error_message': None, 'analysis': None
        }
        
        output_dir = Path(output_dir)
        job_dir = Path(output_dir) / job_id
        log(f"Creating job dir: {job_dir}")
        job_dir.mkdir(parents=True, exist_ok=True)
        
        update_progress(5, "Memulai Stage 1 (Analisis)")
        log(f"Stage 1 started for url={url}")
        
        update_progress(10, "Mengunduh video mentah")
        video_file = download_video(job_id, url, job_dir)
        log(f"Download complete: {video_file}")
        
        # Get duration
        log("Getting video duration")
        ffprobe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_file)]
        try:
            dur_res = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=30)
            result['duration'] = float(dur_res.stdout.strip()) if dur_res.stdout.strip() else 0
            log(f"Duration: {result['duration']}")
        except Exception as e: 
            log(f"Duration extraction failed: {e}")

        update_progress(30, "Mengekstrak audio")
        audio_file = extract_audio(job_id, video_file, job_dir)
        result['audio'] = str(audio_file)
        
        update_progress(50, "Mentranskripsi audio (AI)")
        srt_file = transcribe_audio(job_id, audio_file, job_dir)
        result['srt'] = str(srt_file)
        
        update_progress(70, "Menganalisa isi video (AI Topics)")
        from .analyze_pipeline import analyze_srt
        analysis = analyze_srt(job_id, str(srt_file))
        result['analysis'] = analysis
        
        analysis_path = job_dir / 'analysis.json'
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        update_progress(95, "Mengambil informasi video")
        title = get_video_title(url)
        result['title'] = title
        
        update_progress(100, "Analisis Selesai (Siap Pilih Topik)")
        log("Stage 1 success")
        return result

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"FATAL ERROR in Stage 1: {tb}")
        return {'error_message': tb}

def get_video_title(url):
    try:
        cmd = ['yt-dlp', '--get-title', url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.stdout.strip()
    except:
        return "YouTube Video"
