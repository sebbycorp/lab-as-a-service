# Design freeze — isolation + actors

The portal MVP is live; this file is the isolation contract the
provisioner encodes. Full build order: `docs/ROADMAP.md`.

## Actors

- **Student**: request + status + personal links. **Cannot destroy.**
- **Admin (Sebastian)**: approve, stop/start, destroy only.

## Data

SQLite `labs` table: identity, status machine, tenant allocation, homepage token, Tailscale key/notes.

## Isolation (encoded in `app/provision.py` + `app/proxmox.py`)

| Layer | Mechanism |
|-------|-----------|
| L2 | Per-student bridges `vmbr-sNNN-{trust,dmz,unt}` (no home `vmbr0`) |
| L3 | Trust CIDR `10.50.N.0/24` inside `10.50.0.0/16`; FortiGate deny → `172.16.10.0/24` |
| Identity | Tailscale ACL: `tag:lab-student` → portal :8080 + 10.50.0.0/16 only |
| Lifecycle | Prefer PDM; secrets in Vault; students cannot destroy |

### Tenant plan (N = lab id, 1–200)

| Field | Value |
|-------|--------|
| slug | `sNNN` |
| bridges | `vmbr-sNNN-trust`, `vmbr-sNNN-dmz`, `vmbr-sNNN-unt` (`unt` = untrust; Linux names ≤15 chars) |
| VMID base | `2000 + N*10` |
| guests | PA `+0`, Client `+1`, DMZ `+2`, VRouter `+3` |
| access LXC | `+9`, dual-homed, advertise only `10.50.N.0/24` |
| client / PA | `10.50.N.20` / `10.50.N.254` |

## Provisioner

`approve_lab()` allocates the plan, mints Tailscale (tags → untagged
fallback), and calls PDM hooks **only** when env flags + credentials
exist. Missing Proxmox/PDM creds → offline ready (notes only).

TODO hooks in `app/proxmox.py`:

- linked-clone EDU-210 pack (PA / Client / DMZ / VRouter)
- dual-homed Tailscale access LXC
