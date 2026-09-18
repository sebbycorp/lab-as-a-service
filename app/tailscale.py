"""Tailscale API helpers for lab-as-a-service.

Needs an API access token (tskey-api-...) or OAuth client credentials.
Device auth keys (tskey-auth-...) cannot mint new keys.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.tailscale.com/api/v2"


class TailscaleError(RuntimeError):
    pass


def _token() -> str:
    return (os.environ.get("TAILSCALE_API_KEY") or "").strip()


def _tailnet() -> str:
    # "-" means the default tailnet for this API token
    return (os.environ.get("TAILSCALE_TAILNET") or "-").strip() or "-"


def configured() -> bool:
    tok = _token()
    return bool(tok) and tok.startswith("tskey-api-")


def auth_key_only() -> bool:
    tok = _token()
    return bool(tok) and tok.startswith("tskey-auth-")


def _request(method: str, path: str, body: dict | None = None) -> Any:
    tok = _token()
    if not tok:
        raise TailscaleError("TAILSCALE_API_KEY not set")
    url = API + path
    data = None
    headers = {
        "Authorization": f"Bearer {tok}",
        "User-Agent": "lab-as-service-portal/1.0",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        raise TailscaleError(f"Tailscale API HTTP {e.code}: {err[:400]}") from e


def create_student_auth_key(
    *,
    tenant_slug: str,
    trust_cidr: str,
    description: str | None = None,
    expiry_seconds: int = 86400 * 14,
) -> dict:
    """Mint a one-off auth key tagged for this student lab.

    Tags expected to exist in the tailnet ACL tagOwners:
      - tag:lab-student
      - tag:lab-access
    Per-tenant tag tag:student-<slug> is optional; many orgs only use lab-student
    + ACL groups. We attach tag:lab-student and tag:lab-access.
    """
    if not configured():
        raise TailscaleError(
            "Need TAILSCALE_API_KEY starting with tskey-api- (not tskey-auth-)"
        )
    tags = ["tag:lab-student", "tag:lab-access"]
    # Optional per-tenant tag if ACL defines it
    tags.append(f"tag:student-{tenant_slug}")

    payload = {
        "capabilities": {
            "devices": {
                "create": {
                    "reusable": False,
                    "ephemeral": False,
                    "preauthorized": True,
                    "tags": tags,
                }
            }
        },
        "expirySeconds": expiry_seconds,
        "description": description
        or f"lab {tenant_slug} trust {trust_cidr}",
    }
    # Some tags may not exist yet — retry without per-tenant tag
    try:
        return _request(
            "POST",
            f"/tailnet/{urllib.parse.quote(_tailnet(), safe='')}/keys",
            payload,
        )
    except TailscaleError as e:
        if "tag:student-" in str(e) or "invalid tags" in str(e).lower():
            payload["capabilities"]["devices"]["create"]["tags"] = [
                "tag:lab-student",
                "tag:lab-access",
            ]
            return _request(
                "POST",
                f"/tailnet/{urllib.parse.quote(_tailnet(), safe='')}/keys",
                payload,
            )
        raise


def acl_policy_fragment() -> str:
    """HuJSON fragment for Sebastian to merge into Tailscale ACL."""
    return """\
// Lab-as-a-service — merge into Access Controls
{
  "tagOwners": {
    "tag:lab-portal": ["autogroup:admin"],
    "tag:lab-access": ["autogroup:admin"],
    "tag:lab-student": ["autogroup:admin"],
    // optional per-tenant tags created as tag:student-s001 etc.
  },
  "autoApprovers": {
    // subnet routers for student trust CIDRs (10.50.N.0/24)
    "routes": {
      "10.50.0.0/16": ["tag:lab-access"]
    }
  },
  "grants": [
    // Students can reach the portal
    {
      "src": ["tag:lab-student"],
      "dst": ["tag:lab-portal"],
      "ip": ["8080"]
    },
    // Students can reach advertised lab routes (further narrowed per-device later)
    {
      "src": ["tag:lab-student"],
      "dst": ["10.50.0.0/16"],
      "ip": ["*"]
    }
  ],
  // Harden: students must NOT reach home LAN
  // Prefer grants-only ACLs; if using ACLs legacy, deny 172.16.10.0/24 for tag:lab-student
}
"""
