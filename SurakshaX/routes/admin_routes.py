import os
import io
import csv
import json
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, session, render_template, Response

from database.database import get_db, DB_PATH
from database.seed import seed_database
from Ai_model.face_engine import get_face_engine

admin_bp = Blueprint('admin_bp', __name__)
face_engine = get_face_engine()

MASTER_ADMIN_USERNAME = "admin"
MASTER_ADMIN_PASSWORD = "admin123"
MASTER_ADMIN_PIN = "9988"

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Check session
        if session.get("is_admin") is True:
            return f(*args, **kwargs)
        
        # 2. Check header or query token/PIN
        auth_pin = request.headers.get("X-Admin-Pin") or request.headers.get("X-Admin-Key") or request.args.get("pin")
        if auth_pin == MASTER_ADMIN_PIN or auth_pin == MASTER_ADMIN_PASSWORD:
            return f(*args, **kwargs)

        # 3. Check JSON payload pin
        if request.is_json:
            json_pin = request.get_json().get("admin_pin") if request.get_json() else None
            if json_pin == MASTER_ADMIN_PIN or json_pin == MASTER_ADMIN_PASSWORD:
                return f(*args, **kwargs)

        return jsonify({
            "success": False,
            "error": "Unauthorized: Master Admin Authentication Required. Please login with admin credentials."
        }), 401
    return decorated_function

# ==============================================================================
# HTML & AUTH ROUTES
# ==============================================================================

@admin_bp.route('/admin')
def admin_page():
    """Serves the Master Data Admin Portal."""
    return render_template("admin.html")

@admin_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    pin = (data.get("pin") or "").strip()

    if (username.lower() == MASTER_ADMIN_USERNAME.lower() and password == MASTER_ADMIN_PASSWORD) or pin == MASTER_ADMIN_PIN or password == MASTER_ADMIN_PASSWORD:
        session["is_admin"] = True
        session["user_role"] = "ADMIN"
        session["user_name"] = "Master Safety Administrator"
        return jsonify({
            "success": True,
            "message": "Master Admin Access Granted",
            "admin": {
                "username": MASTER_ADMIN_USERNAME,
                "role": "ADMIN",
                "name": "Master Safety Administrator"
            }
        })

    return jsonify({"success": False, "error": "Invalid Administrator credentials or Master PIN."}), 401

@admin_bp.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop("is_admin", None)
    return jsonify({"success": True, "message": "Master Admin session ended."})

@admin_bp.route('/api/admin/check_auth', methods=['GET'])
def check_auth():
    auth_pin = request.headers.get("X-Admin-Pin") or request.args.get("pin")
    is_authed = bool(session.get("is_admin") or auth_pin in (MASTER_ADMIN_PIN, MASTER_ADMIN_PASSWORD))
    return jsonify({"authenticated": is_authed})

# ==============================================================================
# WORKERS CRUD & BIOMETRICS
# ==============================================================================

@admin_bp.route('/api/admin/workers', methods=['GET'])
@admin_required
def list_workers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers ORDER BY id ASC")
    rows = cursor.fetchall()
    
    # Check users table for face enrollments
    cursor.execute("SELECT worker_id, face_enrolled, phone, address FROM users WHERE role = 'WORKER'")
    user_rows = {u["worker_id"]: dict(u) for u in cursor.fetchall() if u["worker_id"]}
    conn.close()

    workers = []
    compliant_count = 0

    for r in rows:
        w = dict(r)
        user_meta = user_rows.get(w["id"], {})
        w["face_enrolled"] = bool(user_meta.get("face_enrolled", 0))
        w["phone"] = user_meta.get("phone", "")
        w["address"] = user_meta.get("address", "")
        
        # Check turnstile compliance
        missing = []
        if not w["training_valid"]: missing.append("Training Expired")
        if not w["cert_valid"]: missing.append("Cert Expired")
        if not w["helmet_assigned"]: missing.append("Helmet")
        if not w["vest_assigned"]: missing.append("Safety Vest")
        if not w["gloves_assigned"]: missing.append("Gloves")
        if not w["shoes_assigned"]: missing.append("Boots")

        is_compliant = len(missing) == 0
        w["is_compliant"] = is_compliant
        w["missing_items"] = missing
        if is_compliant:
            compliant_count += 1

        workers.append(w)

    return jsonify({
        "success": True,
        "total": len(workers),
        "compliant_count": compliant_count,
        "workers": workers
    })

