# Design freeze — light MVP

## Actors

- **Student**: request + status + personal links. Cannot destroy.
- **Admin (Sebastian)**: approve, stop/start, destroy only.

## Data

SQLite `labs` table: identity, status machine, tenant allocation, homepage token, Tailscale auth key + notes.

Live portal (CT 145) also ships the student homepage two-row UI, Light/Dark theme, reusable student Tailscale keys, and admin remint (`POST /admin/labs/{id}/remint-ts`).

## Isolation (intent recorded now; enforced later)

| Layer | Mechanism |
|-------|-----------|
| L2 | Per-student bridges `vmbr-sNNN-*` (no home `vmbr0`) |
| L3 | Trust CIDR `10.50.N.0/24`; FortiGate deny → `172.16.10.0/24` |
| Identity | Tailscale ACL: student tag → own CIDR only |

## Provisioner

`approve` allocates tenant + marks `ready` with stub notes. Real PDM/qm clone deferred until 128 GiB host or iceman capacity allows.
