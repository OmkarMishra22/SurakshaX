from datetime import date, datetime
from flask import Blueprint, request, jsonify
from database.database import get_db

machines_bp = Blueprint('machines_bp', __name__)

@machines_bp.route('/api/machines', methods=['GET'])
def list_machines():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machines ORDER BY base_risk DESC")
    rows = cursor.fetchall()
    conn.close()

    today = date.today()
    machines = []
    for r in rows:
        item = dict(r)
        try:
            due = date.fromisoformat(item["due_date"])
            days = (due - today).days
        except Exception:
            days = 0

        item["days_remaining"] = days
        if days < 0:
            item["overdue"] = True
            item["overdue_days"] = abs(days)
            item["calculated_status"] = "OVERDUE"
            item["urgency"] = f"CRITICAL: OVERDUE by {abs(days)} days"
        elif days <= 2:
            item["overdue"] = False
            item["overdue_days"] = 0
            item["calculated_status"] = "EXPIRING SOON"
            item["urgency"] = f"URGENT: Due in {days} days"
        elif days <= 7:
            item["overdue"] = False
            item["overdue_days"] = 0
            item["calculated_status"] = "OPERATIONAL"
            item["urgency"] = f"MODERATE: Due in {days} days"
        else:
            item["overdue"] = False
            item["overdue_days"] = 0
            item["calculated_status"] = "OPERATIONAL"
            item["urgency"] = f"NORMAL: Due in {days} days"

        # Interlock status
        item["interlock_badge"] = "LOCKED" if item["locked"] else "UNLOCKED"
        machines.append(item)

    return jsonify(machines)

@machines_bp.route('/api/machines/toggle_lock/<machine_id>', methods=['POST'])
def toggle_machine_lock(machine_id):
    machine_id = machine_id.strip().upper()
    data = request.get_json() or {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machines WHERE id = ?", (machine_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Machine '{machine_id}' not found"}), 404

    current_locked = row["locked"]
    new_locked = 0 if current_locked == 1 else 1
    default_reason = f"Simulated Safety Interlock engaged by HSE Officer due to overdue maintenance." if new_locked else ""
    lock_reason = data.get("reason") or default_reason

    cursor.execute("UPDATE machines SET locked = ?, lock_reason = ? WHERE id = ?", (new_locked, lock_reason, machine_id))
    
    # Add notification if newly locked
    if new_locked:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO notifications (title, message, type, timestamp, read_status)
            VALUES (?, ?, ?, ?, ?)
        """, (f"🔒 Safety Interlock Active ({machine_id})", f"{row['name']} has been locked: {lock_reason}", "WARNING", now_str, 0))

    conn.commit()

    cursor.execute("SELECT * FROM machines WHERE id = ?", (machine_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "success": True,
        "machine": updated,
        "locked": bool(new_locked),
        "disclaimer": "Prototype simulation — real deployment requires certified industrial safety hardware/PLC/interlock and authorized safety procedures."
    })

@machines_bp.route('/api/machines/update_due_date/<machine_id>', methods=['POST'])
def update_due_date(machine_id):
    machine_id = machine_id.strip().upper()
    data = request.get_json() or {}
    new_date = data.get("due_date")
    if not new_date:
        return jsonify({"success": False, "error": "New due date is required (YYYY-MM-DD)"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE machines SET due_date = ? WHERE id = ?", (new_date, machine_id))
    conn.commit()
    cursor.execute("SELECT * FROM machines WHERE id = ?", (machine_id,))
    row = cursor.fetchone()
    conn.close()

    return jsonify({"success": True, "machine": dict(row)})

@machines_bp.route('/api/machines/repair_review', methods=['POST'])
def submit_repair_review():
    """
    Worker Post-Repair Review:
    Workers or technicians inspect repaired equipment and submit verification.
    If verified safe, updates machine status and clears software lockout.
    """
    data = request.get_json() or {}
    machine_id = data.get('machine_id', '').strip().upper()
    worker_id = data.get('worker_id', 'W001').strip().upper()
    worker_name = data.get('worker_name', 'Rahul Das').strip()
    repair_status = data.get('repair_status', 'REPAIRED & VERIFIED').strip().upper()
    observations = data.get('observations', '').strip()
    verified_safe = 1 if data.get('verified_safe', True) else 0

    if not machine_id or not observations:
        return jsonify({"success": False, "error": "Machine ID and inspection observations are required."}), 400

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO repair_reviews (machine_id, worker_id, worker_name, repair_status, observations, verified_safe, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (machine_id, worker_id, worker_name, repair_status, observations, verified_safe, now_str))

    # If verified safe, restore machine status to OPERATIONAL and release interlock
    if verified_safe and repair_status in ['REPAIRED & VERIFIED', 'OPERATIONAL']:
        cursor.execute("""
            UPDATE machines 
            SET status = 'OPERATIONAL', locked = 0, lock_reason = 'Restored following worker post-repair signoff'
            WHERE id = ?
        """, (machine_id,))
        
        # Deflect and resolve open reports associated with this machine
        cursor.execute("""
            UPDATE reports 
            SET status = 'RESOLVED & REPAIRED',
                solution = solution || ' | [REPAIR VERIFIED] Restored & verified safe by ' || ? || ' (' || ? || ') on ' || ? || '. Obs: ' || ?
            WHERE machine_id = ? AND status != 'RESOLVED & REPAIRED'
        """, (worker_name, worker_id, now_str, observations, machine_id))
        deflected_count = cursor.rowcount

        cursor.execute("""
            INSERT INTO notifications (title, message, type, timestamp)
            VALUES (?, ?, 'SUCCESS', ?)
        """, (f"Machine {machine_id} Repaired & Verified Safe", f"Worker {worker_name} ({worker_id}) verified repair. {deflected_count} incident report(s) marked RESOLVED & REPAIRED.", now_str))
    else:
        deflected_count = 0

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Post-repair inspection review recorded for {machine_id}. Deflected {deflected_count} related safety reports to RESOLVED & REPAIRED.",
        "machine_id": machine_id,
        "repair_status": repair_status,
        "verified_safe": bool(verified_safe),
        "deflected_reports_count": deflected_count
    })

@machines_bp.route('/api/machines/repair_reviews', methods=['GET'])
def get_repair_reviews():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repair_reviews ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
