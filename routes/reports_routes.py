import json
from datetime import datetime, date
from flask import Blueprint, request, jsonify
from database.database import get_db
from Ai_model.nlp_engine import SafetyNLPEngine
from Ai_model.sif_detector import SIFDetector
from Ai_model.risk_engine import RiskEngine
from Ai_model.recommendations import RecommendationEngine
from Ai_model.multilingual import MultilingualSafetyEngine

reports_bp = Blueprint('reports_bp', __name__)

nlp_engine = SafetyNLPEngine()
sif_detector = SIFDetector()
risk_engine = RiskEngine()
recommendation_engine = RecommendationEngine()
multilingual_engine = MultilingualSafetyEngine()

DEMO_REPORTS = [
    {
        "id": "demo-hi",
        "title": "Demo (Hindi): पंप रखरखाव और बिजली का तार (SIF Critical)",
        "worker_id": "W001",
        "site": "Site A (Duliajan)",
        "location": "Pump Skid 4",
        "activity": "Pump / Equipment Maintenance",
        "machine_id": "M101",
        "report_type": "Unsafe Condition",
        "text": "पंप रखरखाव के दौरान बिजली का तार खुला था और आइसोलेशन पूरा नहीं हुआ था, कर्मचारी उपकरण के पास काम कर रहे थे।"
    },
    {
        "id": "demo-hinglish",
        "title": "Demo (Hinglish): Mud Pump Hose Phat Gaya (Critical)",
        "worker_id": "W003",
        "site": "Site B (Moran)",
        "location": "Mud Pump Station",
        "activity": "Rig Floor & Well Operations",
        "machine_id": "M102",
        "report_type": "Incident",
        "text": "Mud pump ka high pressure hydraulic hose burst ho gaya aur 3000 PSI ka fluid spray operator cabin ke paas nikla."
    },
    {
        "id": "demo-1",
        "title": "Demo 1: Electrical Isolation Failure (SIF Critical)",
        "worker_id": "W001",
        "site": "Site A (Duliajan)",
        "location": "Pump Skid 4",
        "activity": "Pump / Equipment Maintenance",
        "machine_id": "M101",
        "report_type": "Unsafe Condition",
        "text": "Worker was performing maintenance on a pump while electrical isolation was incomplete and switchgear was energized."
    },
    {
        "id": "demo-2",
        "title": "Demo 2: Routine Pipeline Inspection (Context Negation - Safe)",
        "worker_id": "W002",
        "site": "Site B (Moran)",
        "location": "Moran Manifold Km 12",
        "activity": "Pipeline / Valve Operations",
        "machine_id": "M104",
        "report_type": "Near Miss",
        "text": "No leak was observed during pipeline inspection at Moran manifold; all pressure gauges reading normal."
    },
    {
        "id": "demo-3",
        "title": "Demo 3: Working at Height without Tie-Off (High Risk)",
        "worker_id": "W006",
        "site": "Site B (Moran)",
        "location": "Drilling Rig Mast Section 3",
        "activity": "Working at Height / Scaffolding",
        "machine_id": "M105",
        "report_type": "Unsafe Act",
        "text": "Worker observed working on scaffolding platform at 10 meters height without safety harness clipped to lifeline."
    },
    {
        "id": "demo-4",
        "title": "Demo 4: High-Pressure Hydraulic Line Rupture (Critical)",
        "worker_id": "W003",
        "site": "Site B (Moran)",
        "location": "Mud Pump Station",
        "activity": "Rig Floor & Well Operations",
        "machine_id": "M102",
        "report_type": "Incident",
        "text": "Hydraulic hose on Mud Pump P-07 ruptured under 3000 PSI pressure creating pinhole jet stream near operator cabin."
    }
]

@reports_bp.route('/api/demo_reports', methods=['GET'])
def get_demo_reports():
    return jsonify(DEMO_REPORTS)

