import os
import json
import sqlite3
from datetime import datetime, timedelta, date

try:
    from .database import get_db, init_db
except (ImportError, ValueError):
    from database import get_db, init_db

def seed_database():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # 1. Seed Workers (No demo workers; only new registrations)
    workers_data = []
    if workers_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO workers 
            (id, name, role, department, site, training_valid, cert_valid, helmet_assigned, vest_assigned, goggles_assigned, gloves_assigned, shoes_assigned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, workers_data)

    # 2. Seed Machines
    today = date.today()
    machines_data = [
        ("M101", "Main Gas Compressor C-12", "Site A (Duliajan)", 
         (today - timedelta(days=75)).isoformat(), (today - timedelta(days=15)).isoformat(), 
         94, "OVERDUE", 0, ""),
        ("M102", "High-Pressure Mud Pump P-07", "Site B (Moran)", 
         (today - timedelta(days=69)).isoformat(), (today - timedelta(days=9)).isoformat(), 
         86, "OVERDUE", 1, "Simulated Interlock: High vibration detected on drive bearing"),
        ("M103", "Main Power Generator G-04", "Site C (Digboi)", 
         (today - timedelta(days=35)).isoformat(), (today + timedelta(days=2)).isoformat(), 
         65, "OPERATIONAL", 0, ""),
        ("M104", "ESD Wellhead Valve V-19", "Site A (Duliajan)", 
         (today - timedelta(days=40)).isoformat(), (today + timedelta(days=8)).isoformat(), 
         45, "OPERATIONAL", 0, ""),
        ("M105", "Rig Mast Drilling Hoist H-02", "Site B (Moran)", 
         (today - timedelta(days=64)).isoformat(), (today - timedelta(days=4)).isoformat(), 
         89, "OVERDUE", 0, ""),
        ("M106", "Crude Oil Separator S-01", "Site A (Duliajan)", 
         (today - timedelta(days=25)).isoformat(), (today + timedelta(days=14)).isoformat(), 
         38, "OPERATIONAL", 0, "")
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO machines 
        (id, name, site, last_maintenance, due_date, base_risk, status, locked, lock_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, machines_data)

    # 3. Seed Site Conditions
    site_conditions_data = [
        ("Site A", "Site A (Duliajan Central Field)", 31.5, 82, "Heavy Rain / Thunderstorm", 28.4, "CAUTION", 1.25),
        ("Site B", "Site B (Moran Wellhead Complex)", 34.0, 65, "Clear", 12.0, "SUITABLE", 1.0),
        ("Site C", "Site C (Digboi Refinery & Storage)", 30.0, 75, "Light Drizzle", 16.5, "SUITABLE", 1.1)
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO site_conditions 
        (site_id, site_name, temperature, humidity, rain_status, wind_speed, condition_status, risk_multiplier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, site_conditions_data)

    # 4. Seed Reports (No demo reports; real reports created by workers)
    cursor.execute("SELECT COUNT(*) FROM reports")
    # Clean zero reports default
    seed_reports = []
    if seed_reports:
        cursor.executemany("""
            INSERT INTO reports 
            (report_uid, worker_id, site, location, activity, machine_id, report_type, input_channel, raw_text, 
             hazard, energy_source, worker_exposure, barrier_status, sif_potential, confidence, risk_score, 
             risk_level, risk_drivers, precautions, solution, status, created_at, synced_offline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_reports)

    # 5. Seed Reviews & Feedback Logs (Clean zero default)
    cursor.execute("SELECT COUNT(*) FROM hse_reviews")

    # 6. Seed Notifications (Clean zero default)
    cursor.execute("SELECT COUNT(*) FROM notifications")

    # 7. Seed System Staff Users with Passwords (No demo workers; workers register themselves)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    users_data = [
        ("hse", "hse123", "Ankur Sharma", "HSE OFFICER", "Corporate HSE Directorate", "All OIL Fields", "+91 98765 11223", "OIL Field Headquarters, Duliajan", "HSE01", 1, now_str),
        ("admin", "admin123", "Dr. Prabal Saikia", "ADMIN", "Digital Safety Operations", "Central Command", "+91 98765 99887", "OIL IT Center, Duliajan", "ADM01", 1, now_str),
        ("mechanic", "mech123", "Bikash Borah", "MECHANIC", "Heavy Equipment Maintenance", "Workshop Bay 3", "+91 98765 77665", "East Workshop Enclave, Assam", "MEC01", 1, now_str)
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO users (username, password, name, role, department, site, phone, address, worker_id, face_enrolled, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, users_data)

    conn.commit()
    conn.close()
    print("Database successfully seeded with realistic Oil India Limited operational data and registered user accounts.")

if __name__ == "__main__":
    seed_database()
