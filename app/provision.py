"""Provisioner stub — records isolation intent; PDM clone comes later."""
from __future__ import annotations

import secrets


def allocate_tenant(lab_id: int) -> dict:
    """Assign a private addressing plan that never overlaps 172.16.10.0/24."""
    # Student N uses 10.50.N.0/24 — not routable to home LAN by design.
    n = lab_id  # simple: lab id == tenant octet
    if n < 1 or n > 200:
        n = (lab_id % 200) + 1
    trust = f"10.50.{n}.0/24"
    return {
        "tenant_slug": f"s{n:03d}",
        "vmid_base": 2000 + n * 10,
        "trust_cidr": trust,
        "client_ip": f"10.50.{n}.20",
        "pa_ip": f"10.50.{n}.254",
        "bridges": [
            f"vmbr-s{n:03d}-trust",
            f"vmbr-s{n:03d}-dmz",
            f"vmbr-s{n:03d}-untrust",
        ],
        "notes": (
            "STUB: would create isolated bridges (no vmbr0), "
            "linked-clone EDU-210 pack via PDM, dual-homed Tailscale access LXC "
            f"advertising only {trust}. Never advertise 172.16.10.0/24."
        ),
    }


def mint_homepage_token() -> str:
    return secrets.token_urlsafe(16)


def mint_tailscale_placeholder(tenant_slug: str) -> dict:
    """Until Tailscale API is wired, store a placeholder for admin."""
    return {
        "tailscale_auth_key": "",
        "tailscale_notes": (
            f"Pending: create reusable/ephemeral key tagged "
            f"tag:lab-access,tag:student-{tenant_slug}; "
            f"advertise only this tenant trust CIDR."
        ),
    }


def mint_tailscale_for_lab(tenant_slug: str, trust_cidr: str) -> dict:
    """Try Tailscale API; fall back to placeholder notes."""
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
                    f"Join: tailscale up --auth-key=<key> --accept-routes. "
                    f"Tags={resp.get('capabilities', {})}. "
                    f"Only your lab {trust_cidr} + portal; no home LAN."
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
