import sqlite3
import os
import json
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sifguard.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn

def init_db():
    conn = get_db()
    conn.execute("PRAGMA journal_mode = WAL;")
    cursor = conn.cursor()
    
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS workers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT NOT NULL,
        site TEXT NOT NULL,
        training_valid INTEGER NOT NULL DEFAULT 1,
        cert_valid INTEGER NOT NULL DEFAULT 1,
        helmet_assigned INTEGER NOT NULL DEFAULT 1,
        vest_assigned INTEGER NOT NULL DEFAULT 1,
        goggles_assigned INTEGER NOT NULL DEFAULT 1,
        gloves_assigned INTEGER NOT NULL DEFAULT 1,
        shoes_assigned INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS machines (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        site TEXT NOT NULL,
        last_maintenance TEXT NOT NULL,
        due_date TEXT NOT NULL,
        base_risk INTEGER NOT NULL DEFAULT 50,
        status TEXT NOT NULL DEFAULT 'OPERATIONAL',
        locked INTEGER NOT NULL DEFAULT 0,
        lock_reason TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_uid TEXT UNIQUE NOT NULL,
        worker_id TEXT NOT NULL,
        site TEXT NOT NULL,
        location TEXT NOT NULL,
        activity TEXT NOT NULL,
        machine_id TEXT DEFAULT '',
        report_type TEXT NOT NULL,
        input_channel TEXT NOT NULL DEFAULT 'Text',
        raw_text TEXT NOT NULL,
        hazard TEXT NOT NULL,
        energy_source TEXT NOT NULL,
        worker_exposure INTEGER NOT NULL DEFAULT 0,
        barrier_status TEXT NOT NULL,
        sif_potential INTEGER NOT NULL DEFAULT 0,
        confidence REAL NOT NULL DEFAULT 0.85,
        risk_score INTEGER NOT NULL,
        risk_level TEXT NOT NULL,
        risk_drivers TEXT NOT NULL,
        precautions TEXT NOT NULL,
        solution TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'AI ANALYZED',
        image_data TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        synced_offline INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS hse_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        officer_name TEXT NOT NULL,
        decision TEXT NOT NULL,
        original_risk INTEGER NOT NULL,
        corrected_risk INTEGER NOT NULL,
        original_sif INTEGER NOT NULL,
        corrected_sif INTEGER NOT NULL,
        action_assigned TEXT NOT NULL,
        responsible_person TEXT NOT NULL,
        due_date TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS feedback_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        original_analysis TEXT NOT NULL,
        corrected_analysis TEXT NOT NULL,
        feedback_note TEXT NOT NULL,
        model_version TEXT NOT NULL DEFAULT 'v1.0-hybrid',
        timestamp TEXT NOT NULL,
        FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS site_conditions (
        site_id TEXT PRIMARY KEY,
        site_name TEXT NOT NULL,
        temperature REAL NOT NULL,
        humidity INTEGER NOT NULL,
        rain_status TEXT NOT NULL,
        wind_speed REAL NOT NULL,
        condition_status TEXT NOT NULL,
        risk_multiplier REAL NOT NULL DEFAULT 1.0
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'INFO',
        timestamp TEXT NOT NULL,
        read_status INTEGER NOT NULL DEFAULT 0,
        report_id INTEGER DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT DEFAULT '',
        site TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        address TEXT DEFAULT '',
        worker_id TEXT DEFAULT '',
        face_enrolled INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS mechanic_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pass_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        phone TEXT NOT NULL,
        machine_assigned TEXT NOT NULL,
        entry_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE'
    );

    CREATE TABLE IF NOT EXISTS repair_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id TEXT NOT NULL,
        worker_id TEXT NOT NULL,
        worker_name TEXT NOT NULL,
        repair_status TEXT NOT NULL,
        observations TEXT NOT NULL,
        verified_safe INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS gate_access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id TEXT NOT NULL,
        worker_name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        access_status TEXT NOT NULL,
        missing_ppe TEXT DEFAULT '',
        camera_source TEXT DEFAULT 'Face Gate',
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()

    # Migration: Ensure image_data exists in reports table
    try:
        cursor.execute("ALTER TABLE reports ADD COLUMN image_data TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    # Performance and Data Integrity Indices
    cursor.executescript("""
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE);
    CREATE INDEX IF NOT EXISTS idx_users_worker_id ON users(worker_id COLLATE NOCASE);
    CREATE INDEX IF NOT EXISTS idx_workers_id ON workers(id COLLATE NOCASE);
    CREATE INDEX IF NOT EXISTS idx_reports_worker_id ON reports(worker_id);
    CREATE INDEX IF NOT EXISTS idx_reports_uid ON reports(report_uid);
    CREATE INDEX IF NOT EXISTS idx_gate_logs_worker ON gate_access_logs(worker_id);
    CREATE INDEX IF NOT EXISTS idx_hse_reviews_report ON hse_reviews(report_id);
    """)
    conn.commit()

    conn.close()
