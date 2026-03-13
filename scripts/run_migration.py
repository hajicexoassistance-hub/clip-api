import sqlite3
import os

DB_PATH = 'data/job_history.db'

def run_migration():
    print("Running migration...")
    with sqlite3.connect(DB_PATH) as conn:
        # Add columns if they don't exist (migration for existing DBs)
        try:
            conn.execute('ALTER TABLE analysis_jobs ADD COLUMN title TEXT')
            print("  [OK] Added column 'title'")
        except sqlite3.OperationalError as e:
            print(f"  [INFO] Column 'title' already exists or other error: {e}")
            
        try:
            conn.execute('ALTER TABLE analysis_jobs ADD COLUMN caption TEXT')
            print("  [OK] Added column 'caption'")
        except sqlite3.OperationalError as e:
            print(f"  [INFO] Column 'caption' already exists or other error: {e}")
            
        try:
            conn.execute('ALTER TABLE analysis_jobs ADD COLUMN hashtags TEXT')
            print("  [OK] Added column 'hashtags'")
        except sqlite3.OperationalError as e:
            print(f"  [INFO] Column 'hashtags' already exists or other error: {e}")
            
        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
