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
    """Mint a reusable auth key for this student lab.

    Prefers tags tag:lab-student (+ optional tag:student-<slug>).
    Falls back to an untagged preauthorized key if ACL tagOwners are not set yet.
    Reusable so students can rejoin from multiple devices / reinstalls within expiry.
    """
    if not configured():
        raise TailscaleError(
            "Need TAILSCALE_API_KEY starting with tskey-api- (not tskey-auth-)"
        )

    base_caps = {
        "reusable": True,
        "ephemeral": False,
        "preauthorized": True,
    }
    # Tailscale API 400s if description contains '/'; sanitize CIDR (192.168.1.0/24 → 192.168.1.0-24).
    desc = description or "lab-{}-trust-{}".format(tenant_slug, trust_cidr.replace("/", "-"))
    path = f"/tailnet/{urllib.parse.quote(_tailnet(), safe='')}/keys"

    # Never put tag:lab-access on student keys (that tag auto-approves 10.50 routes for jump hosts).
    # Prefer simple lab-student tag. Per-tenant tags often 400 if not in ACL tagOwners.
    tag_sets = [
        ["tag:lab-student"],
        [],  # untagged fallback until ACL tagOwners exist
    ]
    last_err: Exception | None = None
    for tags in tag_sets:
        create = dict(base_caps)
        if tags:
            create["tags"] = tags
        payload = {
            "capabilities": {"devices": {"create": create}},
            "expirySeconds": expiry_seconds,
            "description": desc,
        }
        try:
            return _request("POST", path, payload)
        except TailscaleError as e:
            last_err = e
            continue
    raise TailscaleError(f"Could not mint auth key: {last_err}")


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
    // Students: SSH jump + browser desktop (noVNC)
    {
      "src": ["tag:lab-student"],
      "dst": ["tag:lab-access"],
      "ip": ["6080", "8443"]
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
