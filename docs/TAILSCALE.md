# Tailscale access (lab-as-a-service)

## Student flow

1. Request a lab on the portal (reachable via Tailscale once portal LXC is tagged `tag:lab-portal`).
2. Instructor approves → portal mints a **reusable device auth key** via Tailscale API.
3. Student runs `tailscale up --auth-key=... --accept-routes` (OS tabs on `/h/<token>`).
4. Student opens Client noVNC and Firewall reverse-proxy from their homepage. No home LAN (`172.16.10.0/24`).

## Instructor setup

1. Create an **API access token** in Tailscale admin (`tskey-api-...`), store in Vault `secret/lab/tailscale` as `TS_API_KEY` / `TAILSCALE_API_KEY`.
   - Device auth keys (`tskey-auth-...`) only join *one* machine; they cannot mint student keys.
2. Put `TAILSCALE_API_KEY` in portal LXC `/opt/lab-as-service/.env`.
3. Merge ACL fragment from `/admin/tailscale-acl` (tagOwners + grants). Also see `docs/ACL-HUJSON.md`.
4. Join portal LXC to the tailnet with tag `tag:lab-portal` (separate reusable auth key).
5. Dual-homed access LXC per pod advertises the lab path with `tag:lab-access`.

## Student auth keys (reusable)

Approve and remint mint a **reusable**, preauthorized device auth key tagged **`tag:lab-student` only** (14-day expiry by default). Students can re-run `tailscale up --auth-key=... --accept-routes` after reinstalls or on another device without a new approve.

Implementation: `app/tailscale.py` → `create_student_auth_key()` sets `reusable: True`. Tag sets tried in order: `["tag:lab-student"]`, then untagged fallback if ACL `tagOwners` are not set yet. Per-tenant tags are **not** preferred (they often 400 if missing from ACL).

Admin UI (`/admin`) shows each lab’s key + notes and has **Remint key** (`POST /admin/labs/{id}/remint-ts`).

### Key description must not contain `/`

Tailscale API returns **HTTP 400** `description had invalid characters` if the key description includes `/`. Sanitize CIDRs before sending:

- `192.168.1.0/24` → `192.168.1.0-24`
- Example description: `lab-s001-trust-192.168.1.0-24`

## Jump / access keys (single-use)

Access jump keys (`tag:lab-access`) stay **single-use** (`reusable: False` in `app/proxmox_provision.py` → `_mint_access_authkey`). They join one jump LXC. **Only student keys are reusable.**

## Destroy

Admin destroy clears the stored student key from SQLite; revoke the device in Tailscale admin if it already joined.

## Vault

- API token: KV v2 `secret/lab/tailscale` (`TS_API_KEY` / `TAILSCALE_API_KEY`)
- Portal URLs / admin password: `secret/lab/portal` (see README ops section)

Never commit `tskey-*` values.
