# Deploy portal LXC on iceman

Target (suggested): privileged or unprivileged Debian/Ubuntu LXC, 1 vCPU / 512–1024 MiB, static IP e.g. `172.16.10.150` on `vmbr0` (portal only — student labs stay off this path).

1. Create LXC via PDM (preferred) or `pct create` on iceman.
2. Install Python 3.11+, copy this repo to `/opt/lab-as-service` on CT 145 (`172.16.10.150`).
3. `python3 -m venv /opt/lab-as-service/.venv && .venv/bin/pip install -r requirements.txt`
4. Put secrets in `/opt/lab-as-service/.env` (`ADMIN_PASSWORD`, `SESSION_SECRET`, optional Tailscale). Values live in Vault KV v2 `secret/lab/portal` and `secret/lab/tailscale` — do not commit them.
5. systemd unit `lab-portal.service`:

```
[Unit]
Description=Lab as a Service portal
After=network.target

[Service]
WorkingDirectory=/opt/lab-as-service
EnvironmentFile=/opt/lab-as-service/.env
ExecStart=/opt/lab-as-service/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

6. `systemctl enable --now lab-portal`
7. FortiGate: allow Tailscale/admin to portal; do **not** put student lab bridges on vmbr0.
