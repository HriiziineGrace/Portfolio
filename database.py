"""
Database module for Government Job Deadline Guardian.
Uses SQLite for persistent storage of job vacancies, duplicate detection logs,
and reminder subscriptions.
"""

import sqlite3
import os
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_DB_PATH = os.path.join(BASE_DIR, "job_guardian.db")

def get_db_path():
    """Resolve database path, handling read-only environments like Vercel."""
    if os.environ.get("VERCEL"):
        vercel_db_path = "/tmp/job_guardian.db"
        if not os.path.exists(vercel_db_path) and os.path.exists(ORIGINAL_DB_PATH):
            try:
                shutil.copy2(ORIGINAL_DB_PATH, vercel_db_path)
            except Exception as e:
                print(f"Error copying DB to /tmp: {e}")
        return vercel_db_path
    return ORIGINAL_DB_PATH

DB_PATH = get_db_path()

def get_db_connection():
    """Get a connection to SQLite database with row factory enabled."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Jobs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hash_fingerprint TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        organization TEXT NOT NULL,
        advt_no TEXT NOT NULL,
        category TEXT NOT NULL,
        state TEXT NOT NULL,
        vacancies INTEGER NOT NULL DEFAULT 1,
        salary_pay TEXT,
        min_age INTEGER NOT NULL DEFAULT 18,
        max_age INTEGER NOT NULL DEFAULT 35,
        min_qualification TEXT NOT NULL,
        qualification_details TEXT,
        stream_specialization TEXT DEFAULT 'Any',
        age_relaxation_json TEXT,
        application_start TEXT,
        deadline TEXT NOT NULL,
        original_deadline TEXT,
        is_extended INTEGER DEFAULT 0,
        corrigendum_note TEXT,
        application_fee TEXT,
        official_notification_url TEXT NOT NULL,
        official_apply_url TEXT NOT NULL,
        source_portal TEXT NOT NULL,
        is_verified INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # Duplicate / Corrigendum Audit Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS duplicate_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incoming_title TEXT NOT NULL,
        incoming_org TEXT NOT NULL,
        incoming_advt TEXT NOT NULL,
        matched_job_id INTEGER,
        status TEXT NOT NULL,
        match_reason TEXT NOT NULL,
        detected_at TEXT NOT NULL
    );
    """)

    # Reminder Subscriptions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        job_id INTEGER,
        notify_before_days INTEGER DEFAULT 3,
        qualification_filter TEXT,
        category_filter TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    );
    """)

    # Sent Alert History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sent_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        job_id INTEGER NOT NULL,
        job_title TEXT NOT NULL,
        deadline TEXT NOT NULL,
        days_left REAL NOT NULL,
        sent_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Simulated Sent',
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    );
    """)

    # Indexes for fast search & filtering
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_deadline ON jobs(deadline);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_qualification ON jobs(min_qualification);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(hash_fingerprint);")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
