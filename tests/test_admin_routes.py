import unittest
import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from database.database import get_db

class AdminRoutesTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_admin_page_renders(self):
        """Verify the /admin HTML dashboard renders with HTTP 200 OK."""
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Master Admin Portal", res.data)

    def test_admin_auth_flow(self):
        """Verify login rejection, successful login with credentials/PIN, and logout."""
        # Unauthorized without session or PIN
        res = self.client.get("/api/admin/workers")
        self.assertEqual(res.status_code, 401)

        # Rejection with wrong password
        res = self.client.post("/api/admin/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 401)

        # Successful login with credentials
        res = self.client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Check authenticated status
        res = self.client.get("/api/admin/check_auth")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["authenticated"])

        # Now authorized to list workers
        res = self.client.get("/api/admin/workers")
        self.assertEqual(res.status_code, 200)

        # Logout
        res = self.client.post("/api/admin/logout")
        self.assertEqual(res.status_code, 200)

        # Now unauthorized again
        res = self.client.get("/api/admin/workers")
        self.assertEqual(res.status_code, 401)

    def test_admin_pin_header_auth(self):
        """Verify X-Admin-Pin header allows direct authorized API access."""
        res = self.client.get("/api/admin/workers", headers={"X-Admin-Pin": "9988"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

    def test_admin_worker_crud(self):
        """Verify adding, updating, toggling clearance, and deleting a worker."""
        headers = {"X-Admin-Pin": "9988"}
        test_id = "WTST99"

        # 1. Add worker
        payload = {
            "id": test_id,
            "name": "Arunabh Baruah",
            "role": "Rig Assistant",
            "department": "Drilling & Production",
            "site": "Site A (Duliajan)",
            "training_valid": 1,
            "cert_valid": 1,
            "helmet_assigned": 1,
            "vest_assigned": 1,
            "gloves_assigned": 1,
            "shoes_assigned": 1
        }
        res = self.client.post("/api/admin/workers", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        # 2. Verify worker exists
        res = self.client.get("/api/admin/workers", headers=headers)
        self.assertEqual(res.status_code, 200)
        workers = res.get_json()["workers"]
        found = [w for w in workers if w["id"] == test_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "Arunabh Baruah")

        # 3. Update worker
        update_payload = {
            "name": "Arunabh Baruah (Senior)",
            "role": "Lead Rig Specialist",
            "department": "Offshore Rigging",
            "site": "Site B (Moran)",
            "training_valid": 1,
            "cert_valid": 1,
            "helmet_assigned": 1,
            "vest_assigned": 1,
            "gloves_assigned": 1,
            "shoes_assigned": 1
        }
        res = self.client.put(f"/api/admin/workers/{test_id}", json=update_payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        # 4. Toggle clearance
        res = self.client.post(f"/api/admin/workers/toggle_clearance/{test_id}", headers=headers)
        self.assertEqual(res.status_code, 200)

        # 5. Delete worker
        res = self.client.delete(f"/api/admin/workers/{test_id}", headers=headers)
        self.assertEqual(res.status_code, 200)

        # 6. Confirm deleted
        res = self.client.get("/api/admin/workers", headers=headers)
        workers = res.get_json()["workers"]
        self.assertFalse(any(w["id"] == test_id for w in workers))

    def test_admin_machine_crud(self):
        """Verify adding, updating, and deleting machinery."""
        headers = {"X-Admin-Pin": "9988"}
        mach_id = "MTST99"

        # 1. Add machine
        res = self.client.post("/api/admin/machines", json={
            "id": mach_id,
            "name": "Test Hydro Turbine T-99",
            "site": "Site C (Digboi)",
            "status": "OPERATIONAL",
            "last_maintenance": "2026-08-01",
            "due_date": "2026-09-30",
            "base_risk": 42
        }, headers=headers)
        self.assertEqual(res.status_code, 200)

        # 2. Update machine
        res = self.client.put(f"/api/admin/machines/{mach_id}", json={
            "name": "Test Hydro Turbine T-99 (Calibrated)",
            "site": "Site C (Digboi)",
            "status": "OPERATIONAL",
            "last_maintenance": "2026-08-01",
            "due_date": "2026-10-15",
            "base_risk": 35,
            "locked": 0,
            "lock_reason": ""
        }, headers=headers)
        self.assertEqual(res.status_code, 200)

        # 3. Delete machine
        res = self.client.delete(f"/api/admin/machines/{mach_id}", headers=headers)
        self.assertEqual(res.status_code, 200)

    def test_admin_system_stats(self):
        """Verify public/admin stats endpoint returns accurate metrics."""
        res = self.client.get("/api/admin/stats")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        stats = data["stats"]
        self.assertIn("workers_count", stats)
        self.assertIn("machines_count", stats)
        self.assertIn("endpoints", stats)

    def test_admin_gate_logs(self):
        """Verify gate access logs endpoint."""
        headers = {"X-Admin-Pin": "9988"}
        res = self.client.get("/api/admin/logs", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["logs"], list)

if __name__ == "__main__":
    unittest.main()
