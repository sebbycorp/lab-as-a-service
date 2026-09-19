"""Lab provisioner — tenant plan + offline-safe approve.

Encodes the isolation contract used by the portal and (later) PDM:

  - Bridges: ``vmbr-sNNN-{trust,dmz,unt}`` (never home ``vmbr0``; ``unt`` = untrust)
  - VMID base: ``2000 + N * 10`` (PA/Client/DMZ/VRouter + access LXC)
  - Trust CIDR: ``10.50.N.0/24`` inside ``10.50.0.0/16``
  - NEVER ``172.16.10.0/24`` (instructor / home lab LAN)

Approve stays online-less: if PDM/Proxmox env flags or credentials are
absent, we still allocate + mint Tailscale and mark the lab ready.
Students cannot destroy labs (``STUDENT_CAN_DESTROY = False``).
"""
from __future__ import annotations

import os
import secrets
from typing import Any

from . import proxmox
from . import tailscale

HOME_LAN_CIDR = "172.16.10.0/24"
LAB_SUPERNET = "10.50.0.0/16"
MAX_TENANT = 200
VMID_BASE_OFFSET = 2000
VMID_STRIDE = 10
STUDENT_CAN_DESTROY = False

# Linux IFNAMSIZ is 15. `vmbr-sNNN-untrust` is 17 chars — use `unt`.
BRIDGE_SUFFIXES = ("trust", "dmz", "unt")
# EDU-210 pack + dual-homed access LXC relative to vmid_base
ROLE_VMID_OFFSETS = {
    "pa": 0,
    "client": 1,
    "dmz": 2,
    "vrouter": 3,
}
ACCESS_LXC_OFFSET = 9


def _tenant_n(lab_id: int) -> int:
    n = int(lab_id)
    if n < 1 or n > MAX_TENANT:
        raise ValueError(f"lab_id {lab_id} out of range 1..{MAX_TENANT} (no wrap)")
    return n


def allocate_tenant(lab_id: int) -> dict[str, Any]:
    """Assign a private addressing plan that never overlaps 172.16.10.0/24."""
    n = _tenant_n(lab_id)
    slug = f"s{n:03d}"
    trust = f"10.50.{n}.0/24"
    vmid_base = VMID_BASE_OFFSET + n * VMID_STRIDE
    guest_vmids = {
        role: vmid_base + offset for role, offset in ROLE_VMID_OFFSETS.items()
    }
    bridges = [f"vmbr-{slug}-{suffix}" for suffix in BRIDGE_SUFFIXES]
    return {
        "lab_id": lab_id,
        "tenant_n": n,
        "tenant_slug": slug,
        "vmid_base": vmid_base,
        "trust_cidr": trust,
        "client_ip": f"10.50.{n}.20",
        "pa_ip": f"10.50.{n}.254",
        "dmz_ip": f"10.50.{n}.10",
        "vrouter_ip": f"10.50.{n}.1",
        "access_lxc_ip": f"10.50.{n}.2",
        "bridges": bridges,
        "guest_vmids": guest_vmids,
        "access_lxc_vmid": vmid_base + ACCESS_LXC_OFFSET,
        "notes": (
            f"Plan {slug}: bridges {', '.join(bridges)} (no vmbr0); "
            f"VMID base {vmid_base} (PA/Client/DMZ/VRouter + access LXC); "
            f"trust {trust} only. Never advertise {HOME_LAN_CIDR}."
        ),
    }


def mint_homepage_token() -> str:
    return secrets.token_urlsafe(16)


def mint_tailscale_placeholder(tenant_slug: str) -> dict:
    """Until Tailscale API is wired, store a placeholder for admin."""
    return {
        "tailscale_auth_key": "",
        "tailscale_notes": (
            f"Pending: mint one-off key tagged {tailscale.TAG_STUDENT} "
            f"(never {tailscale.TAG_ACCESS}); advertise only this tenant "
            f"trust CIDR. Untagged fallback until ACL tagOwners exist."
        ),
    }


