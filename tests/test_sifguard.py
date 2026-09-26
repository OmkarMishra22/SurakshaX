import unittest
import sys
import os

# Ensure sifguard directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from Ai_model.nlp_engine import SafetyNLPEngine
from Ai_model.sif_detector import SIFDetector
from Ai_model.risk_engine import RiskEngine
from Ai_model.recommendations import RecommendationEngine
from database.database import get_db
from app import create_app

class SIFGuardTestSuite(unittest.TestCase):

    def setUp(self):
        self.nlp = SafetyNLPEngine()
        self.sif = SIFDetector()
        self.risk = RiskEngine()
        self.rec = RecommendationEngine()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_nlp_negation_routine_safe(self):
        """Context-aware NLP: 'No leak was observed' should NOT trigger active leak hazard."""
        text = "No leak was observed during pipeline inspection at Moran manifold."
        nlp_out = self.nlp.extract_entities(text)
        self.assertTrue(nlp_out["is_negated"])
        self.assertFalse(nlp_out["worker_exposure"])

        sif_out = self.sif.evaluate_sif(nlp_out)
        self.assertFalse(sif_out["sif_potential"])

        risk_out = self.risk.calculate_risk(nlp_out, sif_out)
        self.assertEqual(risk_out["risk_level"], "LOW")
        self.assertLess(risk_out["risk_score"], 30)

    def test_nlp_sif_critical_electrical(self):
        """SIF Precursor Detection: Maintenance with incomplete electrical isolation."""
        text = "Worker was performing maintenance on a pump while electrical isolation was incomplete and switchgear was energized."
        nlp_out = self.nlp.extract_entities(text)
        self.assertFalse(nlp_out["is_negated"])
        self.assertTrue(nlp_out["worker_exposure"])
        self.assertIn("Electrical", nlp_out["hazard"])

        sif_out = self.sif.evaluate_sif(nlp_out)
        self.assertTrue(sif_out["sif_potential"])

        risk_out = self.risk.calculate_risk(nlp_out, sif_out, weather_multiplier=1.0, machine_overdue=True)
        self.assertEqual(risk_out["risk_level"], "CRITICAL")
        self.assertGreaterEqual(risk_out["risk_score"], 85)

        rec_out = self.rec.get_recommendations(nlp_out, sif_out, risk_out)
        self.assertTrue(any("LOTO" in p or "Lockout" in p for p in rec_out["precautions"]))
        self.assertIn("Stop", rec_out["solution"])

    def test_safety_gate_workflow(self):
        """Safety Gate: Temporary test worker clearance and override workflow."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO workers 
            (id, name, role, department, site, training_valid, cert_valid, helmet_assigned, vest_assigned, goggles_assigned, gloves_assigned, shoes_assigned)
            VALUES ('W001', 'Test Worker 1', 'OPERATOR', 'Rig', 'Site A', 1, 1, 1, 1, 1, 1, 1),
                   ('W002', 'Test Worker 2', 'OPERATOR', 'Rig', 'Site A', 1, 1, 1, 0, 1, 1, 1)
        """)
        conn.commit()
        conn.close()

        try:
            # W001 check
            res1 = self.client.get('/api/safety_gate/check/W001')
            self.assertEqual(res1.status_code, 200)
            data1 = res1.get_json()
            self.assertTrue(data1["access_granted"])

            # W002 check (initially missing vest)
            res2 = self.client.get('/api/safety_gate/check/W002')
            self.assertEqual(res2.status_code, 200)
            data2 = res2.get_json()
            # Should show missing items if vest is not assigned
            if not data2["access_granted"]:
                self.assertIn("ACCESS DENIED", data2["status"])
                # Now override / mark completed
                res_ov = self.client.post('/api/safety_gate/override/W002')
                self.assertEqual(res_ov.status_code, 200)
                data_ov = res_ov.get_json()
                self.assertTrue(data_ov["access_granted"])
        finally:
            conn = get_db()
            conn.execute("DELETE FROM workers WHERE id IN ('W001', 'W002')")
            conn.commit()
            conn.close()

    def test_machine_interlock_simulation(self):
        """Machine Interlock: Software simulation toggle with industrial disclaimer."""
        res = self.client.post('/api/machines/toggle_lock/M101', json={"reason": "Test interlock"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("disclaimer", data)
        self.assertIn("Prototype simulation", data["disclaimer"])

    def test_report_submission_api(self):
        """Submitting a report via API returns full AI analysis and saves to DB."""
        payload = {
            "worker_id": "W001",
            "site": "Site A (Duliajan)",
            "location": "Compressor Skid 1",
            "activity": "Pump / Equipment Maintenance",
            "machine_id": "M101",
            "report_type": "Unsafe Condition",
            "text": "During pump maintenance, the electrical isolation was incomplete and workers were exposed to the equipment."
        }
        res = self.client.post('/api/reports/analyze', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        rep = data["report"]
        self.assertTrue(rep["sif_potential"])
        self.assertEqual(rep["risk_level"], "CRITICAL")
        self.assertGreaterEqual(rep["risk_score"], 85)

    def test_real_camera_scan_frame(self):
        """Real Camera Frame Scan: Strict detection accurately flags when NO face is present in frame."""
        import cv2, numpy as np, base64
        dummy_img = np.zeros((240, 320, 3), dtype=np.uint8)
        _, buf = cv2.imencode('.jpg', dummy_img)
        b64_str = base64.b64encode(buf).decode('utf-8')

        res = self.client.post('/api/safety_gate/scan_frame', json={
            "image": b64_str,
            "preferred_worker_id": "W007"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["face_detected"])
        self.assertFalse(data["access_granted"])
        self.assertEqual(data["status"], "NO FACE DETECTED")
        self.assertIn("issues_detected", data)
        self.assertTrue(any("NO FACE" in issue for issue in data["issues_detected"]))

    def test_casual_chat_invalid_input_rejection(self):
        """Casual / non-hazard input is rejected with invalid input warning without creating false reports."""
        payload = {
            "worker_id": "W001",
            "site": "Site A (Duliajan)",
            "location": "Canteen / Camp Area",
            "activity": "General Observation",
            "machine_id": "None",
            "report_type": "Unsafe Act",
            "text": "mere ko samajh nahi aa raha hai kya chal raha hai chai peete hain"
        }
        res = self.client.post('/api/reports/analyze', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertTrue(data.get("is_invalid_input"))
        self.assertIn("No genuine industrial hazard", data.get("error", ""))

    def test_live_weather_conditions(self):
        """Current Weather: Verify meteorological observation endpoint returns site conditions."""
        res = self.client.get('/api/site_conditions')
        self.assertEqual(res.status_code, 200)
        sites = res.get_json()
        self.assertGreaterEqual(len(sites), 3)
        site_a = sites[0]
        self.assertIn("temperature", site_a)
        self.assertIn("risk_multiplier", site_a)

    def test_multilingual_reporting(self):
        """Multilingual Safety Ingestion: Hindi text is translated and SIF precursor detected."""
        payload = {
            "worker_id": "W007",
            "site": "Site A (Duliajan)",
            "location": "Pump Skid B",
            "activity": "Pump / Equipment Maintenance",
            "machine_id": "M102",
            "report_type": "Unsafe Condition",
            "text": "पंप रखरखाव के दौरान बिजली का तार खुला था और गंभीर खतरा था"
        }
        res = self.client.post('/api/reports/analyze', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        rep = data["report"]
        self.assertTrue(rep["is_translated"])
        self.assertIn(rep["detected_lang"], ["hi", "HI", "hindi"])
        self.assertTrue(rep["sif_potential"])
        self.assertIn("wire", rep["canonical_text"].lower())

    def test_mechanic_entry_gate_pass(self):
        """Mechanic Gate Pass: Issue temporary entry pass for visiting contractor."""
        payload = {
            "name": "Bikash Borah",
            "phone": "+91 98765 43210",
            "address": "Duliajan Workshop East, Assam",
            "machine_assigned": "High-Pressure Mud Pump P-07 (M102)"
        }
        res = self.client.post('/api/safety_gate/mechanic_entry', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("MECH-", data["entry"]["pass_id"])
        self.assertEqual(data["entry"]["name"], "Bikash Borah")

    def test_repair_review_signoff(self):
        """Post-Repair Verification: Worker/mechanic inspects and signs off on machine."""
        payload = {
            "machine_id": "M102",
            "worker_id": "W007",
            "worker_name": "Omkar Mishra",
            "repair_status": "REPAIRED & VERIFIED",
            "observations": "Replaced high-pressure fluid seal, completed 3000 PSI hydrostatic test, all guards restored.",
            "verified_safe": True
        }
        res = self.client.post('/api/machines/repair_review', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Verify entry exists in repair reviews list
        list_res = self.client.get('/api/machines/repair_reviews')
        self.assertEqual(list_res.status_code, 200)
        reviews = list_res.get_json()
        self.assertTrue(any(r["machine_id"] == "M102" for r in reviews))

    def test_auth_registration_and_login(self):
        """Auth Portal: Self-registration and login validation."""
        reg_payload = {
            "name": "Test Inspector",
            "username": "test_inspector",
            "password": "password123",
            "role": "hse",
            "department": "Safety Operations",
            "phone": "+91 91234 56789"
        }
        res = self.client.post('/api/auth/register', json=reg_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "HSE OFFICER")

        # Now test login with correct password
        login_res = self.client.post('/api/auth/login', json={
            "username": "test_inspector",
            "password": "password123",
            "role": "hse"
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertTrue(login_data["success"])
        self.assertEqual(login_data["user"]["username"], "test_inspector")

        # Cleanup test inspector to keep dataset and DB clean
        from database.database import get_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = 'test_inspector'")
        cursor.execute("DELETE FROM workers WHERE id = 'HSE_08'")
        conn.commit()
        conn.close()

    def test_auth_registration_without_username(self):
        """Auth Portal: Registration without providing a username automatically generates username."""
        reg_payload = {
            "name": "Auto Worker",
            "password": "password123",
            "role": "worker",
            "department": "Rig Engineering"
        }
        res = self.client.post('/api/auth/register', json=reg_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("user", data)
        auto_username = data["user"]["username"]
        self.assertTrue("autoworker" in auto_username)
        worker_id = data["user"]["id"]

        # Test login using assigned Worker ID
        login_res = self.client.post('/api/auth/login', json={
            "username": worker_id,
            "password": "password123",
            "role": "worker"
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertTrue(login_data["success"])

        # Cleanup
        from database.database import get_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (data["user"]["db_id"],))
        cursor.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
        conn.commit()
        conn.close()

    def test_clear_all_registrations_api(self):
        """API: /api/auth/clear_all_registrations purges biometrics and resets users."""
        from unittest.mock import patch
        with patch('routes.auth_routes.face_engine.clear_all_registrations', return_value={"success": True, "purged_samples": 0}):
            res = self.client.post('/api/auth/clear_all_registrations')
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertIn("details", data)

    def test_scan_frame_missing_image(self):
        """API: /api/safety_gate/scan_frame returns 400 when no image is sent."""
        res = self.client.post('/api/safety_gate/scan_frame', json={})
        self.assertEqual(res.status_code, 400)

    def test_auth_wrong_password_strictly_declined(self):
        """Strict Authentication: Login with wrong password MUST be declined with 401."""
        res = self.client.post('/api/auth/login', json={
            "username": "hse",
            "password": "definitely_wrong_password_999",
            "role": "hse"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Incorrect password", data["error"])

    def test_auth_unregistered_user_strictly_declined(self):
        """Strict Authentication: Unregistered username MUST be declined with 401."""
        res = self.client.post('/api/auth/login', json={
            "username": "unregistered_ghost_user",
            "password": "somepassword",
            "role": "worker"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not registered in the system", data["error"])

    def test_user_dossier_endpoint(self):
        """Personnel Profile & Safety Dossier: Returns complete identity, compliance, and history."""
        # 1. Register a test worker via self-registration
        reg_res = self.client.post('/api/auth/register', json={
            "name": "Test Dossier Worker",
            "password": "pass123Worker!",
            "role": "WORKER",
            "department": "Rig Drilling",
            "site": "Site A (Duliajan)",
            "phone": "+91 99999 88888",
            "address": "Camp 4"
        })
        self.assertEqual(reg_res.status_code, 200)
        data_reg = reg_res.get_json()
        assigned_id = data_reg["user"]["id"]
        db_id = data_reg["user"]["db_id"]

        try:
            res_worker = self.client.get(f'/api/auth/user_dossier?user_id={assigned_id}')
            self.assertEqual(res_worker.status_code, 200)
            data_w = res_worker.get_json()
            self.assertTrue(data_w["success"])
            self.assertIn("user", data_w)
            self.assertIn("compliance", data_w)
            self.assertIn("past_reports", data_w)
            self.assertIn("stats", data_w)
            self.assertEqual(data_w["user"]["id"], assigned_id)
            self.assertTrue(data_w["compliance"]["training_valid"])
            self.assertTrue(data_w["compliance"]["helmet_assigned"])

            # 2. HSE Officer Dossier
            res_hse = self.client.get('/api/auth/user_dossier?user_id=hse')
            self.assertEqual(res_hse.status_code, 200)
            data_h = res_hse.get_json()
            self.assertTrue(data_h["success"])
            self.assertEqual(data_h["user"]["username"], "hse")
            self.assertIn("hse_reviews", data_h)
        finally:
            conn = get_db()
            conn.execute("DELETE FROM users WHERE id = ?", (db_id,))
            conn.execute("DELETE FROM workers WHERE id = ?", (assigned_id,))
            conn.commit()
            conn.close()

    def test_ppe_yolo_engine_5_classes_strict_safe_to_enter(self):
        """YOLOv8 & Vision Engine: Strict 5 classes required for Safe to Enter (Goggles removed)."""
        from Ai_model.ppe_yolo_engine import PPEVisionEngine, PPE_CLASSES, SAFE_ENTRY_REQUIREMENTS
        engine = PPEVisionEngine()
        
        # Verify exact 5 detection classes (goggles removed)
        self.assertEqual(len(PPE_CLASSES), 5)
        self.assertIn("helmet", PPE_CLASSES)
        self.assertIn("safety_vest", PPE_CLASSES)
        self.assertNotIn("goggles", PPE_CLASSES)
        self.assertIn("gloves", PPE_CLASSES)
        self.assertIn("safety_boots", PPE_CLASSES)
        self.assertIn("face", PPE_CLASSES)

        # 1. All 5 satisfied + valid induction
        all_passed = {c: {"detected": True, "confidence": 0.95} for c in PPE_CLASSES}
        eval_pass = engine.evaluate_safe_to_enter(all_passed, worker_induction_valid=True, medical_cert_valid=True)
        self.assertTrue(eval_pass["safe_to_enter"])
        self.assertEqual(eval_pass["gate_status"], "ACCESS_GRANTED")
        self.assertEqual(len(eval_pass["missing_mandatory_items"]), 0)

        # 2. Missing safety boots -> STRICT ACCESS DENIED
        missing_boots = {c: {"detected": True, "confidence": 0.95} for c in PPE_CLASSES}
        missing_boots["safety_boots"]["detected"] = False
        eval_fail = engine.evaluate_safe_to_enter(missing_boots, worker_induction_valid=True, medical_cert_valid=True)
        self.assertFalse(eval_fail["safe_to_enter"])
        self.assertEqual(eval_fail["gate_status"], "DENIED_PPE_NON_COMPLIANT")
        self.assertIn("safety_boots", eval_fail["missing_mandatory_items"])

    def test_report_with_photo_attachment(self):
        """Photographic Evidence: Report saves image_data and returns it upon retrieval."""
        payload = {
            "worker_id": "W001",
            "site": "Site A (Duliajan)",
            "location": "Drill Rig #4",
            "activity": "Routine Plant Operations",
            "report_type": "Unsafe Condition",
            "text": "Detected pressurized gas line valve leaking near compressor housing.",
            "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBD..."
        }
        res = self.client.post('/api/reports/analyze', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        rep_id = data["report"]["id"]
        self.assertTrue(data["report"]["image_data"].startswith("data:image/jpeg"))

        # Retrieve via GET
        get_res = self.client.get(f'/api/reports/{rep_id}')
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.get_json()
        self.assertEqual(get_data["image_data"], payload["image_data"])

    def test_hse_report_deletion(self):
        """HSE Officer: Can permanently delete a false or test report from the system."""
        # Submit a report first
        payload = {
            "worker_id": "W003",
            "site": "Site B (Moran)",
            "location": "Scaffolding Area",
            "activity": "Working at Height / Scaffolding",
            "report_type": "Unsafe Act",
            "text": "Worker noticed unclipped safety harness hook on scaffold staging."
        }
        res = self.client.post('/api/reports/analyze', json=payload)
        self.assertEqual(res.status_code, 200)
        rep_id = res.get_json()["report"]["id"]

        # Delete it
        del_res = self.client.delete(f'/api/reports/{rep_id}')
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.get_json()
        self.assertTrue(del_data["success"])
        self.assertEqual(del_data["deleted_id"], rep_id)

        # Confirm 404
        check_res = self.client.get(f'/api/reports/{rep_id}')
        self.assertEqual(check_res.status_code, 404)

    def test_worker_post_repair_deflects_report(self):
        """Repair Verification: Verified repair restores machine and resolves linked incident reports."""
        # 1. Submit report referencing machine M102
        payload = {
            "worker_id": "W002",
            "site": "Site B (Moran)",
            "location": "Mud Pump Bay",
            "activity": "Pump / Equipment Maintenance",
            "machine_id": "M102",
            "report_type": "Incident",
            "text": "Mud pump hydraulic valve seal failed under pressure spraying fluid on floor."
        }
        res_rep = self.client.post('/api/reports/analyze', json=payload)
        self.assertEqual(res_rep.status_code, 200)
        rep_id = res_rep.get_json()["report"]["id"]

        # 2. Worker inspects & submits verified safe post-repair sign-off
        repair_payload = {
            "machine_id": "M102",
            "worker_id": "W002",
            "worker_name": "Dipankar Saikia",
            "repair_status": "REPAIRED & VERIFIED",
            "observations": "Replaced hydraulic seal, torque tested to 3200 PSI. No leakage observed.",
            "verified_safe": True
        }
        res_repair = self.client.post('/api/machines/repair_review', json=repair_payload)
        self.assertEqual(res_repair.status_code, 200)
        repair_data = res_repair.get_json()
        self.assertTrue(repair_data["success"])
        self.assertGreaterEqual(repair_data["deflected_reports_count"], 1)

        # 3. Verify report was deflected to RESOLVED & REPAIRED
        chk_res = self.client.get(f'/api/reports/{rep_id}')
        self.assertEqual(chk_res.status_code, 200)
        chk_rep = chk_res.get_json()
        self.assertEqual(chk_rep["status"], "RESOLVED & REPAIRED")
        self.assertIn("REPAIR VERIFIED", chk_rep["solution"])

    def test_gps_weather_endpoint(self):
        """Live GPS Weather: Queries client coordinates and returns device weather entry."""
        res = self.client.get('/api/site_conditions?lat=27.35&lon=95.31')
        self.assertEqual(res.status_code, 200)
        sites = res.get_json()
        self.assertIsInstance(sites, list)
        self.assertGreaterEqual(len(sites), 1)
        # Check if device GPS entry is present
        gps_entry = next((s for s in sites if s.get("is_device_gps")), None)
        self.assertIsNotNone(gps_entry)
        self.assertIn("GPS", gps_entry["site_id"])
        self.assertIn("temperature", gps_entry)

if __name__ == "__main__":
    unittest.main()
