import sqlite3
import os
import json

DB_PATH = 'data/job_history.db'

def test_db_migration():
    print("Testing DB migration...")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        # Check columns in analysis_jobs
        cursor = conn.execute("PRAGMA table_info(analysis_jobs)")
        columns = [row['name'] for row in cursor.fetchall()]
        print(f"Columns in analysis_jobs: {columns}")
        
        expected = ['title', 'caption', 'hashtags']
        for col in expected:
            if col in columns:
                print(f"  [OK] Column '{col}' exists.")
            else:
                print(f"  [FAIL] Column '{col}' is missing!")

def test_mock_clip_save():
    print("\nTesting mock clip save...")
    job_id = "test-job-id"
    clip_id = "test-clip"
    clip_url = "http://localhost:8000/files/test-job-id/clip_test.mp4"
    title = "Test Title"
    caption = "Test Caption"
    hashtags = "#test #smartcrop"
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO analysis_jobs (job_id, action, status, clip_id, clip_url, title, caption, hashtags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (job_id, 'clip', 'completed', clip_id, clip_url, title, caption, hashtags, "2026-03-12T00:00:00")
        )
        conn.commit()
    
    # Verify retrieval
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM analysis_jobs WHERE clip_id=?', (clip_id,)).fetchone()
        if row:
            print(f"  [OK] Saved clip found. Title: {row['title']}")
            if row['caption'] == caption and row['hashtags'] == hashtags:
                print("  [OK] Metadata matches.")
            else:
                print(f"  [FAIL] Metadata mismatch! Saved: {row['caption']} vs Expected: {caption}")
        else:
            print("  [FAIL] Saved clip not found!")

if __name__ == "__main__":
    test_db_migration()
    test_mock_clip_save()
