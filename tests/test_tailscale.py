"""Tailscale minting: tags first, then untagged (live CT 145 behavior)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import re

from app import tailscale
from app.tailscale import TailscaleError, create_student_auth_key


def _grant_dst_values(fragment: str) -> list[str]:
    """Collect dst values from grant objects, ignoring // comments."""
    stripped = "\n".join(
        line.split("//", 1)[0] for line in fragment.splitlines()
    )
    return re.findall(r'"dst"\s*:\s*\[([^\]]*)\]', stripped)


class TagThenUntaggedMintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "TAILSCALE_API_KEY": "tskey-api-test",
                "TAILSCALE_TAILNET": "-",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()

    def test_tagged_mint_succeeds_without_fallback(self) -> None:
        with patch.object(tailscale, "_request", return_value={"key": "tskey-auth-ok"}) as req:
            resp = create_student_auth_key(tenant_slug="s001", trust_cidr="10.50.1.0/24")
        self.assertEqual(resp["key"], "tskey-auth-ok")
        self.assertFalse(resp.get("minted_untagged"))
        self.assertIn("tag:lab-student", resp["minted_tags"])
        self.assertIn("tag:lab-access", resp["minted_tags"])
        self.assertEqual(req.call_count, 1)
        sent_tags = req.call_args.args[2]["capabilities"]["devices"]["create"]["tags"]
        self.assertIn("tag:lab-student", sent_tags)
        self.assertIn("tag:lab-access", sent_tags)

    def test_invalid_tags_fall_back_to_untagged(self) -> None:
        """Mirror live CT 145: if ACL has no tagOwners, mint an untagged key."""
        tagged_err = TailscaleError('Tailscale API HTTP 400: {"message":"invalid tags"}')

        def _side_effect(_method, _path, body):
            tags = body["capabilities"]["devices"]["create"].get("tags") or []
            if tags:
                raise tagged_err
            return {"key": "tskey-auth-untagged"}

        with patch.object(tailscale, "_request", side_effect=_side_effect) as req:
            resp = create_student_auth_key(tenant_slug="s007", trust_cidr="10.50.7.0/24")

        self.assertEqual(resp["key"], "tskey-auth-untagged")
        self.assertTrue(resp["minted_untagged"])
        self.assertEqual(resp["minted_tags"], [])
        self.assertGreaterEqual(req.call_count, 2)
        last_tags = req.call_args.args[2]["capabilities"]["devices"]["create"].get("tags") or []
        self.assertEqual(last_tags, [])

    def test_unknown_tagowners_error_also_falls_back(self) -> None:
        err = TailscaleError("tag:lab-student is not in tagOwners")

        def _side_effect(_method, _path, body):
            tags = body["capabilities"]["devices"]["create"].get("tags") or []
            if tags:
                raise err
            return {"key": "tskey-auth-plain"}

        with patch.object(tailscale, "_request", side_effect=_side_effect):
            resp = create_student_auth_key(tenant_slug="s002", trust_cidr="10.50.2.0/24")
        self.assertTrue(resp["minted_untagged"])
        self.assertEqual(resp["key"], "tskey-auth-plain")

    def test_non_tag_errors_are_not_swallowed(self) -> None:
        with patch.object(
            tailscale,
            "_request",
            side_effect=TailscaleError("Tailscale API HTTP 401: unauthorized"),
        ):
            with self.assertRaises(TailscaleError) as ctx:
                create_student_auth_key(tenant_slug="s003", trust_cidr="10.50.3.0/24")
        self.assertIn("401", str(ctx.exception))

    def test_acl_fragment_never_grants_home_lan(self) -> None:
        fragment = tailscale.acl_policy_fragment()
        self.assertIn("tag:lab-portal", fragment)
        self.assertIn("tag:lab-student", fragment)
        self.assertIn("tag:lab-access", fragment)
        self.assertIn("10.50.0.0/16", fragment)
        self.assertIn("8080", fragment)
        # Home LAN may appear in comments as a deny, never as a grant destination
        self.assertNotIn('"dst": ["172.16.10.0/24"]', fragment)
        self.assertNotIn('"dst":["172.16.10.0/24"]', fragment)
        self.assertNotIn("172.16.10.0/24", " ".join(_grant_dst_values(fragment)))


if __name__ == "__main__":
    unittest.main()
