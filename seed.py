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

    today = date.today()
    now_dt = datetime.now()

    # 1. Seed Machines
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

    # 2. Seed Site Conditions
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

    # 3. Seed Realistic Oilfield Risk & SIF Precursor Reports
    cursor.execute("SELECT COUNT(*) FROM reports WHERE report_uid = 'RPT-2026-010'")
    has_demo_pack = cursor.fetchone()[0] > 0

    if not has_demo_pack:
        cursor.execute("DELETE FROM reports WHERE report_uid LIKE 'RPT-2026-00%'")
        cursor.execute("DELETE FROM hse_reviews")
        cursor.execute("DELETE FROM feedback_log")
        cursor.execute("DELETE FROM notifications")
        def _ts(days_ago: int, hour: int = 10, minute: int = 30) -> str:
            dt = datetime.combine(today - timedelta(days=days_ago), datetime.min.time()).replace(hour=hour, minute=minute)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        seed_reports = [
            (
                "RPT-2026-001", "W001", "Site A (Duliajan)", "Compressor Bay 2", "Pump / Equipment Maintenance", "M101",
                "Unsafe Condition", "Voice",
                "Worker was performing maintenance on Main Gas Compressor C-12 while electrical LOTO isolation was incomplete and 415V switchgear remained energized.",
                "Electrical Shock / Arc Flash", "Electrical (High Voltage 415V)", 1, "Incomplete / Bypassed LOTO Barrier",
                1, 0.96, 94, "CRITICAL",
                json.dumps({"energy": 30, "exposure": 25, "barrier": 25, "environment": 14}),
                json.dumps([
                    "Immediately halt work and apply physical Lockout-Tagout (LOTO) padlock on 415V breaker.",
                    "Verify zero energy state using calibrated voltage detector before touching terminals.",
                    "Station dedicated electrical safety watcher outside MCC panel room."
                ]),
                "Halt maintenance immediately; enforce 100% electrical LOTO isolation and zero-energy verification on M101.",
                "AI ANALYZED", _ts(0, 9, 15), 0
            ),
            (
                "RPT-2026-002", "W003", "Site B (Moran)", "Mud Pump Station", "Rig Floor & Well Operations", "M102",
                "Incident", "Voice",
                "Hydraulic discharge hose on High-Pressure Mud Pump P-07 ruptured under 3000 PSI pressure creating a high-velocity fluid jet near operator cabin.",
                "High-Pressure Fluid Injection / Rupture", "Hydraulic / Pneumatic Pressure (3000 PSI)", 1, "Ruptured Primary Containment Hose",
                1, 0.95, 92, "CRITICAL",
                json.dumps({"energy": 30, "exposure": 25, "barrier": 25, "environment": 12}),
                json.dumps([
                    "Activate Emergency Shutdown (ESD) on Mud Pump P-07 and bleed manifold pressure to 0 PSI.",
                    "Install whip-check safety restraint cables and secondary steel burst shielding on all high-pressure hoses.",
                    "Cordon off 15-meter exclusion zone around Mud Pump P-07 until hydro-tested."
                ]),
                "Engage emergency pump interlock on M102, depressurize manifold, and replace ruptured 3000 PSI hose with whip-check restraints.",
                "ACTION IN PROGRESS", _ts(1, 14, 20), 0
            ),
            (
                "RPT-2026-003", "W002", "Site A (Duliajan)", "Wellhead Manifold V-19", "Pipeline / Valve Operations", "M104",
                "Near Miss", "Text",
                "H2S personal gas monitor alarmed at 18 PPM near ESD Wellhead Valve V-19 flange due to sour gas weeping from degraded gasket.",
                "Toxic H2S Gas Leak / Asphyxiation", "Chemical / Pressurized Sour Gas (H2S)", 1, "Missing SCBA / Degraded Flange Seal",
                1, 0.94, 89, "CRITICAL",
                json.dumps({"energy": 28, "exposure": 25, "barrier": 24, "environment": 12}),
                json.dumps([
                    "Evacuate upwind immediately and don Positive-Pressure SCBA (Self-Contained Breathing Apparatus).",
                    "Trigger remote ESD valve closure on Wellhead V-19 to isolate sour gas flow.",
                    "Perform continuous multi-gas monitoring before permitting flange re-torquing."
                ]),
                "Isolate Wellhead Valve V-19 via remote ESD, evacuate downwind personnel, and replace sour-service ring gasket under SCBA.",
                "AI ANALYZED", _ts(2, 11, 45), 0
            ),
            (
                "RPT-2026-004", "W006", "Site B (Moran)", "Drilling Rig Mast Section 3", "Working at Height / Scaffolding", "M105",
                "Unsafe Act", "Text",
                "Rig technician observed working on monkey board scaffolding platform at 12 meters height without double-lanyard safety harness clipped to lifeline.",
                "Fall from Height (>10 Meters)", "Gravitational Potential Energy", 1, "Unlatched Fall Arrest Harness",
                1, 0.92, 84, "HIGH",
                json.dumps({"energy": 26, "exposure": 24, "barrier": 22, "environment": 12}),
                json.dumps([
                    "Enforce mandatory 100% tie-off policy using twin-leg shock-absorbing lanyards anchored above shoulder height.",
                    "Inspect full-body harness D-ring and self-retracting lifeline (SRL) before mast ascent.",
                    "Suspend high-wind derrick work when gusts exceed 25 km/h."
                ]),
                "Stand down derrick crew immediately and verify 100% twin-lanyard tie-off on Rig Mast H-02 lifeline.",
                "AI ANALYZED", _ts(2, 16, 10), 0
            ),
            (
                "RPT-2026-005", "W004", "Site A (Duliajan)", "Pipe Yard Bay 4", "Heavy Lifting & Rigging", "M105",
                "Unsafe Act", "Voice",
                "Roustabout walked directly beneath a suspended 8-ton drill collar bundle while crane was slewing with a frayed wire rope sling.",
                "Suspended Load Drop / Crushing", "Mechanical / Gravitational (8-Ton Load)", 1, "Bypassed Exclusion Zone / Frayed Sling",
                1, 0.90, 79, "HIGH",
                json.dumps({"energy": 25, "exposure": 22, "barrier": 20, "environment": 12}),
                json.dumps([
                    "Never stand or walk beneath a suspended load; establish hard barricades around crane swing radius.",
                    "Use taglines to guide drill pipe bundles from a safe lateral distance.",
                    "Condemn and destroy frayed wire rope sling immediately per OISD-GDN-207."
                ]),
                "Halt crane lift, clear line-of-fire zone using taglines, and replace damaged wire rope sling.",
                "ACTION IN PROGRESS", _ts(3, 10, 5), 0
            ),
            (
                "RPT-2026-006", "W005", "Site C (Digboi)", "Crude Storage Tank T-08", "Confined Space Entry", "M106",
                "Unsafe Condition", "Text",
                "Maintenance crew prepared to enter Crude Oil Separator S-01 manhole for sludge cleaning without mechanical forced ventilation or calibrated LEL gas test.",
                "Confined Space Explosive / Oxygen-Deficient Atmosphere", "Chemical / Hydrocarbon Vapor (LEL)", 1, "Missing Atmospheric Test & Forced Ventilation",
                1, 0.91, 76, "HIGH",
                json.dumps({"energy": 24, "exposure": 20, "barrier": 22, "environment": 10}),
                json.dumps([
                    "Suspend Confined Space Entry Permit until %LEL < 5%, O2 = 20.9%, and H2S = 0 PPM are verified.",
                    "Install explosion-proof air eductor blowers for continuous positive ventilation.",
                    "Station trained standby rescue attendant with tripod hoist at manhole entrance."
                ]),
                "Revoke confined space entry permit on S-01 until continuous gas purging and atmospheric certification are completed.",
                "FIELD VERIFY", _ts(4, 15, 30), 0
            ),
            (
                "RPT-2026-007", "W007", "Site C (Digboi)", "Generator House 2", "Hot Work / Welding", "M103",
                "Unsafe Condition", "Text",
                "Welding sparks observed near Main Power Generator G-04 diesel day-tank transfer pipe without fire blanket containment curtain.",
                "Ignition of Flammable Vapors / Fire", "Thermal / Arc Welding Sparks", 1, "Incomplete Fire Curtain Barrier",
                0, 0.87, 68, "HIGH",
                json.dumps({"energy": 20, "exposure": 18, "barrier": 20, "environment": 10}),
                json.dumps([
                    "Erect FR welding habitat curtains to contain all grinding and welding sparks.",
                    "Cover nearby drains and diesel transfer flanges with wet fire blankets.",
                    "Keep twin CO2 and Dry Chemical Powder (DCP) fire extinguishers within 3 meters."
                ]),
                "Pause welding near Generator G-04 until FR spark containment curtains and fire watch are in place.",
                "AI ANALYZED", _ts(5, 12, 0), 0
            ),
            (
                "RPT-2026-008", "W001", "Site A (Duliajan)", "Separator Skid Walkway", "Routine Plant Operations", "M106",
                "Unsafe Condition", "Voice",
                "Crude emulsion and rainwater accumulation on steel grating walkway near Separator S-01 creating slip hazard during monsoon shower.",
                "Slip / Trip on Oily Grating", "Kinetic / Surface Friction Loss", 0, "Degraded Housekeeping / Drainage",
                0, 0.85, 52, "MEDIUM",
                json.dumps({"energy": 12, "exposure": 14, "barrier": 14, "environment": 12}),
                json.dumps([
                    "Apply absorbent pads and industrial degreaser to clear oil film from grating.",
                    "Unblock oily water drain (OWS) catch-pit strainer.",
                    "Place yellow wet-floor caution cones at walkway approaches."
                ]),
                "Deploy spill absorbent pads on Separator S-01 walkway and clear OWS drain strainer.",
                "ACTION IN PROGRESS", _ts(5, 17, 25), 0
            ),
            (
                "RPT-2026-009", "W002", "Site B (Moran)", "Generator Acoustic Hood", "Pump / Equipment Maintenance", "M103",
                "Near Miss", "Text",
                "Acoustic exhaust heat shield guard on Generator G-04 had two loose bolts causing rattle vibration; no worker contact occurred.",
                "Hot Surface / Mechanical Vibration", "Thermal / Mechanical Vibration", 0, "Loose Secondary Guard Bolt",
                0, 0.84, 44, "MEDIUM",
                json.dumps({"energy": 12, "exposure": 10, "barrier": 12, "environment": 10}),
                json.dumps([
                    "Torque heat-shield mounting bolts with split lock-washers after cool-down.",
                    "Verify thermal insulation cladding integrity."
                ]),
                "Re-torque exhaust guard bolts on Generator G-04 during scheduled shift inspection.",
                "CLOSED", _ts(6, 9, 40), 0
            ),
            (
                "RPT-2026-010", "W003", "Site B (Moran)", "Moran Manifold Km 12", "Pipeline / Valve Operations", "M104",
                "Near Miss", "Text",
                "No leak was observed during routine pipeline walkdown at Moran manifold; all pressure gauges reading normal and LOTO tags intact.",
                "Routine Safe Observation (No Active Hazard)", "Low / Controlled Process Pressure", 0, "All Primary & Secondary Barriers Intact",
                0, 0.93, 18, "LOW",
                json.dumps({"energy": 5, "exposure": 4, "barrier": 4, "environment": 5}),
                json.dumps([
                    "Continue standard shift pressure logging.",
                    "Maintain housekeeping around manifold valve pit."
                ]),
                "No corrective intervention required; log routine compliant inspection.",
                "CLOSED", _ts(6, 16, 50), 0
            )
        ]

        cursor.executemany("""
            INSERT INTO reports 
            (report_uid, worker_id, site, location, activity, machine_id, report_type, input_channel, raw_text, 
             hazard, energy_source, worker_exposure, barrier_status, sif_potential, confidence, risk_score, 
             risk_level, risk_drivers, precautions, solution, status, created_at, synced_offline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_reports)

        cursor.execute("SELECT id, report_uid FROM reports")
        uid_to_id = {row["report_uid"]: row["id"] for row in cursor.fetchall()}
        r1_id = uid_to_id.get("RPT-2026-001")
        r2_id = uid_to_id.get("RPT-2026-002")
        r3_id = uid_to_id.get("RPT-2026-003")
        r5_id = uid_to_id.get("RPT-2026-005")
        r6_id = uid_to_id.get("RPT-2026-006")

        # 4. Seed HSE Reviews & Continuous Learning Feedback Logs
        hse_reviews_data = [
            (
                r2_id, "Ankur Sharma (HSE Lead)", "ACCEPTED", 92, 92, 1, 1,
                "Locked out Mud Pump P-07, depressurized manifold, and ordered replacement 5000-PSI armored hose with whip-checks.",
                "Bikash Borah (Mechanical Lead)", (today + timedelta(days=1)).isoformat(),
                "Critical SIF precursor confirmed; automatic machine interlock engaged on M102.", _ts(1, 15, 0)
            ),
            (
                r5_id, "Ankur Sharma (HSE Lead)", "CORRECTED", 79, 82, 1, 1,
                "Condemned frayed sling and installed rigid red-zone barricades around Pipe Yard Bay 4 crane swing radius.",
                "Rigging Supervisor - Site A", (today + timedelta(days=2)).isoformat(),
                "Elevated risk score from 79% to 82% due to wet ground conditions near crane outriggers.", _ts(3, 11, 15)
            ),
            (
                r6_id, "Ankur Sharma (HSE Lead)", "VERIFY_REQ", 76, 76, 1, 1,
                "Hold Confined Space Entry until gas tester certificate and forced ventilation blower are verified on site.",
                "Area Safety Officer - Digboi", (today + timedelta(days=1)).isoformat(),
                "Field verification ordered prior to issuing entry permit.", _ts(4, 16, 10)
            )
        ]
        cursor.executemany("""
            INSERT INTO hse_reviews 
            (report_id, officer_name, decision, original_risk, corrected_risk, original_sif, corrected_sif, 
             action_assigned, responsible_person, due_date, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, hse_reviews_data)

        feedback_data = [
            (
                r5_id,
                json.dumps({"risk": 79, "sif": 1, "hazard": "Suspended Load Drop / Crushing"}),
                json.dumps({"risk": 82, "sif": 1, "hazard": "Suspended Load Drop / Crushing"}),
                "Elevated risk score from 79% to 82% due to wet ground conditions near crane outriggers.",
                "v1.2-hybrid", _ts(3, 11, 15)
            )
        ]
        cursor.executemany("""
            INSERT INTO feedback_log (report_id, original_analysis, corrected_analysis, feedback_note, model_version, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, feedback_data)

        # 5. Seed Notifications
        notifications_data = [
            (
                "🔴 Critical SIF Precursor Detected (RPT-2026-001)",
                "Electrical Shock / Arc Flash at Site A (Duliajan) - Compressor Bay 2. Immediate HSE triage required.",
                "CRITICAL", _ts(0, 9, 15), 0, r1_id
            ),
            (
                "🔴 Critical SIF Precursor Detected (RPT-2026-002)",
                "High-Pressure Fluid Injection / Rupture at Site B (Moran) - Mud Pump P-07 locked via safety interlock.",
                "CRITICAL", _ts(1, 14, 20), 0, r2_id
            ),
            (
                "🔴 Toxic H2S Gas Alert (RPT-2026-003)",
                "H2S 18 PPM detected at ESD Wellhead Valve V-19 flange (Site A). Upwind evacuation & SCBA required.",
                "CRITICAL", _ts(2, 11, 45), 0, r3_id
            ),
            (
                "🛡️ HSE Review Completed: RPT-2026-005",
                "Decision: CORRECTED | Assigned to: Rigging Supervisor - Site A",
                "INFO", _ts(3, 11, 15), 1, r5_id
            )
        ]
        cursor.executemany("""
            INSERT INTO notifications (title, message, type, timestamp, read_status, report_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, notifications_data)

    # 6. Seed System Staff Users with Passwords (No fake worker face biometrics; workers self-register)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    users_data = [
        ("hse", "hse123", "Ankur Sharma", "HSE OFFICER", "Corporate HSE Directorate", "All OIL Fields", "+91 98765 11223", "OIL Field Headquarters, Duliajan", "HSE01", 1, now_str),
        ("admin", "admin123", "Dr. Prabal Saikia", "ADMIN", "Digital Safety Operations", "Central Command", "+91 98765 99887", "OIL IT Center, Duliajan", "ADM01", 1, now_str),
        ("mechanic", "mech123", "Bikash Borah", "MECHANIC", "Heavy Equipment Maintenance", "Workshop Bay 3", "+91 98765 77665", "East Workshop Enclave, Assam", "MEC01", 1, now_str)
    ]
    cursor.executemany("""
        INSERT OR IGNORE INTO users (username, password, name, role, department, site, phone, address, worker_id, face_enrolled, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, users_data)

    conn.commit()
    conn.close()
    print("Database successfully seeded with realistic Oil India Limited Risk & SIF Precursor demo data.")

if __name__ == "__main__":
    seed_database()
