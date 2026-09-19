# Status (2026-09-18)

## Live
- Portal LXC on Proxmox **iceman**: CT **145** hostname `lab-portal`
- URL: http://172.16.10.150:8080 (lab LAN / instructor VPN — not for students)
- systemd: `lab-portal` (onboot)
- Admin password: on operator machine / Vault only (not in git)
- Key minting on CT 145: **try tags, then fall back to untagged** if ACL
  `tagOwners` are missing. This repo mirrors that in `app/tailscale.py`
  (student keys get `tag:lab-student` only — never `tag:lab-access`).

## In-repo (production path, not MVP-only)
- Student request / status / personal Homepage links (`/h/<token>`) — **no destroy**
- Admin approve / stop / start / destroy (destroy is admin-only)
- `approve` allocates `vmbr-sNNN-*`, VMID base `2000+N*10`, trust `10.50.N.0/24`
- PDM/Proxmox provisioner **skeleton** in `app/proxmox.py` (linked-clone +
  access LXC hooks). Approve stays **offline-safe** if PDM/PVE creds are absent.
- Tailscale helper: tagged mint → untagged fallback; ACL fragment in
  `docs/ACL-HUJSON.md` and `/admin/tailscale-acl`
- Roadmap: `docs/ROADMAP.md`

## Access model
- Tailscale-only for students (not public GCP)
- Students reach portal **:8080** and **10.50.0.0/16** only
- Students must **never** reach instructor LAN `172.16.10.0/24`
- Destroy admin-only — students cannot destroy labs

## Vault
- `secret/lab/tailscale`: device auth keys (`TS_AUTHKEY` / `TAILSCALE_AUTHKEY`)
- Need API access token field `TS_API_KEY` / `TAILSCALE_API_KEY` (`tskey-api-…`)
  for per-student key minting
- Future: `secret/lab/proxmox` or `secret/lab/pdm` for PDM/PVE tokens
  (`PDM_URL`, `PDM_TOKEN`, or `PROXMOX_HOST` + `PROXMOX_TOKEN_*`)
- Never commit `.env` or tokens

## Isolation contract (encoded now; enforced as phases land)

| Layer | Rule |
|-------|------|
| L2 | `vmbr-sNNN-{trust,dmz,unt}` — no student NIC on `vmbr0` (`unt` = untrust, IFNAMSIZ) |
| L3 | Trust `10.50.N.0/24` inside `10.50.0.0/16` |
| Tailscale | Students: portal :8080 + 10.50.0.0/16. **Never** 172.16.10.0/24 |
| Lifecycle | PDM for guests; students cannot destroy |

## Next
Follow `docs/ROADMAP.md` in order:

1. **ACL** — merge `docs/ACL-HUJSON.md` (`tagOwners` + grants)
2. **Portal on Tailscale** — tag CT 145 `tag:lab-portal`; students use MagicDNS
3. **Template pack** — EDU-210 PA / Client / DMZ / VRouter + access LXC in PDM
4. **Per-student provision** — implement the TODO hooks in `app/proxmox.py`
5. **FortiGate deny** — lab VRFs / 10.50.0.0/16 → 172.16.10.0/24
6. **Scale host** — dedicated 128 GiB / 8 TB Proxmox node
