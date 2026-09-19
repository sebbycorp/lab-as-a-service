"""Tenant allocation + offline-safe provisioner skeleton."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import provision


class AllocateTenantTests(unittest.TestCase):
    def test_encodes_bridge_vmid_and_trust_cidr(self) -> None:
        plan = provision.allocate_tenant(3)
        self.assertEqual(plan["tenant_slug"], "s003")
        self.assertEqual(plan["trust_cidr"], "10.50.3.0/24")
        self.assertEqual(plan["vmid_base"], 2030)
        self.assertEqual(
            plan["bridges"],
            ["vmbr-s003-trust", "vmbr-s003-dmz", "vmbr-s003-unt"],
        )
        self.assertTrue(all(b.startswith("vmbr-s003-") for b in plan["bridges"]))
        self.assertTrue(all(len(b) <= 15 for b in plan["bridges"]))
        self.assertNotIn("vmbr0", plan["bridges"])

    def test_never_uses_home_lan_as_trust(self) -> None:
        for lab_id in (1, 10, 50, 200):
            plan = provision.allocate_tenant(lab_id)
            self.assertTrue(plan["trust_cidr"].startswith("10.50."))
            self.assertNotEqual(plan["trust_cidr"], "172.16.10.0/24")
            self.assertNotIn("172.16", plan["client_ip"])
            self.assertNotIn("172.16", plan["pa_ip"])
        with self.assertRaises(ValueError):
            provision.allocate_tenant(201)

    def test_edu210_roles_are_encoded(self) -> None:
        plan = provision.allocate_tenant(1)
        self.assertIn("guest_vmids", plan)
        for role in ("pa", "client", "dmz", "vrouter"):
            self.assertIn(role, plan["guest_vmids"])
        self.assertIn("access_lxc_vmid", plan)


class OfflineApproveTests(unittest.TestCase):
    def test_approve_works_without_proxmox_creds(self) -> None:
        env = {
            "PROXMOX_ENABLED": "0",
            "PDM_ENABLED": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("PROXMOX_HOST", None)
            os.environ.pop("PDM_URL", None)
            os.environ.pop("PROXMOX_TOKEN_SECRET", None)
            result = provision.approve_lab(4)

        self.assertEqual(result["tenant_slug"], "s004")
        self.assertEqual(result["trust_cidr"], "10.50.4.0/24")
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["provision_offline"])
        self.assertIn("vmbr-s004-trust", result["admin_notes"])
        self.assertIn("offline", result["admin_notes"].lower())

    def test_enabled_flag_without_creds_stays_offline(self) -> None:
        with patch.dict(
            os.environ,
            {"PROXMOX_ENABLED": "1", "PDM_ENABLED": "1"},
            clear=False,
        ):
            os.environ.pop("PROXMOX_HOST", None)
            os.environ.pop("PDM_URL", None)
            os.environ.pop("PROXMOX_TOKEN_SECRET", None)
            os.environ.pop("PDM_TOKEN", None)
            result = provision.approve_lab(5)
        self.assertTrue(result["provision_offline"])
        self.assertEqual(result["status"], "ready")

    def test_students_cannot_destroy(self) -> None:
        self.assertTrue(hasattr(provision, "destroy_lab"))
        self.assertFalse(provision.STUDENT_CAN_DESTROY)


class ProxmoxHookTests(unittest.TestCase):
    def test_configured_false_without_secrets(self) -> None:
        from app import proxmox

        with patch.dict(os.environ, {"PROXMOX_ENABLED": "1"}, clear=False):
            os.environ.pop("PROXMOX_HOST", None)
            os.environ.pop("PDM_URL", None)
            os.environ.pop("PROXMOX_TOKEN_SECRET", None)
            os.environ.pop("PDM_TOKEN", None)
            self.assertFalse(proxmox.configured())

    def test_configured_true_with_pdm_env(self) -> None:
        from app import proxmox

        with patch.dict(
            os.environ,
            {
                "PDM_ENABLED": "1",
                "PDM_URL": "https://pdm.example.invalid",
                "PDM_TOKEN": "pdm-token-placeholder",
            },
            clear=False,
        ):
            self.assertTrue(proxmox.configured())

    def test_edu210_pack_hook_is_callable(self) -> None:
        from app import proxmox

        plan = provision.allocate_tenant(8)
        result = proxmox.provision_edu210_pack(plan)
        self.assertIn("skipped", result["status"])
        self.assertIn("PA", result["notes"].upper() + result["notes"])
        self.assertTrue(
            any(role in result["notes"] for role in ("PA", "Client", "DMZ", "VRouter"))
        )

    def test_access_lxc_hook_documents_dual_home(self) -> None:
        from app import proxmox

        plan = provision.allocate_tenant(8)
        result = proxmox.provision_access_lxc(plan)
        self.assertIn("10.50.8.0/24", result["notes"])
        self.assertNotIn("172.16.10.0/24", result.get("advertise_routes", []))


if __name__ == "__main__":
    unittest.main()