def mint_tailscale_for_lab(tenant_slug: str, trust_cidr: str) -> dict:
    """Try Tailscale API (tags → untagged); fall back to placeholder notes."""
    if tailscale.configured():
        try:
            resp = tailscale.create_student_auth_key(
                tenant_slug=tenant_slug, trust_cidr=trust_cidr
            )
            key = resp.get("key") or ""
            untagged = bool(resp.get("minted_untagged"))
            tags = resp.get("minted_tags") or []
            tag_note = (
                "untagged fallback (merge docs/ACL-HUJSON.md tagOwners)"
                if untagged
                else f"tags={tags}"
            )
            return {
                "tailscale_auth_key": key,
                "tailscale_notes": (
                    f"Join: tailscale up --auth-key=<key> --accept-routes. "
                    f"{tag_note}. Only your lab {trust_cidr} + portal :8080; "
                    f"no home LAN {HOME_LAN_CIDR}."
                ),
                "minted_untagged": untagged,
            }
        except Exception as e:
            return {
                "tailscale_auth_key": "",
                "tailscale_notes": (
                    f"Tailscale API error: {e}. Admin: fix TAILSCALE_API_KEY "
                    "(tskey-api-)."
                ),
                "minted_untagged": False,
            }
    if tailscale.auth_key_only():
        return {
            "tailscale_auth_key": "",
            "tailscale_notes": (
                "Server has tskey-auth- only. Need tskey-api- in Vault/env to mint "
                f"per-student keys for {tenant_slug} / {trust_cidr}."
            ),
            "minted_untagged": False,
        }
    return mint_tailscale_placeholder(tenant_slug)


def _proxmox_offline() -> bool:
    """Approve must not fail when PDM/PVE is off or secrets are missing."""
    if os.environ.get("PROVISION_OFFLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    return not proxmox.configured()


def approve_lab(lab_id: int) -> dict[str, Any]:
    """Allocate tenant, optionally call PDM hooks, mint Tailscale.

    Always returns a ready allocation when the plan is valid. Missing
    Proxmox/PDM credentials set ``provision_offline=True`` and skip clones.
    """
    plan = allocate_tenant(lab_id)
    ts = mint_tailscale_for_lab(plan["tenant_slug"], plan["trust_cidr"])
    notes = [plan["notes"], "Bridges: " + ", ".join(plan["bridges"])]

    offline = _proxmox_offline()
    if offline:
        notes.append(
            "PDM/Proxmox creds absent or PROVISION_OFFLINE — "
            "offline approve (allocation + Tailscale only)."
        )
        notes.append(proxmox.provision_edu210_pack(plan)["notes"])
        notes.append(proxmox.provision_access_lxc(plan)["notes"])
    else:
        bridges = proxmox.create_isolated_bridges(plan)
        pack = proxmox.provision_edu210_pack(plan)
        access = proxmox.provision_access_lxc(plan)
        notes.extend([bridges["notes"], pack["notes"], access["notes"]])
        # Hooks are still TODO; treat skipped clones as not-yet-on-metal.
        if pack.get("status") == "skipped" and access.get("status") == "skipped":
            notes.append("PDM hooks present but not implemented — guests not cloned.")

    return {
        **plan,
        "tailscale_auth_key": ts.get("tailscale_auth_key", ""),
        "tailscale_notes": ts.get("tailscale_notes", ""),
        "status": "ready",
        "provision_offline": offline,
        "admin_notes": " ".join(notes),
    }


def plan_for_lab(lab_id: int) -> dict[str, Any]:
    """Rehydrate the deterministic tenant plan from a lab id (for PDM hooks)."""
    return allocate_tenant(lab_id)


def stop_lab(lab_id: int | None = None, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Admin stop. Offline: portal status only; PDM stop is a TODO hook."""
    resolved = plan or (plan_for_lab(lab_id) if lab_id else None)
    if resolved and proxmox.configured():
        return proxmox.stop_guests(resolved)
    return {"status": "skipped", "notes": "offline stop (portal status only)"}


def start_lab(lab_id: int | None = None, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Admin start. Offline: portal status only; PDM start is a TODO hook."""
    resolved = plan or (plan_for_lab(lab_id) if lab_id else None)
    if resolved and proxmox.configured():
        return proxmox.start_guests(resolved)
    return {"status": "skipped", "notes": "offline start (portal status only)"}


def destroy_lab(lab_id: int | None = None, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Admin-only destroy hook. Students have no portal route to this.

    Offline: SQLite row is cleared by the caller; PDM destroy is TODO.
    """
    if STUDENT_CAN_DESTROY:
        raise RuntimeError("students must not destroy labs")
    resolved = plan or (plan_for_lab(lab_id) if lab_id else None)
    if resolved and proxmox.configured():
        return proxmox.destroy_guests(resolved)
    return {
        "status": "skipped",
        "notes": "offline destroy (SQLite only; PDM teardown TODO)",
    }
