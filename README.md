# Lab as a Service

FastAPI + SQLite portal for isolated EDU-210 student lab pods. This repo is the source of truth for the live portal on **CT 145** (`http://172.16.10.150:8080/`).

Students request a lab, get a personal homepage after instructor approval, and connect over Tailscale. Destroy is admin-only. Student labs never advertise instructor LAN `172.16.10.0/24`.

## Student homepage (`/h/<token>`)

Two-row layout after the lab is approved:

1. **Network map** (left) — static diagram `app/static/img/edu210-network-map.png` — beside **Open devices** (Client noVNC, Firewall reverse-proxy, SSH-from-Client instructions).
2. **How to connect** (OS tabs: Windows / macOS / Linux) beside **Credentials**.

Light / Dark theme toggle lives in the base layout (`data-theme` on `<html>`, persisted as `localStorage` key `las-theme`).

### Lab host credentials (student page)

| Device   | Typical IP     | User     | Password      |
|----------|----------------|----------|---------------|
| Client   | 192.168.1.20   | lab-user | `Pal0Alt0!`   |
| Firewall | 192.168.1.254  | admin    | `W3lcome098!` |
| DMZ      | 192.168.50.10  | root     | `Pal0Alt0!`   |
| VRouter  | 192.168.1.10   | root     | `Pal0Alt0!`   |

Firewall is **not** the same password as Client / DMZ / VRouter.

## Admin (`/admin`)

- Lists active labs with each lab’s Tailscale auth key and notes.
- **Remint key** posts to `/admin/labs/{id}/remint-ts` (mints a new reusable student key).
- Approve / stop / start / destroy (destroy is admin-only).
- ACL fragment helper at `/admin/tailscale-acl`.

## Tailscale

Student keys are **reusable** (`reusable: True` in `app/tailscale.py`) so students can rejoin within the key expiry. Prefer tags `tag:lab-student` only.

Key **description must not contain `/`** — Tailscale API returns HTTP 400 (`description had invalid characters`). CIDRs are sanitized (`192.168.1.0/24` → `192.168.1.0-24`).

**Jump / access keys remain single-use** (`reusable: False`, tag `tag:lab-access`). Only student keys are reusable.

See `docs/TAILSCALE.md`.

## Run locally

```bash
cp .env.example .env   # set ADMIN_PASSWORD (local only; do not commit)
./run.sh
```

Or:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
set -a && . ./.env && set +a
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open http://127.0.0.1:8080 — Admin at `/admin`.

## Deploy (LXC on iceman)

See `docs/DEPLOY-LXC.md`. Live portal: CT 145 @ `172.16.10.150:8080`. Copy this tree to `/opt/lab-as-service` on the LXC.

## Ops credentials (Vault)

Portal admin password and URLs live in HashiCorp Vault **KV v2**. Document **paths only** — never paste secret values into git.

| Path | Fields |
|------|--------|
| `secret/lab/portal` | `portal_url`, `admin_url`, `ADMIN_PASSWORD` |
| `secret/lab/tailscale` | `TS_API_KEY` / `TAILSCALE_API_KEY` (must be `tskey-api-…`) |
| `secret/lab/fortigate` | FortiGate API (see `docs/FORTIGATE-DENY.md`) |

Runtime secrets on the LXC go in `/opt/lab-as-service/.env` (gitignored). SQLite state is `data/portal.db` (also gitignored).

## Isolation (intent)

- Per-student bridges `vmbr-sNNN-*` (no home `vmbr0`)
- Live EDU-210 pack stays on academy `192.168.1.0/24` behind a dual-homed Tailscale jump (`tag:lab-access`)
- FortiGate deny any → `172.16.10.0/24` from lab VRFs — `docs/FORTIGATE-DENY.md`
- Provisioning notes: `docs/PROVISIONING.md`

## Repo layout

```
app/          # FastAPI app, templates, static assets
docs/         # Tailscale, deploy, provisioning, ACL, FortiGate
scripts/      # Host-side provision/destroy (iceman)
.env.example  # Env var names only
```
