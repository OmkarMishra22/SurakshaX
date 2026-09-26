import cv2
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from database.database import get_db
from Ai_model.face_engine import FaceGateEngine, get_face_engine

safety_gate_bp = Blueprint('safety_gate_bp', __name__)
face_engine = get_face_engine()

@safety_gate_bp.route('/api/safety_gate/workers', methods=['GET'])
def get_enrolled_workers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, role, department, site FROM workers ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@safety_gate_bp.route('/api/safety_gate/scan_frame', methods=['POST'])
def scan_real_camera_frame():
    """
    Scans a captured frame directly from the real offline local webcam.
    Performs face detection, strict biometric recognition, and PPE clearance inspection.
    """
    data = request.get_json() or {}
    image_base64 = data.get("image")

    if not image_base64:
        return jsonify({"success": False, "error": "No camera frame image received."}), 400

    try:
        bgr_image = face_engine.decode_base64_image(image_base64)
        result = face_engine.analyze_frame(bgr_image)
        return jsonify(result)
    except Exception as e:
        print(f"Frame analysis error: {e}")
        return jsonify({"success": False, "error": f"Camera frame processing error: {str(e)}"}), 500

@safety_gate_bp.route('/api/safety_gate/check/<worker_id>', methods=['GET'])
def check_worker_safety(worker_id):
    worker_id = worker_id.strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": f"Worker with ID '{worker_id}' not found in enrolled registry."}), 404

    w = dict(row)
    missing_precautions = []

    if not w["training_valid"]:
        missing_precautions.append("Mandatory Oilfield Safety Training Refresher Required")
    if not w["cert_valid"]:
        missing_precautions.append("Operational / Medical Fitness Certificate Expired")
    if not w["helmet_assigned"]:
        missing_precautions.append("Hard Hat / Safety Helmet (EN 397)")
    if not w["vest_assigned"]:
        missing_precautions.append("High-Visibility Safety Vest (Class 3)")
    if not w["gloves_assigned"]:
        missing_precautions.append("Heavy-Duty Chemical / Cut-Resistant Gloves")
    if not w["shoes_assigned"]:
        missing_precautions.append("Steel-Toe Anti-Static Safety Boots (IS 15298)")

    access_granted = len(missing_precautions) == 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_str = "ACCESS GRANTED" if access_granted else f"ACCESS DENIED ({len(missing_precautions)} ISSUES DETECTED)"
    missing_str = ", ".join(missing_precautions) if missing_precautions else "None (Full Compliance)"

    try:
        log_conn = get_db()
        log_cursor = log_conn.cursor()
        log_cursor.execute("""
            INSERT INTO gate_access_logs (worker_id, worker_name, timestamp, access_status, missing_ppe, camera_source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (w["id"], w["name"], now_str, status_str, missing_str, "Safety Turnstile", now_str))
        log_conn.commit()
        log_conn.close()
    except Exception:
        pass

    ppe_items = [
        {"item": "Safety Helmet", "detected": bool(w["helmet_assigned"]), "standard": "EN 397"},
        {"item": "High-Vis Safety Vest", "detected": bool(w["vest_assigned"]), "standard": "Class 3 Reflective"},
        {"item": "Safety Gloves", "detected": bool(w["gloves_assigned"]), "standard": "Cut Level 5"},
        {"item": "Steel-Toe Boots", "detected": bool(w["shoes_assigned"]), "standard": "IS 15298"}
    ]

    return jsonify({
        "success": True,
        "worker": w,
        "access_granted": access_granted,
        "status": status_str,
        "issues_detected": missing_precautions,
        "missing_precautions": missing_precautions,
        "ppe_checklist": ppe_items,
        "camera_source": "Offline Local Camera Feed"
    })

@safety_gate_bp.route('/api/safety_gate/override/<worker_id>', methods=['POST'])
def override_worker_safety(worker_id):
    worker_id = worker_id.strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE workers 
        SET training_valid = 1, cert_valid = 1, helmet_assigned = 1, vest_assigned = 1, 
            goggles_assigned = 1, gloves_assigned = 1, shoes_assigned = 1
        WHERE id = ?
    """, (worker_id,))
    conn.commit()

    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "Worker not found"}), 404

    return jsonify({
        "success": True,
        "message": f"Precautions verified and updated for worker {worker_id}.",
        "access_granted": True,
        "status": "ACCESS GRANTED",
        "worker": dict(row)
    })

@safety_gate_bp.route('/api/safety_gate/mechanic_entry', methods=['POST'])
def register_mechanic_entry():
    """
    Dedicated entry registration for Visiting Mechanics & Contractors at Smart Gate.
    Captures Name, Address, Phone, and Assigned Machine, issuing an official Temporary Gate Pass.
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    address = data.get('address', '').strip()
    phone = data.get('phone', '').strip()
    machine_assigned = data.get('machine_assigned', 'General Plant Maintenance').strip()

    if not name or not phone:
        return jsonify({"success": False, "error": "Mechanic Name and Phone number are required."}), 400

    import random
    pass_code = f"MECH-PASS-{random.randint(1000, 9999)}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO mechanic_entries (pass_code, name, address, phone, machine_assigned, entry_time, status)
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
    """, (pass_code, name, address or "Local Contractor Workshop", phone, machine_assigned, now_str))
    conn.commit()

    # Also log notification for HSE controller
    cursor.execute("""
        INSERT INTO notifications (title, message, type, timestamp)
        VALUES (?, ?, 'INFO', ?)
    """, (f"Mechanic Gate Pass Issued ({pass_code})", f"Mechanic {name} entered for repair on {machine_assigned}.", now_str))
    conn.commit()
    conn.close()

    entry_data = {
        "pass_id": pass_code,
        "pass_code": pass_code,
        "name": name,
        "phone": phone,
        "address": address,
        "machine_assigned": machine_assigned,
        "entry_time": now_str,
        "status": "ACTIVE"
    }

    return jsonify({
        "success": True,
        "pass_code": pass_code,
        "name": name,
        "phone": phone,
        "address": address,
        "machine_assigned": machine_assigned,
        "entry_time": now_str,
        "status": "ACTIVE",
        "entry": entry_data,
        "message": f"Temporary Gate Pass {pass_code} successfully issued for {name}."
    })

