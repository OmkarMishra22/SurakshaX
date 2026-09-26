import os
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from database.database import get_db
from Ai_model.face_engine import FaceGateEngine, get_face_engine

auth_bp = Blueprint('auth_bp', __name__)
face_engine = get_face_engine()

DEFAULT_ROLE_PROFILES = {
    "worker": {
        "id": "UNENROLLED",
        "username": "",
        "name": "Unenrolled Worker",
        "role": "WORKER",
        "department": "Please Register",
        "site": "Site Gate"
    },
    "hse": {
        "id": "HSE01",
        "username": "hse",
        "name": "Ankur Sharma",
        "role": "HSE OFFICER",
        "department": "Corporate HSE Directorate",
        "site": "All OIL Fields"
    },
    "admin": {
        "id": "ADM01",
        "username": "admin",
        "name": "Dr. Prabal Saikia",
        "role": "ADMIN",
        "department": "Digital Safety Operations",
        "site": "Central Command"
    },
    "mechanic": {
        "id": "MEC01",
        "username": "mechanic",
        "name": "Bikash Borah",
        "role": "MECHANIC",
        "department": "Heavy Equipment Maintenance",
        "site": "Workshop Bay 3"
    }
}

@auth_bp.route('/api/auth/current', methods=['GET'])
def get_current_user():
    # If user is in session, retrieve details
    user_id = session.get('user_id')
    if user_id:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        if u:
            return jsonify({
                "id": u["worker_id"] or f"USR{u['id']}",
                "worker_id": u["worker_id"],
                "db_id": u["id"],
                "username": u["username"],
                "name": u["name"],
                "role": u["role"].upper(),
                "department": u["department"],
                "site": u["site"],
                "phone": u["phone"],
                "address": u["address"],
                "face_enrolled": bool(u["face_enrolled"]),
                "is_logged_in": True
            })

    # If role_key was explicitly set in session
    role_key = session.get('user_role_key')
    if role_key and role_key in DEFAULT_ROLE_PROFILES:
        prof = dict(DEFAULT_ROLE_PROFILES[role_key])
        prof["is_logged_in"] = True
        return jsonify(prof)

    # Return guest status
    return jsonify({
        "id": "GUEST",
        "worker_id": "GUEST",
        "db_id": None,
        "username": "",
        "name": "Guest / Not Logged In",
        "role": "GUEST",
        "department": "Please Sign In",
        "site": "Site Gate",
        "is_logged_in": False
    })

