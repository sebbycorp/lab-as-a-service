"""Call iceman to provision/destroy EDU-210 pods via SSH + host scripts."""
from __future__ import annotations

import os
import shlex
from typing import Any


def enabled() -> bool:
    return os.environ.get("LAS_PROVISION", "").lower() in ("1", "true", "yes")


def _ssh_run(remote: str, timeout: int = 900) -> str:
    import paramiko

    host = os.environ.get("PVE_SSH_HOST", "172.16.10.5")
    user = os.environ.get("PVE_SSH_USER", "root")
    password = os.environ.get("PVE_SSH_PASSWORD") or os.environ.get("PROXMOX_PASSWORD") or ""
    if not password:
        raise RuntimeError("PVE_SSH_PASSWORD / PROXMOX_PASSWORD not set")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, allow_agent=False, look_for_keys=False, timeout=30)
    try:
        _i, stdout, stderr = client.exec_command(remote, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if code != 0 and "OK tenant=" not in out:
            raise RuntimeError(f"ssh exit {code}: {err or out}")
        return out
    finally:
        client.close()


def _mint_access_authkey(tenant_slug: str) -> str:
    """Mint a short-lived device auth key tagged tag:lab-access for the jump LXC."""
    try:
        from . import tailscale
    except ImportError:
        from app import tailscale  # type: ignore
    if not tailscale.configured():
        return ""
    import json
    import urllib.request

    api = os.environ.get("TAILSCALE_API_KEY", "").strip()
    if not api:
        return ""
    body = json.dumps({
        "capabilities": {
            "devices": {
                "create": {
                    "reusable": False,
                    "ephemeral": False,
                    "preauthorized": True,
                    "tags": ["tag:lab-access"],
                }
            }
        },
        "expirySeconds": 86400,
        "description": f"{tenant_slug}-access",
    }).encode()
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/tailnet/-/keys",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api}",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    return data.get("key") or ""


def provision_tenant(lab_id: int, tenant_slug: str) -> dict[str, Any]:
    if not enabled():
        return {"skipped": True, "reason": "LAS_PROVISION not enabled"}
    script = "/usr/local/sbin/las-provision-tenant.sh"
    access_key = ""
    try:
        access_key = _mint_access_authkey(tenant_slug)
    except Exception as e:
        access_key = ""
        access_err = str(e)
    else:
        access_err = ""
    if access_key:
        # pass key as 3rd arg; quote carefully
        remote = f"{shlex.quote(script)} {int(lab_id)} {shlex.quote(tenant_slug)} {shlex.quote(access_key)}"
    else:
        remote = f"{shlex.quote(script)} {int(lab_id)} {shlex.quote(tenant_slug)}"
    out = _ssh_run(remote)
    meta: dict[str, Any] = {"raw": out, "skipped": False}
    if access_err:
        meta["access_ts_error"] = access_err
    if access_key:
        meta["access_ts_key_minted"] = True
    for line in out.splitlines():
        if "=" in line and not line.startswith(" "):
            k, _, v = line.partition("=")
            if k in (
                "vmid_pa", "vmid_client", "vmid_dmz", "vmid_vrouter", "ctid_access",
                "bridge_trust", "pa_ip", "client_ip", "access_ip", "trust_lab",
                "access_tailscale",
            ):
                meta[k] = v.strip()
    return meta


def destroy_tenant(lab_id: int) -> dict[str, Any]:
    if not enabled():
        return {"skipped": True, "reason": "LAS_PROVISION not enabled"}
    out = _ssh_run(f"/usr/local/sbin/las-destroy-tenant.sh {int(lab_id)}")
    return {"raw": out, "skipped": False}
