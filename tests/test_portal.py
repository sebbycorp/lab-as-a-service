"""Portal approve stays usable without Proxmox credentials."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class OfflinePortalApproveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "portal.db"
        self.env = patch.dict(
            os.environ,
            {
                "ADMIN_PASSWORD": "test-admin",
                "SESSION_SECRET": "test-session-secret-not-for-git",
                "PROXMOX_ENABLED": "0",
                "PDM_ENABLED": "0",
            },
            clear=False,
        )
        self.env.start()
        os.environ.pop("PROXMOX_HOST", None)
        os.environ.pop("PDM_URL", None)
        os.environ.pop("TAILSCALE_API_KEY", None)

        from app import db

        self.db_patch = patch.object(db, "DB_PATH", db_path)
        self.db_patch.start()
        db.init_db()

        from app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.db_patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_student_cannot_destroy(self) -> None:
        r = self.client.post("/request", data={"student_name": "Ada", "student_email": "ada@school.edu"})
        self.assertEqual(r.status_code, 200)
        # Student pages have no destroy action
        status = self.client.get("/lab/1?email=ada@school.edu")
        self.assertNotIn("/admin/labs/1/destroy", status.text)
        home = self.client.get("/h/" + self._homepage_token())
        self.assertNotIn("Destroy", home.text)

    def test_admin_approve_offline(self) -> None:
        self.client.post("/request", data={"student_name": "Ada", "student_email": "ada@school.edu"})
        login = self.client.post("/admin/login", data={"password": "test-admin"})
        self.assertEqual(login.status_code, 200)
        approve = self.client.post("/admin/labs/1/approve")
        self.assertEqual(approve.status_code, 200)
        self.assertIn("s001", approve.text)
        self.assertIn("10.50.1.0/24", approve.text)

        status = self.client.get("/lab/1?email=ada@school.edu")
        self.assertIn("10.50.1.0/24", status.text)
        self.assertIn("172.16.10.0/24", status.text)  # shown as blocked
        self.assertIn("cannot destroy", status.text.lower())

    def _homepage_token(self) -> str:
        from app import db

        with db.connect() as conn:
            row = conn.execute("SELECT homepage_token FROM labs WHERE id = 1").fetchone()
        return row["homepage_token"]


if __name__ == "__main__":
    unittest.main()
