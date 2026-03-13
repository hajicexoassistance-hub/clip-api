from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, Query, HTTPException, Depends, Header, Body
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid, datetime, sqlite3, os, json

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Allow all origins for dev, optionally restrict in production via env
allowed_origins = os.environ.get('PORTRAITGEN_CORS_ORIGINS', '*')
allow_origins = [o.strip() for o in allowed_origins.split(',')] if allowed_origins else ['*']
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for output directory
# Note: In production with Nginx, this might be handled by the web server instead.
app.mount("/files", StaticFiles(directory="output"), name="files")

DB_PATH = os.environ.get('PORTRAITGEN_DB_PATH', 'data/job_history.db')
DATA_DIR = os.path.dirname(DB_PATH) or '.'
OUTPUT_DIR = os.environ.get('PORTRAITGEN_OUTPUT_DIR', 'output')
BASE_URL = os.environ.get('PORTRAITGEN_BASE_URL', '/files/')
API_KEY = "test"

# DB setup
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT,
            output TEXT,
            title TEXT,
            media_type TEXT,
            duration INTEGER,
            progress_percent INTEGER,
            error_message TEXT,
            expires_at TEXT,
            created_at TEXT,
            source_url TEXT,
            result_url TEXT,
            srt TEXT,
            audio TEXT
        )''')
        # Mark interrupted jobs as failed on startup
        conn.execute("UPDATE jobs SET status='failed', error_message='Job interrupted by system restart' WHERE status NOT IN ('completed', 'failed')")
        # Clean up expired rows (defensive, even if files already removed)
        conn.execute("DELETE FROM jobs WHERE expires_at IS NOT NULL AND datetime(expires_at) < datetime('now')")
        conn.commit()
init_db()

class JobResponse(BaseModel):
    job_id: str
    status: str
    output: Optional[str]
    title: Optional[str]
    media_type: Optional[str]
    duration: Optional[float]
    progress_percent: Optional[int]
    error_message: Optional[str]
    expires_at: Optional[str]
    created_at: Optional[str]
    source_url: Optional[str]
    result_url: Optional[str]
    srt: Optional[str]
    audio: Optional[str]

def require_api_key(x_api_key: str = Header(None), api_key: Optional[str] = Query(None)):
    # CURRENTLY DISABLED: Set PORTRAITGEN_REQUIRE_API_KEY=true in .env to enable
    if os.environ.get('PORTRAITGEN_REQUIRE_API_KEY', 'false').lower() == 'true':
        expected_key = os.environ.get('PORTRAITGEN_API_KEY', 'test')
        if x_api_key != expected_key and api_key != expected_key:
            raise HTTPException(status_code=403, detail="Invalid or missing API Key")
    return True

# Helper for sequential automated rendering
def _auto_clip_sequencer(job_id, analysis_data):
    from smartcrop.analyze_pipeline import produce_clip
    topics = analysis_data.get('topics', [])
    _log_pipeline(f"Automation: Starting sequential rendering for {len(topics)} topics for job {job_id}")
    
    for i, topic in enumerate(topics):
        try:
            clip_id = str(uuid.uuid4())[:8]
            _log_pipeline(f"Automation: Rendering topic {i}/{len(topics)} (clip_id: {clip_id}) for job {job_id}")
            
            # Track start in analysis_jobs
            now = datetime.datetime.utcnow().isoformat()
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    'INSERT INTO analysis_jobs (job_id, action, status, topics_selected, clip_id, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                    (job_id, 'clip', 'rendering', json.dumps([i]), clip_id, now)
                )
                conn.commit()
            
            # Render the clip
            clip_result = produce_clip(job_id, OUTPUT_DIR, [i], analysis_data, clip_id=clip_id)
            
            # Build response with URL
            clip_url = f"{BASE_URL}{job_id}/{clip_result['clip_filename']}"
            
            # Update analysis_jobs with success
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    'UPDATE analysis_jobs SET status=?, clip_url=?, title=?, caption=?, hashtags=? WHERE clip_id=?',
                    ('completed', clip_url, clip_result.get('draft_judul'), clip_result.get('draft_caption'), clip_result.get('draft_hashtag'), clip_id)
                )
                conn.commit()
            _log_pipeline(f"Automation: Successfully rendered clip {clip_id} for job {job_id}")
        except Exception as clip_err:
            import traceback
            _log_pipeline(f"Automation: Failed to render topic {i} for job {job_id}: {str(clip_err)}\n{traceback.format_exc()}")
            # Update status to failed
            try:
                # clip_id might be defined from earlier in the loop
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        'UPDATE analysis_jobs SET status=?, error_message=? WHERE clip_id=?',
                        ('failed', f"Auto-render failed: {str(clip_err)}", clip_id)
                    )
                    conn.commit()
            except: pass
    
    _log_pipeline(f"Automation: Finished all {len(topics)} topics for job {job_id}")

# Dummy pipeline (replace with actual pipeline call)
def process_pipeline(job_id, url, background_tasks: BackgroundTasks, preset='default'):
    from smartcrop.api_pipeline import run_pipeline
    
    def progress_callback(percent, status_text):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('UPDATE jobs SET progress_percent=?, status=? WHERE job_id=?',
                             (percent, status_text, job_id))
                conn.commit()
        except Exception as e:
            print(f"[CALLBACK-ERROR] {job_id}: {str(e)}")

    try:
        # Initial status
        progress_callback(5, 'Memulai Analisis')
        
        # Run actual pipeline (Stage 1) with callback
        _log_pipeline(f"Starting Stage 1 for job {job_id}")
        from smartcrop.api_pipeline import run_pipeline_stage1
        _log_pipeline(f"Stage 1 code loaded for job {job_id}")
        result = run_pipeline_stage1(job_id, url, OUTPUT_DIR, preset, progress_callback=progress_callback)
        
        # After pipeline, update DB with results
        title = result.get('title')
        duration = result.get('duration')
        error_message = result.get('error_message')
        
        # Mark as completed or failed
        final_status = 'completed' if not error_message else 'failed'
        progress = 100 if not error_message else 0
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''UPDATE jobs SET status=?, progress_percent=?, error_message=?, title=?, duration=? WHERE job_id=?''',
                         (final_status, progress, error_message, title, duration, job_id))
            conn.commit()

        # AUTOMATION: Trigger sequence in background
        if final_status == 'completed' and result.get('analysis'):
            _log_pipeline(f"Automation: Detected topics for job {job_id}. Starting sequencer...")
            background_tasks.add_task(_auto_clip_sequencer, job_id, result['analysis'])
            
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('UPDATE jobs SET status=?, error_message=? WHERE job_id=?',
                         ('failed', err_msg, job_id))
            conn.commit()

