"""Tenant addressing + homepage/Tailscale helpers."""
from __future__ import annotations

import secrets


def allocate_tenant(lab_id: int) -> dict:
    """Assign tenant slug / VMID plan. Live pods use academy 192.168.1.0/24 on isolated bridges."""
    n = lab_id
    if n < 1 or n > 200:
        n = (lab_id % 200) + 1
    # Documented future: 10.50.N.0/24 subnet routes. Live EDU-210 pack stays 192.168.1.0/24
    # per academy; access is via Tailscale jump (tag:lab-access), not overlapping routes.
    trust = "192.168.1.0/24"
    return {
        "tenant_slug": f"s{n:03d}",
        "vmid_base": 2000 + n * 10,
        "trust_cidr": trust,
        "client_ip": "192.168.1.20",
        "pa_ip": "192.168.1.254",
        "bridges": [
            f"vmbr-s{n:03d}-trust",
            f"vmbr-s{n:03d}-dmz",
            f"vmbr-s{n:03d}-unt",
            f"vmbr-s{n:03d}-x4",
            f"vmbr-s{n:03d}-x5",
        ],
        "notes": (
            "Isolated bridges (no vmbr0), linked-clone EDU-210 templates, "
            "dual-homed Tailscale access LXC (tag:lab-access). Never advertise 172.16.10.0/24."
        ),
    }


def mint_homepage_token() -> str:
    return secrets.token_urlsafe(16)


def mint_tailscale_placeholder(tenant_slug: str) -> dict:
    return {
        "tailscale_auth_key": "",
        "tailscale_notes": (
            f"Pending: mint key tagged tag:lab-student for {tenant_slug}."
        ),
    }


def mint_tailscale_for_lab(tenant_slug: str, trust_cidr: str) -> dict:
    try:
        from . import tailscale
    except ImportError:
        from app import tailscale  # type: ignore

    if tailscale.configured():
        try:
            resp = tailscale.create_student_auth_key(
                tenant_slug=tenant_slug, trust_cidr=trust_cidr
            )
            key = resp.get("key") or ""
            return {
                "tailscale_auth_key": key,
                "tailscale_notes": (
                    f"Reusable join key (valid until expiry): tailscale up --auth-key=<key> --accept-routes. "
                    f"Only portal + your jump/lab; no home LAN ({trust_cidr} via access host)."
                ),
            }
        except Exception as e:
            return {
                "tailscale_auth_key": "",
                "tailscale_notes": f"Tailscale API error: {e}. Admin: fix TAILSCALE_API_KEY (tskey-api-).",
            }
    if tailscale.auth_key_only():
        return {
            "tailscale_auth_key": "",
            "tailscale_notes": (
                "Server has tskey-auth- only. Need tskey-api- in Vault/env to mint "
                f"per-student keys for {tenant_slug} / {trust_cidr}."
            ),
        }
    return mint_tailscale_placeholder(tenant_slug)