@admin_bp.route('/api/admin/workers', methods=['POST'])
@admin_required
def add_worker():
    data = request.get_json() or {}
    worker_id = (data.get("id") or "").strip().upper()
    name = (data.get("name") or "").strip()
    role = (data.get("role") or "Field Operator").strip()
    department = (data.get("department") or "Drilling & Production").strip()
    site = (data.get("site") or "Site A (Duliajan)").strip()

    if not worker_id or not name:
        return jsonify({"success": False, "error": "Worker ID and Full Name are mandatory."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM workers WHERE id = ?", (worker_id,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": f"Worker with ID '{worker_id}' already exists."}), 409

    cursor.execute("""
        INSERT INTO workers 
        (id, name, role, department, site, training_valid, cert_valid, helmet_assigned, vest_assigned, goggles_assigned, gloves_assigned, shoes_assigned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        worker_id, name, role, department, site,
        int(data.get("training_valid", 1)),
        int(data.get("cert_valid", 1)),
        int(data.get("helmet_assigned", 1)),
        int(data.get("vest_assigned", 1)),
        0, # goggles removed
        int(data.get("gloves_assigned", 1)),
        int(data.get("shoes_assigned", 1))
    ))

    # Also register in users table
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT OR REPLACE INTO users (username, password, name, role, department, site, phone, address, worker_id, face_enrolled, created_at)
        VALUES (?, ?, ?, 'WORKER', ?, ?, ?, ?, ?, 0, ?)
    """, (
        worker_id.lower(), "worker123", name, department, site,
        data.get("phone", ""), data.get("address", ""), worker_id, now_str
    ))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Worker '{name}' ({worker_id}) added successfully."})

@admin_bp.route('/api/admin/workers/<worker_id>', methods=['PUT'])
@admin_required
def update_worker(worker_id):
    worker_id = worker_id.strip().upper()
    data = request.get_json() or {}

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Worker '{worker_id}' not found."}), 404

    current = dict(row)
    name = data.get("name", current["name"]).strip()
    role = data.get("role", current["role"]).strip()
    department = data.get("department", current["department"]).strip()
    site = data.get("site", current["site"]).strip()
    training_valid = int(data.get("training_valid", current["training_valid"]))
    cert_valid = int(data.get("cert_valid", current["cert_valid"]))
    helmet_assigned = int(data.get("helmet_assigned", current["helmet_assigned"]))
    vest_assigned = int(data.get("vest_assigned", current["vest_assigned"]))
    gloves_assigned = int(data.get("gloves_assigned", current["gloves_assigned"]))
    shoes_assigned = int(data.get("shoes_assigned", current["shoes_assigned"]))

    cursor.execute("""
        UPDATE workers 
        SET name = ?, role = ?, department = ?, site = ?,
            training_valid = ?, cert_valid = ?,
            helmet_assigned = ?, vest_assigned = ?, gloves_assigned = ?, shoes_assigned = ?
        WHERE id = ?
    """, (
        name, role, department, site,
        training_valid, cert_valid,
        helmet_assigned, vest_assigned, gloves_assigned, shoes_assigned,
        worker_id
    ))

    # Sync name/dept/site to users table
    cursor.execute("""
        UPDATE users SET name = ?, department = ?, site = ? WHERE worker_id = ?
    """, (name, department, site, worker_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Worker '{worker_id}' details updated successfully."})

@admin_bp.route('/api/admin/workers/<worker_id>', methods=['DELETE'])
@admin_required
def delete_worker(worker_id):
    worker_id = worker_id.strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
    deleted_w = cursor.rowcount
    cursor.execute("DELETE FROM users WHERE worker_id = ? OR username = ?", (worker_id, worker_id.lower()))
    conn.commit()
    conn.close()

    # Clean biometrics from face engine
    face_clean = face_engine.delete_worker_registration(worker_id)

    if deleted_w == 0:
        return jsonify({"success": False, "error": f"Worker '{worker_id}' not found."}), 404

    return jsonify({
        "success": True,
        "message": f"Worker '{worker_id}' and biometric samples deleted successfully.",
        "biometrics_purged": face_clean.get("purged_samples", 0)
    })

@admin_bp.route('/api/admin/workers/toggle_clearance/<worker_id>', methods=['POST'])
@admin_required
def toggle_worker_clearance(worker_id):
    worker_id = worker_id.strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Worker '{worker_id}' not found."}), 404

    w = dict(row)
    # If all items are 1, revoke by setting training_valid = 0; else grant all
    currently_compliant = (w["training_valid"] and w["cert_valid"] and w["helmet_assigned"] and 
                           w["vest_assigned"] and w["gloves_assigned"] and w["shoes_assigned"])

    if currently_compliant:
        cursor.execute("UPDATE workers SET training_valid = 0 WHERE id = ?", (worker_id,))
        new_status = "REVOKED"
    else:
        cursor.execute("""
            UPDATE workers 
            SET training_valid = 1, cert_valid = 1, helmet_assigned = 1, vest_assigned = 1, gloves_assigned = 1, shoes_assigned = 1
            WHERE id = ?
        """, (worker_id,))
        new_status = "GRANTED"

    conn.commit()
    conn.close()

    return jsonify({"success": True, "worker_id": worker_id, "clearance_status": new_status})

@admin_bp.route('/api/admin/workers/clear_all', methods=['POST'])
@admin_required
def clear_all_workers():
    # Purge face samples and embeddings
    face_res = face_engine.clear_all_registrations()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workers")
    deleted_workers = cursor.rowcount
    cursor.execute("DELETE FROM users WHERE role = 'WORKER'")
    deleted_users = cursor.rowcount
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Purged all {deleted_workers} workers and {face_res.get('purged_samples', 0)} face biometric samples."
    })