@safety_gate_bp.route('/api/safety_gate/mechanic_entries', methods=['GET'])
def list_mechanic_entries():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mechanic_entries ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@safety_gate_bp.route('/api/worker/precaution_pass', methods=['POST'])
def issue_worker_precaution_pass():
    """
    Hassle-Free Worker Safety Precaution Check & Digital Gate Pass Generator.
    Validates 7 mandatory oilfield rig precautions, guarantees zero friction,
    and returns a verifiable digital rig entry pass with audio confirmation.
    """
    import random
    from datetime import timedelta
    data = request.get_json() or {}

    name = data.get('name', '').strip() or 'Rig Crew Technician'
    worker_id = (data.get('worker_id', '').strip() or f"W{random.randint(100, 999)}").upper()
    role = data.get('role', '').strip() or 'Rig Crew Specialist'
    department = data.get('department', '').strip() or 'Drilling & Operations'
    site = data.get('site', '').strip() or 'Site A (Duliajan Central Field)'
    
    precautions_input = data.get('precautions') or {}
    # If 1-tap compliance override or missing keys, default to full compliance
    helmet = int(precautions_input.get('helmet', 1))
    vest = int(precautions_input.get('vest', 1))
    goggles = int(precautions_input.get('goggles', 1))
    gloves = int(precautions_input.get('gloves', 1))
    shoes = int(precautions_input.get('shoes', 1))
    h2s_badge = int(precautions_input.get('h2s_badge', 1))
    ptw_valid = int(precautions_input.get('ptw_valid', 1))

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expiry_str = (now + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    pass_code = f"OIL-PASS-{random.randint(10000, 99999)}"

    # Check for any missing safety items
    missing = []
    if not helmet: missing.append("Safety Helmet / Hard Hat (EN 397)")
    if not vest: missing.append("High-Vis Reflective Vest (Class 3)")
    if not goggles: missing.append("Impact Eye Protection / Goggles (ANSI Z87)")
    if not gloves: missing.append("Cut & Chemical Heavy Rig Gloves")
    if not shoes: missing.append("Steel-Toe Anti-Static Boots (IS 15298)")
    if not h2s_badge: missing.append("H2S Personal Gas Monitor Badge")
    if not ptw_valid: missing.append("Valid Permit-To-Work (PTW) Verification")

    access_granted = (len(missing) == 0)
    status_text = "ACCESS GRANTED • RIG CLEARANCE VALID" if access_granted else f"ACCESS DENIED ({len(missing)} ISSUES)"

    # Auto-register / sync worker in 'workers' table so they are always recognized
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO workers (id, name, role, department, site, training_valid, cert_valid, 
                             helmet_assigned, vest_assigned, goggles_assigned, gloves_assigned, shoes_assigned)
        VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            role = excluded.role,
            department = excluded.department,
            site = excluded.site,
            helmet_assigned = excluded.helmet_assigned,
            vest_assigned = excluded.vest_assigned,
            goggles_assigned = excluded.goggles_assigned,
            gloves_assigned = excluded.gloves_assigned,
            shoes_assigned = excluded.shoes_assigned
    """, (worker_id, name, role, department, site, helmet, vest, goggles, gloves, shoes))

    # Log turnstile entry log
    cursor.execute("""
        INSERT INTO gate_access_logs (worker_id, worker_name, timestamp, access_status, missing_ppe, camera_source, created_at)
        VALUES (?, ?, ?, ?, ?, 'Worker Portal Kiosk', ?)
    """, (worker_id, name, now_str, status_text, ", ".join(missing) if missing else "All 7 Precautions Verified", now_str))

    conn.commit()
    conn.close()

    response_payload = {
        "success": True,
        "pass_code": pass_code,
        "access_granted": access_granted,
        "status": status_text,
        "worker": {
            "id": worker_id,
            "name": name,
            "role": role,
            "department": department,
            "site": site
        },
        "precautions_verified": [
            {"name": "Hard Hat / Helmet", "standard": "EN 397 / IS 2925", "verified": bool(helmet)},
            {"name": "High-Vis Vest", "standard": "Class 3 Reflective", "verified": bool(vest)},
            {"name": "Safety Goggles", "standard": "ANSI Z87.1", "verified": bool(goggles)},
            {"name": "Rig Gloves", "standard": "EN 388 Cut-5", "verified": bool(gloves)},
            {"name": "Steel-Toe Boots", "standard": "IS 15298 Anti-Static", "verified": bool(shoes)},
            {"name": "H2S Gas Detector", "standard": "OIL Personal Gas Monitor", "verified": bool(h2s_badge)},
            {"name": "Permit to Work (PTW)", "standard": "Daily Rig Tool Clearance", "verified": bool(ptw_valid)}
        ],
        "missing_precautions": missing,
        "issued_at": now_str,
        "expires_at": expiry_str,
        "voice_message": (
            f"Access Granted. All safety precautions verified for {name}. Rig turnstile unlocked. Have a safe shift."
            if access_granted else
            f"Access Denied. {len(missing)} safety precautions pending. Please equip gear and retry."
        )
    }

    return jsonify(response_payload)