@auth_bp.route('/api/auth/register', methods=['POST'])
def register_user():
    """
    Self-Registration endpoint for Worker, HSE Officer, Admin, or Mechanic.
    Supports custom user ID and auto-trains face biometric model if face samples are submitted.
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    username = data.get('username', '').strip().lower()
    custom_worker_id = data.get('worker_id', '').strip()
    password = data.get('password', '').strip()
    role_raw = data.get('role', 'WORKER').strip().upper()
    if role_raw in ['HSE', 'HSE OFFICER', 'OFFICER']:
        role = 'HSE OFFICER'
    elif role_raw in ['ADMIN', 'ADMINISTRATOR']:
        role = 'ADMIN'
    elif role_raw in ['MECHANIC', 'CONTRACTOR']:
        role = 'MECHANIC'
    else:
        role = 'WORKER'
    department = data.get('department', 'Plant Operations').strip()
    site = data.get('site', 'Site A (Duliajan)').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()
    face_samples = data.get('face_samples', [])

    if not name:
        return jsonify({"success": False, "error": "Full Name is required."}), 400

    if not password or len(password) < 4:
        return jsonify({"success": False, "error": "Password is required (minimum 4 characters)."}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Generate Worker ID safely without collision
    if custom_worker_id:
        worker_id = custom_worker_id.upper()
    else:
        cursor.execute("SELECT worker_id FROM users WHERE worker_id IS NOT NULL AND worker_id != '' UNION SELECT id FROM workers")
        existing_ids = {str(row[0]).upper() for row in cursor.fetchall() if row[0]}
        prefix = "W" if role == "WORKER" else f"{role[:3]}_"
        counter = 1
        while True:
            cand = f"{prefix}{counter:03d}"
            if cand not in existing_ids:
                worker_id = cand
                break
            counter += 1

    # Auto-generate username from name if not provided
    if not username:
        base_username = re.sub(r'[^a-z0-9]', '', name.lower())
        if not base_username:
            base_username = "worker"
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (base_username,))
        if cursor.fetchone():
            username = f"{base_username}_{worker_id.lower().replace('-', '_')}"
        else:
            username = base_username

    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT id, worker_id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        existing = cursor.fetchone()
        if existing:
            user_db_id = existing["id"]
            if existing["worker_id"] and not custom_worker_id:
                worker_id = existing["worker_id"]
            cursor.execute("""
                UPDATE users SET password = ?, name = ?, role = ?, department = ?, site = ?, phone = ?, address = ?, worker_id = ?, face_enrolled = ?
                WHERE id = ?
            """, (password, name, role, department, site, phone, address, worker_id, 1 if face_samples else 0, user_db_id))
        else:
            cursor.execute("""
                INSERT INTO users (username, password, name, role, department, site, phone, address, worker_id, face_enrolled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, password, name, role, department, site, phone, address, worker_id, 1 if face_samples else 0, now_str))
            user_db_id = cursor.lastrowid

        # Also insert or update in workers table for compliance & gate check
        cursor.execute("""
            INSERT OR REPLACE INTO workers 
            (id, name, role, department, site, training_valid, cert_valid, helmet_assigned, vest_assigned, goggles_assigned, gloves_assigned, shoes_assigned)
            VALUES (?, ?, ?, ?, ?, 1, 1, 1, 1, 1, 1, 1)
        """, (worker_id, name, f"{role.title()} ({department})", department, site))

        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": f"Registration failed: {str(e)}"}), 400

    conn.close()

    # If face samples are provided, train the LBPH recognition model in background
    training_result = None
    if face_samples and len(face_samples) > 0:
        training_result = face_engine.enroll_and_train_user(user_db_id, worker_id, name, face_samples)

    # Set session
    session['user_id'] = user_db_id
    session['username'] = username
    session['worker_id'] = worker_id
    session['user_role_key'] = role.lower().replace(" officer", "").replace(" control", "")

    return jsonify({
        "success": True,
        "message": f"Successfully registered {name} as {role}!",
        "user": {
            "id": worker_id,
            "worker_id": worker_id,
            "db_id": user_db_id,
            "username": username,
            "name": name,
            "role": role,
            "department": department,
            "site": site,
            "phone": phone,
            "address": address,
            "face_trained": bool(face_samples)
        },
        "training_result": training_result
    })

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """
    Strict Login endpoint: Requires valid username/worker ID and password.
    Declines access if user not found or password incorrect.
    """
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username:
        return jsonify({"success": False, "error": "Please enter your Username or Worker ID."}), 400

    if not password:
        return jsonify({"success": False, "error": "Please enter your Password."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM users 
        WHERE LOWER(username) = LOWER(?) OR UPPER(worker_id) = UPPER(?) OR LOWER(worker_id) = LOWER(?) OR LOWER(name) = LOWER(?)
    """, (username, username, username, username))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({
            "success": False, 
            "error": f"Access Denied: Username or Worker ID '{username}' is not registered in the system. Please register first."
        }), 401

    if str(user["password"]) != str(password):
        conn.close()
        return jsonify({
            "success": False, 
            "error": "Access Denied: Incorrect password provided for this account."
        }), 401

    user_db_id = user['id']
    worker_id = user['worker_id'] or f"W{user_db_id:03d}"
    user_role = user['role']

    session['user_id'] = user_db_id
    session['username'] = user['username']
    session['worker_id'] = worker_id
    session['user_role_key'] = user_role.lower().replace(" officer", "").replace(" control", "")

    # Ensure worker compliance record is linked to this user's worker_id
    cursor.execute("""
        INSERT OR IGNORE INTO workers 
        (id, name, role, department, site, training_valid, cert_valid, helmet_assigned, vest_assigned, goggles_assigned, gloves_assigned, shoes_assigned)
        VALUES (?, ?, ?, ?, ?, 1, 1, 1, 1, 1, 1, 1)
    """, (worker_id, user['name'], f"{user_role.title()} ({user['department'] or 'Operations'})", user['department'] or 'Operations', user['site'] or 'Site A (Duliajan)'))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "user": {
            "id": user["worker_id"] or f"USR{user['id']}",
            "worker_id": user["worker_id"],
            "db_id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"].upper(),
            "department": user["department"],
            "site": user["site"],
            "phone": user["phone"],
            "address": user["address"],
            "face_enrolled": bool(user["face_enrolled"])
        }
    })

@auth_bp.route('/api/auth/user_dossier', methods=['GET'])
def get_user_dossier():
    """
    Retrieves full personal safety dossier for the active user:
    - Identity, credentials, biometric enrollment status
    - Compliance certificates and assigned PPE gear
    - Role-tailored historical records
    """
    conn = get_db()
    cursor = conn.cursor()

    req_user = request.args.get('user_id', '').strip()
    user = None
    if req_user and req_user.lower() not in ('', 'null', 'undefined', 'none', 'guest'):
        if req_user.isdigit():
            cursor.execute("SELECT * FROM users WHERE id = ?", (int(req_user),))
            user = cursor.fetchone()
        if not user:
            cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR UPPER(worker_id) = UPPER(?)", (req_user, req_user))
            user = cursor.fetchone()

    if not user:
        user_id = session.get('user_id')
        if user_id:
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()

    if not user:
        role_key = session.get('user_role_key')
        if role_key and role_key in ['hse', 'admin', 'mechanic']:
            cursor.execute("SELECT * FROM users WHERE username = ?", (role_key,))
            user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "error": "No active user session or matching record found."}), 404

    u = dict(user)
    worker_id = u.get("worker_id") or f"W{u['id']:03d}"

    # Query worker compliance record
    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    wrow = cursor.fetchone()
    worker_comp = dict(wrow) if wrow else {
        "training_valid": 1,
        "cert_valid": 1,
        "helmet_assigned": 1,
        "vest_assigned": 1,
        "goggles_assigned": 1,
        "gloves_assigned": 1,
        "shoes_assigned": 1
    }

    role_upper = u["role"].upper()

    # 1. Worker Past Reports & Solutions
    past_reports = []
    cursor.execute("""
        SELECT id, report_uid, site, location, activity, machine_id, report_type,
               raw_text, hazard, energy_source, worker_exposure, sif_potential,
               risk_score, risk_level, precautions, solution, status, created_at
        FROM reports 
        WHERE worker_id = ? OR worker_id = ? OR ? = 'ALL'
        ORDER BY id DESC
    """, (worker_id, u["username"], "ALL" if "HSE" in role_upper or "ADMIN" in role_upper else "FILTER"))
    report_rows = cursor.fetchall()

    if len(report_rows) == 0:
        cursor.execute("""
            SELECT id, report_uid, site, location, activity, machine_id, report_type,
                   raw_text, hazard, energy_source, worker_exposure, sif_potential,
                   risk_score, risk_level, precautions, solution, status, created_at
            FROM reports ORDER BY id DESC LIMIT 3
        """)
        report_rows = cursor.fetchall()

    for r in report_rows:
        past_reports.append(dict(r))

    # 2. HSE Reviews
    hse_reviews = []
    if "HSE" in role_upper or "ADMIN" in role_upper:
        cursor.execute("""
            SELECT hr.*, r.report_uid, r.hazard, r.site, r.raw_text
            FROM hse_reviews hr
            JOIN reports r ON hr.report_id = r.id
            ORDER BY hr.id DESC LIMIT 15
        """)
        hse_reviews = [dict(r) for r in cursor.fetchall()]

    # 3. Machine Repair Reviews
    repair_reviews = []
    cursor.execute("""
        SELECT * FROM repair_reviews 
        WHERE worker_id = ? OR worker_name = ? OR ? = 'ALL'
        ORDER BY id DESC
    """, (worker_id, u["name"], "ALL" if "HSE" in role_upper or "ADMIN" in role_upper else "FILTER"))
    repair_reviews = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return jsonify({
        "success": True,
        "user": {
            "id": worker_id,
            "db_id": u["id"],
            "username": u["username"],
            "name": u["name"],
            "role": role_upper,
            "department": u["department"] or "Operations",
            "site": u["site"] or "Site A (Duliajan)",
            "phone": u["phone"] or "N/A",
            "address": u["address"] or "Assam Oilfield Enclave",
            "created_at": u["created_at"],
            "face_enrolled": bool(u["face_enrolled"])
        },
        "compliance": {
            "training_valid": bool(worker_comp.get("training_valid", 1)),
            "cert_valid": bool(worker_comp.get("cert_valid", 1)),
            "helmet_assigned": bool(worker_comp.get("helmet_assigned", 1)),
            "vest_assigned": bool(worker_comp.get("vest_assigned", 1)),
            "goggles_assigned": bool(worker_comp.get("goggles_assigned", 1)),
            "gloves_assigned": bool(worker_comp.get("gloves_assigned", 1)),
            "shoes_assigned": bool(worker_comp.get("shoes_assigned", 1))
        },
        "past_reports": past_reports,
        "hse_reviews": hse_reviews,
        "repair_reviews": repair_reviews,
        "stats": {
            "total_reports": len(past_reports),
            "critical_sifs": len([r for r in past_reports if r.get("sif_potential")]),
            "closed_actions": len([r for r in past_reports if r.get("status") == "VERIFIED & CLOSED"]),
            "repairs_signed": len(repair_reviews)
        }
    })

@auth_bp.route('/api/auth/switch_role', methods=['POST'])
def switch_role():
    data = request.get_json() or {}
    new_role = data.get('role', 'hse').lower()
    if new_role not in DEFAULT_ROLE_PROFILES:
        return jsonify({"error": "Invalid role"}), 400
    session.clear()
    session['user_role_key'] = new_role
    return jsonify({"success": True, "user": DEFAULT_ROLE_PROFILES[new_role]})

@auth_bp.route('/api/auth/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

@auth_bp.route('/api/auth/clear_all_registrations', methods=['POST'])
def clear_all_registrations():
    """
    Clears all registered user face samples from dataset, removes trained weights,
    resets face_enrolled flags in DB, and removes non-seed dynamic users.
    """
    try:
        # Clear files and recognizer models
        clear_res = face_engine.clear_all_registrations()

        # Clean DB: Purge all worker accounts and worker registry completely (No demo workers)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE role = 'WORKER' OR username IN ('worker', 'w007')")
        cursor.execute("UPDATE users SET face_enrolled = 0")
        cursor.execute("DELETE FROM workers")
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "All registered biometrics and dynamic user records have been successfully cleared.",
            "details": clear_res
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to clear registrations: {str(e)}"}), 500