class DownloadRequest(BaseModel):
    url: str
    preset: Optional[str] = 'default'

@app.post('/download', response_model=JobResponse, dependencies=[Depends(require_api_key)])
def download(req: DownloadRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(days=1)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO jobs (job_id, status, output, title, media_type, duration, progress_percent, error_message, expires_at, created_at, source_url, result_url, srt, audio)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (job_id, 'queued', req.preset, None, 'video', None, 0, None, expires_at.isoformat(), now.isoformat(), req.url, None, '', ''))
        conn.commit()
    background_tasks.add_task(process_pipeline, job_id, req.url, background_tasks, req.preset)
    return JobResponse(
        job_id=job_id,
        status='queued',
        output=req.preset,
        title=None,
        media_type='video',
        duration=None,
        progress_percent=0,
        error_message=None,
        expires_at=expires_at.isoformat(),
        created_at=now.isoformat(),
        source_url=req.url,
        result_url=None,
        srt='',
        audio=''
    )

@app.get('/job/{job_id}', response_model=JobResponse, dependencies=[Depends(require_api_key)])
def get_job(job_id: str):
    import traceback
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
            if not row:
                return JobResponse(
                    job_id=job_id,
                    status="not_found",
                    output=None,
                    title=None,
                    media_type=None,
                    duration=None,
                    progress_percent=0,
                    error_message="Job not found",
                    expires_at=None,
                    created_at=None,
                    source_url=None,
                    result_url=None,
                    srt=None,
                    audio=None
                )
            job = dict(row)
            
            def to_url(job_id, filename):
                if job_id and filename:
                    return f'{BASE_URL}{job_id}/{filename}'
                return None

            return JobResponse(
                job_id=job.get('job_id', job_id),
                status=job.get('status', 'unknown'),
                output=job.get('output'),
                title=job.get('title'),
                media_type=job.get('media_type'),
                duration=job.get('duration'),
                progress_percent=job.get('progress_percent', 0),
                error_message=job.get('error_message'),
                expires_at=job.get('expires_at'),
                created_at=job.get('created_at'),
                source_url=job.get('source_url'),
                result_url=to_url(job.get('job_id', job_id), 'result.mp4'),
                srt=to_url(job.get('job_id', job_id), 'subtitle.srt'),
                audio=to_url(job.get('job_id', job_id), 'audio.mp3')
            )
    except Exception as e:
        print(f"[JOB-ERROR] {job_id}: {str(e)}", flush=True)
        return JobResponse(
            job_id=job_id,
            status="error",
            output=None,
            title=None,
            media_type=None,
            duration=None,
            progress_percent=0,
            error_message=f"Internal error: {str(e)}",
            expires_at=None,
            created_at=None,
            source_url=None,
            result_url=None,
            srt=None,
            audio=None
        )
