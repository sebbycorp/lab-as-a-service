"""Tailscale API helpers for lab-as-a-service.

Needs an API access token (tskey-api-...) or OAuth client credentials.
Device auth keys (tskey-auth-...) cannot mint new keys.

Minting (mirrors live CT 145):
  1. Try tagged key (tag:lab-student, optional tag:student-sNNN; never tag:lab-access)
  2. If ACL rejects tags (missing tagOwners), retry without the per-tenant tag
  3. If tags still fail, mint an untagged key so approve still works
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

TAG_PORTAL = "tag:lab-portal"
TAG_STUDENT = "tag:lab-student"
TAG_ACCESS = "tag:lab-access"
HOME_LAN_CIDR = "172.16.10.0/24"
LAB_SUPERNET = "10.50.0.0/16"


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


def _env_tag(name: str, default: str) -> str:
    raw = (os.environ.get(name) or default).strip()
    return raw or default


def student_tags(tenant_slug: str) -> list[str]:
    """Tags requested for a *student device* key (before untagged fallback).

    Only ``tag:lab-student`` (plus optional ``tag:student-sNNN``).
    Never attach ``tag:lab-access`` — that tag is an autoApprover for
    ``10.50.0.0/16`` and belongs on the dual-homed access LXC only.
    """
    tags = [_env_tag("TAILSCALE_TAG_STUDENT", TAG_STUDENT)]
    slug = (tenant_slug or "").strip()
    if slug:
        tags.append(f"tag:student-{slug}")
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def _is_tag_error(err: TailscaleError) -> bool:
    """True only for ACL/tagOwners rejections — not every body that mentions tags."""
    msg = str(err).lower()
    needles = (
        "invalid tags",
        "invalid tag",
        "unknown tag",
        "tag not found",
        "not in tagowners",
        "tagowners",
    )
    return any(n in msg for n in needles)


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


def _keys_path() -> str:
    return f"/tailnet/{urllib.parse.quote(_tailnet(), safe='')}/keys"


def _auth_key_payload(
    *,
    tags: list[str],
    description: str,
    expiry_seconds: int,
) -> dict:
    create: dict[str, Any] = {
        "reusable": False,
        "ephemeral": False,
        "preauthorized": True,
    }
    if tags:
        create["tags"] = list(tags)
    # Untagged fallback: omit `tags` entirely (empty list can be "invalid tags")
    return {
        "capabilities": {"devices": {"create": create}},
        "expirySeconds": expiry_seconds,
        "description": description,
    }


def _annotate(resp: dict, tags: list[str]) -> dict:
    out = dict(resp)
    out["minted_tags"] = list(tags)
    out["minted_untagged"] = not tags
    return out


def create_student_auth_key(
    *,
    tenant_slug: str,
    trust_cidr: str,
    description: str | None = None,
    expiry_seconds: int = 86400 * 14,
) -> dict:
    """Mint a one-off auth key, trying tags then falling back to untagged.

    Live CT 145 behavior: tagged mint is preferred once ACL tagOwners exist.
    Until then, an untagged key still lets the student join; grants must later
    restrict them to portal :8080 and 10.50.0.0/16 — never 172.16.10.0/24.
    """
    if not configured():
        raise TailscaleError(
            "Need TAILSCALE_API_KEY starting with tskey-api- (not tskey-auth-)"
        )

    desc = description or f"lab {tenant_slug} trust {trust_cidr}"
    requested = student_tags(tenant_slug)
    without_per_tenant = [t for t in requested if not t.startswith("tag:student-")]
    attempts: list[list[str]] = []
    for candidate in (requested, without_per_tenant, []):
        if candidate not in attempts:
            attempts.append(candidate)

    last_err: TailscaleError | None = None
    for tags in attempts:
        payload = _auth_key_payload(
            tags=tags, description=desc, expiry_seconds=expiry_seconds
        )
        try:
            return _annotate(_request("POST", _keys_path(), payload), tags)
        except TailscaleError as e:
            if _is_tag_error(e):
                last_err = e
                continue
            raise
    if last_err is not None:
        raise last_err
    raise TailscaleError("Unable to mint Tailscale auth key")


def acl_policy_fragment() -> str:
    """HuJSON fragment for Sebastian to merge into Tailscale ACL.

    tagOwners: tag:lab-portal / tag:lab-student / tag:lab-access
    grants: students → portal :8080 and 10.50.0.0/16 only.
    NEVER grant 172.16.10.0/24 (instructor / home lab LAN).
    """
    return f"""\
// Lab-as-a-service — merge into Tailscale Access Controls (HuJSON)
// Full copy-paste policy: docs/ACL-HUJSON.md
{{
  "tagOwners": {{
    "{TAG_PORTAL}": ["autogroup:admin"],
    "{TAG_STUDENT}": ["autogroup:admin"],
    "{TAG_ACCESS}": ["autogroup:admin"]
  }},
  "autoApprovers": {{
    "routes": {{
      "{LAB_SUPERNET}": ["{TAG_ACCESS}"]
    }}
  }},
  "grants": [
    {{
      "src": ["{TAG_STUDENT}"],
      "dst": ["{TAG_PORTAL}"],
      "ip": ["8080"]
    }},
    {{
      "src": ["{TAG_STUDENT}"],
      "dst": ["{LAB_SUPERNET}"],
      "ip": ["*"]
    }}
  ]
}}
// NEVER grant {HOME_LAN_CIDR} to {TAG_STUDENT} (instructor LAN).
// Grants are default-deny: omitting {HOME_LAN_CIDR} is the deny.
"""