# ==============================================================================
# MACHINES CRUD & INTERLOCKS
# ==============================================================================

@admin_bp.route('/api/admin/machines', methods=['GET'])
@admin_required
def list_admin_machines():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machines ORDER BY base_risk DESC")
    rows = cursor.fetchall()
    conn.close()

    today = date.today()
    machines = []
    locked_count = 0
    overdue_count = 0

    for r in rows:
        m = dict(r)
        try:
            due = date.fromisoformat(m["due_date"])
            days = (due - today).days
        except Exception:
            days = 0

        m["days_remaining"] = days
        m["is_overdue"] = days < 0
        if days < 0:
            overdue_count += 1
        if m["locked"]:
            locked_count += 1

        machines.append(m)

    return jsonify({
        "success": True,
        "total": len(machines),
        "locked_count": locked_count,
        "overdue_count": overdue_count,
        "machines": machines
    })

@admin_bp.route('/api/admin/machines', methods=['POST'])
@admin_required
def add_machine():
    data = request.get_json() or {}
    machine_id = (data.get("id") or "").strip().upper()
    name = (data.get("name") or "").strip()
    site = (data.get("site") or "Site A (Duliajan)").strip()
    last_maint = data.get("last_maintenance") or date.today().isoformat()
    due_date = data.get("due_date") or (date.today() + timedelta(days=30)).isoformat()
    base_risk = int(data.get("base_risk", 50))
    status = data.get("status", "OPERATIONAL")

    if not machine_id or not name:
        return jsonify({"success": False, "error": "Machine ID and Name are required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM machines WHERE id = ?", (machine_id,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": f"Machine '{machine_id}' already exists."}), 409

    cursor.execute("""
        INSERT INTO machines (id, name, site, last_maintenance, due_date, base_risk, status, locked, lock_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, '')
    """, (machine_id, name, site, last_maint, due_date, base_risk, status))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Machine '{name}' ({machine_id}) added successfully."})

@admin_bp.route('/api/admin/machines/<machine_id>', methods=['PUT'])
@admin_required
def update_machine(machine_id):
    machine_id = machine_id.strip().upper()
    data = request.get_json() or {}

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machines WHERE id = ?", (machine_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Machine '{machine_id}' not found."}), 404

    cur = dict(row)
    name = data.get("name", cur["name"]).strip()
    site = data.get("site", cur["site"]).strip()
    last_maintenance = data.get("last_maintenance", cur["last_maintenance"])
    due_date = data.get("due_date", cur["due_date"])
    base_risk = int(data.get("base_risk", cur["base_risk"]))
    status = data.get("status", cur["status"])
    locked = int(data.get("locked", cur["locked"]))
    lock_reason = data.get("lock_reason", cur["lock_reason"])

    cursor.execute("""
        UPDATE machines 
        SET name = ?, site = ?, last_maintenance = ?, due_date = ?, base_risk = ?, status = ?, locked = ?, lock_reason = ?
        WHERE id = ?
    """, (name, site, last_maintenance, due_date, base_risk, status, locked, lock_reason, machine_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Machine '{machine_id}' updated successfully."})

@admin_bp.route('/api/admin/machines/<machine_id>', methods=['DELETE'])
@admin_required
def delete_machine(machine_id):
    machine_id = machine_id.strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM machines WHERE id = ?", (machine_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"success": False, "error": f"Machine '{machine_id}' not found."}), 404

    return jsonify({"success": True, "message": f"Machine '{machine_id}' removed from equipment registry."})

@admin_bp.route('/api/admin/machines/reset_defaults', methods=['POST'])
@admin_required
def reset_machines_defaults():
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
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM machines")
    cursor.executemany("""
        INSERT INTO machines (id, name, site, last_maintenance, due_date, base_risk, status, locked, lock_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, machines_data)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Default oilfield machinery fleet restored successfully."})

# ==============================================================================
# SIF HAZARD REPORTS CRUD
# ==============================================================================

@admin_bp.route('/api/admin/reports', methods=['GET'])
@admin_required
def list_admin_reports():
    conn = get_db()
    cursor = conn.cursor()
    query = request.args.get("q", "").strip().lower()
    risk_filter = request.args.get("risk", "").strip().upper()

    sql = "SELECT * FROM reports"
    params = []
    conditions = []

    if query:
        conditions.append("(LOWER(report_uid) LIKE ? OR LOWER(worker_id) LIKE ? OR LOWER(hazard) LIKE ? OR LOWER(location) LIKE ?)")
        wild = f"%{query}%"
        params.extend([wild, wild, wild, wild])

    if risk_filter:
        conditions.append("risk_level = ?")
        params.append(risk_filter)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY id DESC LIMIT 150"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    reports = [dict(r) for r in rows]
    return jsonify({"success": True, "total": len(reports), "reports": reports})

@admin_bp.route('/api/admin/reports/<int:report_id>', methods=['PUT'])
@admin_required
def update_report(report_id):
    data = request.get_json() or {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Report #{report_id} not found."}), 404

    cur = dict(row)
    hazard = data.get("hazard", cur["hazard"])
    energy_source = data.get("energy_source", cur["energy_source"])
    worker_exposure = int(data.get("worker_exposure", cur["worker_exposure"]))
    barrier_status = data.get("barrier_status", cur["barrier_status"])
    sif_potential = int(data.get("sif_potential", cur["sif_potential"]))
    risk_score = int(data.get("risk_score", cur["risk_score"]))
    risk_level = data.get("risk_level", cur["risk_level"])
    solution = data.get("solution", cur["solution"])
    precautions = data.get("precautions", cur["precautions"])
    status = data.get("status", cur["status"])

    cursor.execute("""
        UPDATE reports 
        SET hazard = ?, energy_source = ?, worker_exposure = ?, barrier_status = ?,
            sif_potential = ?, risk_score = ?, risk_level = ?, solution = ?, precautions = ?, status = ?
        WHERE id = ?
    """, (
        hazard, energy_source, worker_exposure, barrier_status,
        sif_potential, risk_score, risk_level, solution, precautions, status,
        report_id
    ))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Report #{report_id} updated successfully."})

@admin_bp.route('/api/admin/reports/<int:report_id>', methods=['DELETE'])
@admin_required
def delete_report(report_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"success": False, "error": f"Report #{report_id} not found."}), 404

    return jsonify({"success": True, "message": f"Report #{report_id} deleted successfully."})

@admin_bp.route('/api/admin/reports/clear_all', methods=['POST'])
@admin_required
def clear_all_reports():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reports")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Cleared {deleted} safety reports from history."})

@admin_bp.route('/api/admin/reports/export', methods=['GET'])
@admin_required
def export_reports_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    
    if rows:
        headers = [k for k in rows[0].keys() if k != "image_data"]
        writer.writerow(headers)
        for r in rows:
            row_dict = dict(r)
            row_dict.pop("image_data", None)
            writer.writerow([row_dict.get(h, "") for h in headers])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=SurakshaX_Reports_{date.today().isoformat()}.csv"}
    )

# ==============================================================================
# GATE ACCESS LOGS
# ==============================================================================

@admin_bp.route('/api/admin/logs', methods=['GET'])
@admin_required
def get_gate_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gate_access_logs ORDER BY id DESC LIMIT 200")
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"success": True, "total": len(rows), "logs": [dict(r) for r in rows]})

@admin_bp.route('/api/admin/logs', methods=['DELETE'])
@admin_required
def clear_gate_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gate_access_logs")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Cleared {deleted} gate turnstile access log records."})

# ==============================================================================
# SYSTEM STATS & HEALTH
# ==============================================================================

@admin_bp.route('/api/admin/stats', methods=['GET'])
def get_admin_system_stats():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM workers")
    total_workers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM machines")
    total_machines = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM machines WHERE locked = 1")
    locked_machines = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reports")
    total_reports = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reports WHERE sif_potential = 1")
    sif_reports = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM gate_access_logs")
    total_gate_logs = cursor.fetchone()[0]

    conn.close()

    db_size_kb = 0
    if os.path.exists(DB_PATH):
        db_size_kb = round(os.path.getsize(DB_PATH) / 1024, 1)

    return jsonify({
        "success": True,
        "stats": {
            "workers_count": total_workers,
            "machines_count": total_machines,
            "locked_machines": locked_machines,
            "reports_count": total_reports,
            "sif_reports_count": sif_reports,
            "gate_logs_count": total_gate_logs,
            "database_size_kb": db_size_kb,
            "endpoints": {
                "localhost": "http://127.0.0.1:5000",
                "local_wifi": "http://192.168.1.5:5000",
                "global_live": "https://define-stoplight-olympics.ngrok-free.dev"
            }
        }
    })