@app.get('/job/by-url', response_model=JobResponse, dependencies=[Depends(require_api_key)])
def get_job_by_url(url: str = Query(...)):
    """Cari job berdasarkan source_url untuk mengecek history."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            # Cari job terbaru untuk url tersebut
            row = conn.execute('SELECT * FROM jobs WHERE source_url=? ORDER BY created_at DESC LIMIT 1', (url,)).fetchone()
            if not row:
                return JobResponse(
                    job_id="none",
                    status="not_found",
                    output=None,
                    title=None,
                    media_type=None,
                    duration=None,
                    progress_percent=0,
                    error_message="No history for this URL",
                    expires_at=None,
                    created_at=None,
                    source_url=url,
                    result_url=None,
                    srt=None,
                    audio=None
                )
            
            job = dict(row)
            def to_url(job_id, filename):
                if job_id and filename:
                    return f'{BASE_URL}{job_id}/{filename}'
                return None

            return JobResponse(
                job_id=job.get('job_id'),
                status=job.get('status', 'unknown'),
                output=job.get('output'),
                title=job.get('title'),
                media_type=job.get('media_type'),
                duration=job.get('duration'),
                progress_percent=job.get('progress_percent', 0),
                error_message=job.get('error_message'),
                expires_at=job.get('expires_at'),
                created_at=job.get('created_at'),
                source_url=job.get('source_url'),
                result_url=to_url(job.get('job_id'), 'result.mp4'),
                srt=to_url(job.get('job_id'), 'subtitle.srt'),
                audio=to_url(job.get('job_id'), 'audio.mp3')
            )
    except Exception as e:
        print(f"[JOB-LOOKUP-ERROR]: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/jobs', dependencies=[Depends(require_api_key)])
def list_jobs(limit: int = 50):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        return [dict(row) for row in rows]

# ============================================================
# ANALYZE & CLIP ENDPOINTS
# ============================================================

# Initialize analysis_jobs table
def init_analysis_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS analysis_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            clip_id TEXT,
            clip_url TEXT,
            topics_selected TEXT,
            title TEXT,
            caption TEXT,
            hashtags TEXT,
            error_message TEXT,
            created_at TEXT
        )''')
        # Add columns if they don't exist (migration for existing DBs)
        try:
            conn.execute('ALTER TABLE analysis_jobs ADD COLUMN title TEXT')
            conn.execute('ALTER TABLE analysis_jobs ADD COLUMN caption TEXT')
            conn.execute('ALTER TABLE analysis_jobs ADD COLUMN hashtags TEXT')
        except sqlite3.OperationalError:
            pass # Already exists
        conn.commit()
init_analysis_db()

class ClipRequest(BaseModel):
    job_id: str
    topics: List[int]  # indices of selected topics from /analyze response

def _log_pipeline(msg: str) -> None:
    """Write to pipeline.log for visibility in /logs-ui."""
    from datetime import datetime as dt
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        log_file = os.path.join(DATA_DIR, 'pipeline.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{dt.utcnow().isoformat()}] [ANALYZE] {msg}\n")
    except Exception:
        pass

@app.get('/analyze', dependencies=[Depends(require_api_key)])
def analyze_job(background_tasks: BackgroundTasks, job_id: str = Query(...)):
    """
    Analyze a completed job's SRT to extract topics with virality scores.
    Starts the analysis as a background task and returns immediately.
    """
    from smartcrop.analyze_pipeline import analyze_srt, log_event  # type: ignore[import]

    _log_pipeline(f"Analyze requested for job {job_id}")

    # Verify job exists and is completed
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    srt_path = os.path.join(job_dir, 'subtitle.srt')
    analysis_path = os.path.join(job_dir, 'analysis.json')

    if not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail=f"SRT not found for job {job_id}. Is the job completed?")

    # Return cached analysis if it exists
    if os.path.exists(analysis_path):
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            if not isinstance(cached, dict):
                raise ValueError("Cached analysis is not a dictionary")
            _log_pipeline(f"Returning cached analysis for job {job_id}")
            # Track in DB
            now = datetime.datetime.utcnow().isoformat()
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    'INSERT INTO analysis_jobs (job_id, action, status, created_at) VALUES (?, ?, ?, ?)',
                    (job_id, 'analyze', 'completed_cached', now)
                )
                conn.commit()
            return {"job_id": job_id, "cached": True, **cached}
        except (json.JSONDecodeError, ValueError):
            pass  # Re-analyze if cache is corrupt or null

    # Track start in DB
    now = datetime.datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO analysis_jobs (job_id, action, status, created_at) VALUES (?, ?, ?, ?)',
            (job_id, 'analyze', 'processing', now)
        )
        conn.commit()

    try:
        # Define the background worker
        def _analyze_worker():
            try:
                analysis = analyze_srt(job_id, srt_path)

                # Save analysis to job folder for later use by /clip
                with open(analysis_path, 'w', encoding='utf-8') as f:
                    json.dump(analysis, f, ensure_ascii=False, indent=2)

                # Update DB
                topic_count = len(analysis.get('topics', []))
                _log_pipeline(f"Analysis complete for job {job_id}: {topic_count} topics found")
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        'UPDATE analysis_jobs SET status=? WHERE job_id=? AND action=? AND status=?',
                        ('completed', job_id, 'analyze', 'processing')
                    )
                    conn.commit()
            except Exception as e:
                _log_pipeline(f"Analysis FAILED for {job_id}: {str(e)}")
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        'UPDATE analysis_jobs SET status=?, error_message=? WHERE job_id=? AND action=? AND status=?',
                        ('failed', str(e), job_id, 'analyze', 'processing')
                    )
                    conn.commit()

        background_tasks.add_task(_analyze_worker)
        return {"job_id": job_id, "status": "processing", "message": "Analysis started in background"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Startup logic failed: {str(e)}")

@app.post('/clip', dependencies=[Depends(require_api_key)])
def clip_job(req: ClipRequest, background_tasks: BackgroundTasks):
    """
    Cut & merge video segments from selected topics.
    Runs asynchronously; polls /job/{job_id} for results.
    """
    from smartcrop.analyze_pipeline import render_clip, log_event  # type: ignore[import]

    _log_pipeline(f"Clip requested for job {req.job_id}, topics: {req.topics}")

    job_dir = os.path.join(OUTPUT_DIR, req.job_id)
    analysis_path = os.path.join(job_dir, 'analysis.json')

    # Validate
    # Result video is no longer a prerequisite for clipping in Stage 2
    # We only need analysis.json and the raw video (which is checked inside produce_clip)

    if not os.path.exists(analysis_path):
        raise HTTPException(status_code=400, detail="Run /analyze first before clipping")

    if not req.topics:
        raise HTTPException(status_code=400, detail="No topics selected")

    # Load analysis
    try:
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read analysis: {str(e)}")

    # Track start in DB
    now = datetime.datetime.utcnow().isoformat()
    topics_str = json.dumps(req.topics)
    clip_id = str(uuid.uuid4())[:8]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO analysis_jobs (job_id, action, status, topics_selected, clip_id, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (req.job_id, 'clip', 'rendering', topics_str, clip_id, now)
        )
        conn.commit()

    try:
        def _clip_worker():
            try:
                # Panggil produce_clip (Stage 2)
                clip_result = render_clip(req.job_id, OUTPUT_DIR, req.topics, analysis_data, clip_id=clip_id)

                # Build response with URL
                clip_url = f"{BASE_URL}{req.job_id}/{clip_result['clip_filename']}"

                # Update DB
                _log_pipeline(f"Clip complete for job {req.job_id}: {clip_result['clip_filename']}")
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        'UPDATE analysis_jobs SET status=?, clip_url=?, title=?, caption=?, hashtags=? WHERE clip_id=? AND action=? AND status=?',
                        ('completed', clip_url, clip_result.get('draft_judul'), clip_result.get('draft_caption'), clip_result.get('draft_hashtag'), clip_id, 'clip', 'rendering')
                    )
                    conn.commit()
            except Exception as e:
                _log_pipeline(f"Clip FAILED for {req.job_id}: {str(e)}")
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        'UPDATE analysis_jobs SET status=?, error_message=? WHERE clip_id=? AND action=? AND status=?',
                        ('failed', str(e), clip_id, 'clip', 'rendering')
                    )
                    conn.commit()

        background_tasks.add_task(_clip_worker)
        return {
            "job_id": req.job_id,
            "clip_id": clip_id,
            "status": "processing",
            "message": "Clip rendering started in background"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clip initialization failed: {str(e)}")


@app.get('/job/{job_id}/results', dependencies=[Depends(require_api_key)])
def get_job_results(job_id: str):
    """
    Get all generated clips and their metadata for a specific job.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM analysis_jobs WHERE job_id=? AND action=? AND status=?',
                (job_id, 'clip', 'completed')
            ).fetchall()
            
            # Also get source video info
            job_row = conn.execute('SELECT source_url, title FROM jobs WHERE job_id=?', (job_id,)).fetchone()
            source_info = dict(job_row) if job_row else {}

            results = []
            for row in rows:
                item = dict(row)
                results.append({
                    "clip_id": item.get("clip_id"),
                    "url": item.get("clip_url"),
                    "title": item.get("title"),
                    "caption": item.get("caption"),
                    "hashtags": item.get("hashtags"),
                    "source_url": source_info.get("source_url"),
                    "source_title": source_info.get("title"),
                    "created_at": item.get("created_at")
                })
            
            return {
                "job_id": job_id,
                "total_clips": len(results),
                "clips": results
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/clip/{clip_id}', dependencies=[Depends(require_api_key)])
def get_clip_status(clip_id: str):
    """
    Get status and metadata for a specific clip_id.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM analysis_jobs WHERE clip_id=?', (clip_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Clip not found")
            
            item = dict(row)
            if item.get('status') != 'completed':
                return {
                    "clip_id": clip_id,
                    "status": item.get('status'),
                    "error": item.get('error_message'),
                    "message": "Clip is still processing or failed" if item.get('status') != 'failed' else "Clip failed"
                }

            return {
                "clip_id": clip_id,
                "status": "completed",
                "url": item.get("clip_url"),
                "title": item.get("title"),
                "caption": item.get("caption"),
                "hashtags": item.get("hashtags"),
                "created_at": item.get("created_at")
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/job/{job_id}/clip-status', dependencies=[Depends(require_api_key)])
def get_job_clip_status(job_id: str):
    """
    Get a summary of the clipping progress for a specific job_id.
    Shows total topics, completed, failed, and rendering counts.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            
            # 1. Get Stage 1 status & source info
            job_row = conn.execute('SELECT status, source_url FROM jobs WHERE job_id=?', (job_id,)).fetchone()
            if not job_row:
                raise HTTPException(status_code=404, detail="Job not found")
            stage1_status = job_row['status']
            source_url = job_row['source_url']

            # 2. Get total expected topics from analysis.json
            job_dir = os.path.join(OUTPUT_DIR, job_id)
            analysis_path = os.path.join(job_dir, 'analysis.json')
            total_expected = 0
            if os.path.exists(analysis_path):
                try:
                    with open(analysis_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        total_expected = len(data.get('topics', []))
                except:
                    pass

            # 3. Get progress from analysis_jobs
            rows = conn.execute(
                'SELECT * FROM analysis_jobs WHERE job_id=? AND action=?',
                (job_id, 'clip')
            ).fetchall()
            
            results = [dict(r) for r in rows]
            completed = [r for r in results if r['status'] == 'completed']
            failed = [r for r in results if r['status'] == 'failed']
            rendering = [r for r in results if r['status'] == 'rendering']
            
            # 4. Determine if finished
            # Finished if Stage 1 is done AND (all clips are done OR Stage 1 failed and no clips will be processed)
            is_finished = False
            if stage1_status == 'completed':
                if total_expected > 0 and (len(completed) + len(failed) == total_expected):
                    is_finished = True
                elif total_expected == 0:
                    is_finished = True # No topics to process
            elif stage1_status == 'failed':
                is_finished = True

            return {
                "job_id": job_id,
                "stage1_status": stage1_status,
                "source_url": source_url,
                "total_topics": total_expected,
                "total_clips_initialized": len(results),
                "completed": len(completed),
                "failed": len(failed),
                "rendering": len(rendering),
                "is_finished": is_finished,
                "clips": [
                    {
                        "clip_id": r.get("clip_id"),
                        "status": r.get("status"),
                        "url": r.get("clip_url"),
                        "error": r.get("error_message"),
                        "title": r.get("title"),
                        "caption": r.get("caption"),
                        "hashtags": r.get("hashtags")
                    } for r in results
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/logs', dependencies=[Depends(require_api_key)])
def get_logs(lines: int = Query(100)):
    log_file = os.path.join(DATA_DIR, 'pipeline.log')
    if not os.path.exists(log_file):
        return {"logs": ["Log file not found."]}
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.readlines()
            lines_to_show = int(lines)
            return {"logs": content[-lines_to_show:]}
    except Exception as e:
        print(f"[LOG-READ-ERROR] {str(e)}")
        return {"logs": [f"Error reading logs: {str(e)}"]}

@app.get('/logs-ui', response_class=HTMLResponse, dependencies=[Depends(require_api_key)])
def logs_ui():
    html_content = r"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portrait Generator - Log Monitor</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #0f172a;
                --surface: #1e293b;
                --text: #f8fafc;
                --accent: #38bdf8;
                --border: #334155;
            }
            body { 
                margin: 0; 
                padding: 20px; 
                background: var(--bg); 
                color: var(--text); 
                font-family: 'Inter', sans-serif;
                overflow: hidden;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 1px solid var(--border);
            }
            h1 { font-size: 1.25rem; font-weight: 600; margin: 0; color: var(--accent); }
            .status-badge {
                background: #10b981;
                color: white;
                padding: 4px 10px;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.7; }
                100% { opacity: 1; }
            }
            .log-container {
                flex: 1;
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 15px;
                font-family: 'Fira Code', monospace;
                font-size: 0.85rem;
                line-height: 1.5;
                overflow-y: auto;
                white-space: pre-wrap;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
            }
            .log-line { margin-bottom: 2px; border-left: 2px solid transparent; padding-left: 10px; }
            .log-line:hover { background: rgba(255,255,255,0.03); border-left-color: var(--accent); }
            .timestamp { color: #94a3b8; margin-right: 10px; font-size: 0.75rem; }
            .pill { 
                display: inline-block; 
                padding: 2px 6px; 
                border-radius: 4px; 
                font-size: 0.7rem; 
                font-weight: 600; 
                margin-right: 5px;
                text-transform: uppercase;
            }
            .pill-info { background: #3b82f6; color: white; }
            .pill-error { background: #ef4444; color: white; }
            .pill-pipeline { background: #a855f7; color: white; }
            .controls { display: flex; gap: 10px; }
            button {
                background: var(--surface);
                border: 1px solid var(--border);
                color: var(--text);
                padding: 6px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.8rem;
                transition: all 0.2s;
            }
            button:hover { background: var(--border); border-color: var(--accent); }
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: var(--bg); }
            ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #475569; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Pipeline Monitor <span style="font-size:0.8rem; font-weight:400; color:var(--text); opacity:0.6;">v1.0</span></h1>
            <div class="controls">
                <div id="status-badge" class="status-badge">LIVE MONITORING</div>
                <button onclick="fetchLogs()">Refresh Now</button>
            </div>
        </div>
        <div id="log-display" class="log-container">Loading logs...</div>

        <script>
            let autoScroll = true;
            const logDisplay = document.getElementById('log-display');

            async function fetchLogs() {
                try {
                    const urlParams = new URLSearchParams(window.location.search);
                    const apiKey = urlParams.get('api_key') || '';
                    const response = await fetch(`/api/logs?lines=150&api_key=${apiKey}&_t=${Date.now()}`);
                    const data = await response.json();
                    document.getElementById('status-badge').innerText = 'LIVE: ' + new Date().toLocaleTimeString();
                    renderLogs(data.logs);
                } catch (err) {
                    logDisplay.innerHTML = '<span class="pill pill-error">ERROR</span> Gagal mengambil log: ' + err;
                }
            }

            function renderLogs(logs) {
                if (!logs || logs.length === 0) {
                    logDisplay.innerHTML = "No logs yet.";
                    return;
                }
                
                const html = logs.map(line => {
                    let processedLine = line.trim();
                    let timestamp = "";
                    let type = "info";
                    
                    // Match [ISO_TIMESTAMP]
                    const tsMatch = processedLine.match(/^\[(.*?)\]\s*(.*)/);
                    if (tsMatch) {
                        timestamp = `<span class="timestamp">${tsMatch[1].split('T')[1].split('.')[0]} UTC</span>`;
                        processedLine = tsMatch[2];
                    }

                    if (processedLine.includes('[ERROR]')) type = "error";
                    if (processedLine.includes('[PIPELINE]')) type = "pipeline";

                    const pill = `<span class="pill pill-${type}">${type}</span>`;
                    
                    return `<div class="log-line">${timestamp}${pill} ${processedLine}</div>`;
                }).join('');
                
                logDisplay.innerHTML = html;
                
                if (autoScroll) {
                    logDisplay.scrollTop = logDisplay.scrollHeight;
                }
            }

            // Auto refresh every 3 seconds
            setInterval(fetchLogs, 3000);
            fetchLogs();

            // Detect manual scroll to disable auto-scroll
            logDisplay.addEventListener('scroll', () => {
                const isAtBottom = logDisplay.scrollHeight - logDisplay.scrollTop <= logDisplay.clientHeight + 50;
                autoScroll = isAtBottom;
            });
        </script>
    </body>
    </html>
    """
    return html_content
