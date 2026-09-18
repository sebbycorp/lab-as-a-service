"""PDM / Proxmox hooks for per-student EDU-210 packs.

Prefer **Proxmox Datacenter Manager (PDM)** for guest lifecycle (clone, start,
stop, destroy). Direct PVE API is a fallback when PDM is not in the path.

Secrets stay in Vault / LXC `.env` — never in git.

This module is a real skeleton: naming, env flags, and TODO hooks are encoded
so approve can run offline when credentials are absent.

Isolation rules (must hold when hooks are implemented):
  - Bridges: ``vmbr-sNNN-*`` only — never attach student NICs to home ``vmbr0``
  - Advertise ``10.50.N.0/24`` only — NEVER ``172.16.10.0/24``
  - Students cannot destroy labs (portal has no student destroy route)
"""
from __future__ import annotations

import os
from typing import Any

HOME_LAN_CIDR = "172.16.10.0/24"
LAB_SUPERNET = "10.50.0.0/16"

# EDU-210 template pack roles (linked-clone sources live in PDM/PVE templates).
EDU210_ROLES = ("pa", "client", "dmz", "vrouter")
EDU210_ROLE_LABELS = {
    "pa": "PA",
    "client": "Client",
    "dmz": "DMZ",
    "vrouter": "VRouter",
}


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def configured() -> bool:
    """True only when an enable flag is set *and* non-empty credentials exist.

    Env flags (Vault → LXC .env, never git):
      PDM_ENABLED / PDM_URL / PDM_TOKEN
      PROXMOX_ENABLED / PROXMOX_HOST / PROXMOX_USER / PROXMOX_TOKEN_ID /
      PROXMOX_TOKEN_SECRET
    """
    pdm_on = _truthy("PDM_ENABLED") or _truthy("PROXMOX_ENABLED")
    pve_on = _truthy("PROXMOX_ENABLED") or _truthy("PDM_ENABLED")
    if not (pdm_on or pve_on):
        return False
    has_pdm = bool(_env("PDM_URL") and _env("PDM_TOKEN"))
    has_pve = bool(_env("PROXMOX_HOST") and _env("PROXMOX_TOKEN_SECRET"))
    return has_pdm or has_pve


def prefer_pdm() -> bool:
    """Guest lifecycle should go through PDM when its URL is set."""
    return bool(_env("PDM_URL"))


def create_isolated_bridges(plan: dict[str, Any]) -> dict[str, Any]:
    """TODO: create ``vmbr-sNNN-{trust,dmz,untrust}`` on the target node.

    Must not bridge onto ``vmbr0`` / {HOME_LAN_CIDR}.
    PDM/PVE: node network config (``/nodes/{{node}}/network``) then reload.
    """
    bridges = list(plan.get("bridges") or [])
    return {
        "status": "skipped",
        "notes": (
            "TODO PDM/PVE: create isolated bridges "
            + ", ".join(bridges)
            + f" (no vmbr0, never {HOME_LAN_CIDR})"
        ),
        "bridges": bridges,
    }


def provision_edu210_pack(plan: dict[str, Any]) -> dict[str, Any]:
    """TODO: PDM linked-clone of the EDU-210 pack (PA / Client / DMZ / VRouter).

    Intended flow (when credentials exist):
      1. create_isolated_bridges(plan)
      2. For each role in EDU210_ROLES, PDM/PVE linked-clone from the
         template VMID map (PROXMOX_TEMPLATE_PA / _CLIENT / _DMZ / _VROUTER)
         onto the matching ``vmbr-sNNN-*`` using plan['guest_vmids'][role]
      3. Do not start a guest on home LAN
      4. Record task IDs; students still cannot destroy

    Offline: returns skipped so portal approve still marks the lab ready.
    """
    roles = ", ".join(EDU210_ROLE_LABELS[r] for r in EDU210_ROLES)
    slug = plan.get("tenant_slug", "?")
    if not configured():
        return {
            "status": "skipped",
            "notes": (
                f"TODO PDM: linked-clone EDU-210 pack ({roles}) for {slug} "
                f"onto {', '.join(plan.get('bridges') or [])}. "
                "Creds absent — skipped."
            ),
        }
    # Credentials present — still a hook until PDM client is wired.
    return {
        "status": "skipped",
        "notes": (
            f"TODO PDM API: linked-clone EDU-210 pack ({roles}) "
            f"to VMIDs {plan.get('guest_vmids')} on bridges "
            f"{plan.get('bridges')}. Prefer PDM; PVE clone is fallback."
        ),
        "guest_vmids": plan.get("guest_vmids"),
    }


def provision_access_lxc(plan: dict[str, Any]) -> dict[str, Any]:
    """TODO: dual-homed Tailscale access LXC for this tenant.

    NICs:
      - tailnet (or WAN) for Tailscale
      - ``vmbr-sNNN-trust`` at 10.50.N.2 (not on vmbr0)
    Advertise **only** plan['trust_cidr'] (10.50.N.0/24).
    NEVER advertise {HOME_LAN_CIDR}.
    Tag the node ``tag:lab-access`` once ACL tagOwners exist.
    """
    trust = plan.get("trust_cidr", "")
    return {
        "status": "skipped",
        "notes": (
            "TODO PDM: dual-homed Tailscale access LXC "
            f"(VMID {plan.get('access_lxc_vmid')}) advertising only {trust}. "
            f"Never advertise {HOME_LAN_CIDR}."
        ),
        "advertise_routes": [trust] if trust else [],
        "vmid": plan.get("access_lxc_vmid"),
    }


def stop_guests(plan: dict[str, Any]) -> dict[str, Any]:
    """TODO: PDM stop of EDU-210 VMs + access LXC for this tenant."""
    return {
        "status": "skipped",
        "notes": f"TODO PDM: stop guests for {plan.get('tenant_slug')}",
    }


def start_guests(plan: dict[str, Any]) -> dict[str, Any]:
    """TODO: PDM start of EDU-210 VMs + access LXC for this tenant."""
    return {
        "status": "skipped",
        "notes": f"TODO PDM: start guests for {plan.get('tenant_slug')}",
    }


def destroy_guests(plan: dict[str, Any]) -> dict[str, Any]:
    """TODO: PDM destroy guests + bridges. Admin-only (portal enforces)."""
    return {
        "status": "skipped",
        "notes": (
            f"TODO PDM: destroy VMIDs {plan.get('guest_vmids')} "
            f"+ access LXC {plan.get('access_lxc_vmid')} "
            f"+ bridges {plan.get('bridges')} for {plan.get('tenant_slug')}"
        ),
    }