def process_and_save_report(data: dict, conn) -> dict:
    raw_text = data.get("text", "").strip()
    if not raw_text:
        raise ValueError("Report text description is required.")

    worker_id = data.get("worker_id", "W001").strip().upper()
    site = data.get("site", "Site A (Duliajan)")
    location = data.get("location", "Field Area")
    activity = data.get("activity", "Routine Plant Operations")
    machine_id = data.get("machine_id", "").strip().upper()
    report_type = data.get("report_type", "Unsafe Condition")
    input_channel = data.get("input_channel", "Text")
    image_data = data.get("image_data", "").strip()
    synced_offline = 1 if data.get("is_offline_sync") else 0

    # Check machine overdue status
    cursor = conn.cursor()
    machine_overdue = False
    if machine_id:
        cursor.execute("SELECT status, due_date FROM machines WHERE id = ?", (machine_id,))
        m_row = cursor.fetchone()
        if m_row:
            if m_row["status"] == "OVERDUE":
                machine_overdue = True
            else:
                try:
                    due = date.fromisoformat(m_row["due_date"])
                    if (due - date.today()).days < 0:
                        machine_overdue = True
                except Exception:
                    pass

    # Check site conditions
    weather_multiplier = 1.0
    cursor.execute("SELECT risk_multiplier FROM site_conditions WHERE site_id = ? OR site_name LIKE ?", 
                   (site[:6], f"%{site[:6]}%"))
    s_row = cursor.fetchone()
    if s_row:
        weather_multiplier = s_row["risk_multiplier"]

    # Multilingual Processing & Canonical Translation
    multi_res = multilingual_engine.process_multilingual_report(raw_text)
    canonical_text = multi_res.get("canonical_text", raw_text)
    detected_lang = multi_res.get("detected_lang", "EN")
    is_translated = multi_res.get("is_translated", False)
    trans_method = multi_res.get("method", "Native")

    # Validate whether input describes a genuine industrial/oilfield safety issue
    validation = nlp_engine.validate_safety_report(f"{canonical_text} {raw_text}")
    if not validation["is_valid"]:
        return {
            "success": False,
            "is_invalid_input": True,
            "error": "Invalid Input: No genuine industrial hazard or safety problem detected regarding the oil camp / worksite. Please report an actual field observation, equipment issue, or safety incident.",
            "raw_text": raw_text,
            "canonical_text": canonical_text,
            "detected_lang": detected_lang
        }

    # NLP & AI Analysis Pipeline using Canonical English Text
    nlp_res = nlp_engine.extract_entities(canonical_text)
    if activity and activity != "Routine Plant Operations":
        nlp_res["activity"] = activity

    sif_res = sif_detector.evaluate_sif(nlp_res)
    risk_res = risk_engine.calculate_risk(nlp_res, sif_res, weather_multiplier, machine_overdue)
    rec_res = recommendation_engine.get_recommendations(nlp_res, sif_res, risk_res)

    # Generate unique report ID
    cursor.execute("SELECT COUNT(*) FROM reports")
    total_reps = cursor.fetchone()[0] + 1
    report_uid = f"RPT-2026-{total_reps:03d}"
    created_at = data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Insert into reports table
    cursor.execute("""
        INSERT INTO reports 
        (report_uid, worker_id, site, location, activity, machine_id, report_type, input_channel, raw_text, 
         hazard, energy_source, worker_exposure, barrier_status, sif_potential, confidence, risk_score, 
         risk_level, risk_drivers, precautions, solution, status, image_data, created_at, synced_offline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report_uid, worker_id, site, location, nlp_res["activity"], machine_id,
        report_type, input_channel, raw_text,
        nlp_res["hazard"], nlp_res["energy_source"], 1 if nlp_res["worker_exposure"] else 0,
        nlp_res["barrier_status"], 1 if sif_res["sif_potential"] else 0,
        sif_res["confidence"], risk_res["risk_score"], risk_res["risk_level"],
        json.dumps(risk_res["risk_drivers"]), json.dumps(rec_res["precautions"]),
        rec_res["solution"], "AI ANALYZED", image_data, created_at, synced_offline
    ))
    report_id = cursor.lastrowid

    # Create notification if CRITICAL or SIF Potential
    if risk_res["risk_level"] == "CRITICAL" or sif_res["sif_potential"]:
        notif_title = f"🔴 Critical SIF Precursor Detected ({report_uid})"
        notif_msg = f"{nlp_res['hazard']} at {site} ({location}). Immediate HSE triage required."
        cursor.execute("""
            INSERT INTO notifications (title, message, type, timestamp, read_status, report_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (notif_title, notif_msg, "CRITICAL", created_at, 0, report_id))

    conn.commit()

    return {
        "id": report_id,
        "report_uid": report_uid,
        "worker_id": worker_id,
        "site": site,
        "location": location,
        "activity": nlp_res["activity"],
        "machine_id": machine_id,
        "report_type": report_type,
        "input_channel": input_channel,
        "raw_text": raw_text,
        "canonical_text": canonical_text,
        "detected_lang": detected_lang,
        "is_translated": is_translated,
        "trans_method": trans_method,
        "hazard": nlp_res["hazard"],
        "energy_source": nlp_res["energy_source"],
        "worker_exposure": nlp_res["worker_exposure"],
        "barrier_status": nlp_res["barrier_status"],
        "sif_potential": sif_res["sif_potential"],
        "sif_scenario": sif_res["scenario"],
        "confidence": sif_res["confidence"],
        "risk_score": risk_res["risk_score"],
        "risk_level": risk_res["risk_level"],
        "risk_drivers": risk_res["risk_drivers"],
        "drivers_summary": risk_res["drivers_summary"],
        "explanation": risk_res["explanation"],
        "precautions": rec_res["precautions"],
        "solution": rec_res["solution"],
        "responsible_role": rec_res["responsible_role"],
        "urgency": rec_res["urgency"],
        "status": "AI ANALYZED",
        "image_data": image_data,
        "created_at": created_at,
        "synced_offline": synced_offline
    }

@reports_bp.route('/api/reports/analyze', methods=['POST'])
def analyze_report():
    data = request.get_json() or {}
    try:
        conn = get_db()
        result = process_and_save_report(data, conn)
        conn.close()
        if isinstance(result, dict) and not result.get("success", True):
            return jsonify(result), 200
        return jsonify({"success": True, "report": result})
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal error during analysis: {str(e)}"}), 500

@reports_bp.route('/api/reports', methods=['GET'])
def list_reports():
    conn = get_db()
    cursor = conn.cursor()

    site = request.args.get('site')
    risk_level = request.args.get('risk_level')
    sif = request.args.get('sif')
    search = request.args.get('search')
    worker_id = request.args.get('worker_id')

    query = "SELECT * FROM reports WHERE 1=1"
    params = []

    if site:
        query += " AND site LIKE ?"
        params.append(f"%{site}%")
    if risk_level:
        query += " AND risk_level = ?"
        params.append(risk_level)
    if sif in ['1', '0']:
        query += " AND sif_potential = ?"
        params.append(int(sif))
    if worker_id:
        query += " AND worker_id = ?"
        params.append(worker_id)
    if search:
        query += " AND (report_uid LIKE ? OR raw_text LIKE ? OR hazard LIKE ? OR machine_id LIKE ? OR worker_id LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term])

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    reports = []
    for r in rows:
        item = dict(r)
        try:
            item['risk_drivers'] = json.loads(item['risk_drivers'])
        except Exception:
            item['risk_drivers'] = {}
        try:
            item['precautions'] = json.loads(item['precautions'])
        except Exception:
            item['precautions'] = []
        reports.append(item)

    conn.close()
    return jsonify(reports)

@reports_bp.route('/api/reports/<int:report_id>', methods=['GET'])
def get_report(report_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Report not found"}), 404

    report = dict(row)
    try:
        report['risk_drivers'] = json.loads(report['risk_drivers'])
    except Exception:
        report['risk_drivers'] = {}
    try:
        report['precautions'] = json.loads(report['precautions'])
    except Exception:
        report['precautions'] = []

    # HSE Reviews for this report
    cursor.execute("SELECT * FROM hse_reviews WHERE report_id = ? ORDER BY id DESC", (report_id,))
    reviews = [dict(r) for r in cursor.fetchall()]
    report['reviews'] = reviews

    # Machine details if linked
    if report.get('machine_id'):
        cursor.execute("SELECT * FROM machines WHERE id = ?", (report['machine_id'],))
        m = cursor.fetchone()
        report['machine'] = dict(m) if m else None
    else:
        report['machine'] = None

    conn.close()
    return jsonify(report)

@reports_bp.route('/api/reports/sync', methods=['POST'])
def sync_offline_reports():
    data = request.get_json() or {}
    items = data.get("reports", [])
    if not items:
        return jsonify({"success": True, "synced_count": 0, "message": "No offline items provided."})

    conn = get_db()
    synced_results = []
    errors = []
    for item in items:
        try:
            item["is_offline_sync"] = True
            saved = process_and_save_report(item, conn)
            synced_results.append(saved)
        except Exception as ex:
            errors.append(str(ex))

    conn.close()
    return jsonify({
        "success": True,
        "synced_count": len(synced_results),
        "synced_reports": synced_results,
        "errors": errors
    })

@reports_bp.route('/api/reports/<int:report_id>', methods=['DELETE'])
def delete_report(report_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, report_uid FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Report ID {report_id} not found."}), 404

    report_uid = row["report_uid"]
    # Delete cascade or delete related rows
    cursor.execute("DELETE FROM hse_reviews WHERE report_id = ?", (report_id,))
    cursor.execute("DELETE FROM feedback_log WHERE report_id = ?", (report_id,))
    cursor.execute("DELETE FROM notifications WHERE report_id = ?", (report_id,))
    cursor.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Report {report_uid} successfully deleted by HSE authority.",
        "deleted_id": report_id
    })
