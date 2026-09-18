# Lab as a Service

Isolated student lab pods (EDU-210 / PAN academy style) with a light FastAPI portal, Tailscale access, and admin-only destroy.

## Repo contents
- `app/` — FastAPI + Jinja + SQLite portal
- `docs/DESIGN-MVP.md` — isolation + actor model
- `docs/DEPLOY-LXC.md` — Proxmox LXC deploy
- `docs/TAILSCALE.md` — student join + API token requirements
- `docs/STATUS.md` — what’s live vs next

## Quick run (dev)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # set ADMIN_PASSWORD; optional TAILSCALE_API_KEY=tskey-api-...
./run.sh
```

## Production
Deployed as LXC on Proxmox iceman (see `docs/STATUS.md` and `docs/DEPLOY-LXC.md`). Prefer PDM for guest lifecycle; secrets in Vault, never in git.
