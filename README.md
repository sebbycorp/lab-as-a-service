# Lab as a Service

Isolated student lab pods (EDU-210 / PAN academy style) with a light FastAPI portal, Tailscale access, and admin-only destroy.

Students reach the portal on **:8080** and **10.50.0.0/16** only — **never** `172.16.10.0/24`. Students cannot destroy labs.

## Repo contents
- `app/` — FastAPI + Jinja + SQLite portal
- `app/tailscale.py` — key mint (tags, then untagged fallback; mirrors live CT 145)
- `app/provision.py` / `app/proxmox.py` — tenant plan + PDM hooks (offline-safe approve)
- `docs/DESIGN-MVP.md` — isolation + actor model
- `docs/DEPLOY-LXC.md` — Proxmox LXC deploy
- `docs/TAILSCALE.md` — student join + minting + API token
- `docs/ACL-HUJSON.md` — tagOwners + grants (no home LAN)
- `docs/STATUS.md` — what’s live vs next
- `docs/ROADMAP.md` — ACL → Tailscale portal → template pack → provision → FortiGate → scale

## Quick run (dev)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # set ADMIN_PASSWORD; optional TAILSCALE_API_KEY=tskey-api-...
./run.sh
```

```bash
python3 -m unittest discover -s tests -v
```

## Production
Deployed as LXC on Proxmox iceman CT 145 (see `docs/STATUS.md` and `docs/DEPLOY-LXC.md`). Prefer PDM for guest lifecycle; secrets in Vault, never in git. Approve works without Proxmox creds (`PROVISION_OFFLINE` / missing `PDM_*`).
