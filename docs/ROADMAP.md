# Roadmap — Lab as a Service

Production path for the full system (not just the MVP portal stub).
Secrets stay in Vault. Prefer **PDM** for guest lifecycle. Students
cannot destroy labs.

## Phase 1 — ACL

- [ ] **Remove/replace** any legacy `"acls"` allow-all (`*:*`) before merging grants
- [ ] Merge `docs/ACL-HUJSON.md` into the tailnet Access Controls
- [ ] Confirm `tagOwners` for `tag:lab-portal`, `tag:lab-student`, `tag:lab-access`
- [ ] Confirm grants: students → portal **:8080** and **10.50.0.0/16** only
- [ ] Confirm **no** grant to **172.16.10.0/24**
- [ ] After tagOwners exist, re-approve a lab and confirm tagged (not untagged) mint
- [ ] Student keys use `tag:lab-student` only — never `tag:lab-access` (route autoApprover)

## Phase 2 — Portal on Tailscale

- [ ] Join CT 145 (`lab-portal` on iceman) with `tag:lab-portal`
- [ ] Store `TAILSCALE_API_KEY` (`tskey-api-…`) in Vault `secret/lab/tailscale` and LXC `.env`
- [ ] Point `PORTAL_PUBLIC_URL` at the portal’s Tailscale IP / MagicDNS name
- [ ] Students reach http://&lt;portal&gt;:8080 **only** via Tailscale (not public GCP)
- [ ] FortiGate/admin path to `172.16.10.150:8080` remains instructor-only

## Phase 3 — Template pack

- [ ] Import / golden-image the EDU-210 pack in PDM: **PA, Client, DMZ, VRouter**
- [ ] Record template VMIDs in Vault-backed env (`PROXMOX_TEMPLATE_PA`, …)
- [ ] Build the dual-homed Tailscale **access LXC** template (`tag:lab-access`)
- [ ] Confirm templates have no NIC on home `vmbr0` / `172.16.10.0/24`

## Phase 4 — Per-student provision

- [ ] Implement PDM linked-clone in `app/proxmox.py` hooks
- [ ] Create `vmbr-sNNN-{trust,dmz,unt}` per tenant (no `vmbr0`; `unt` = untrust)
- [ ] Clone pack onto those bridges using VMID base `2000 + N*10`
- [ ] Deploy access LXC advertising **only** `10.50.N.0/24`
- [ ] Approve stays offline-safe if PDM creds are absent (already true)
- [ ] Admin stop / start / destroy call PDM; students still have no destroy

## Phase 5 — FortiGate deny

- [ ] Deny lab VRFs / `10.50.0.0/16` → `172.16.10.0/24` on the FortiGate
- [ ] Verify a student Tailscale node cannot hit `172.16.10.0/24`
- [ ] Verify instructor can still reach portal + PDM from the home LAN

## Phase 6 — Scale host

- [ ] Move student pods to the dedicated 128 GiB / 8 TB Proxmox host
- [ ] Keep portal on iceman CT 145 (or migrate with the same hostname/tags)
- [ ] PDM manages both nodes; Vault remains the only secret store
- [ ] Capacity / backup runbook for N concurrent `10.50.N.0/24` tenants

## Already in this repo

| Piece | Where |
|-------|--------|
| Tag-then-untagged key mint | `app/tailscale.py` (mirrors live CT 145) |
| Tenant plan (bridges, VMID, CIDR) | `app/provision.py` |
| PDM/PVE TODO hooks | `app/proxmox.py` |
| Offline approve | `approve_lab()` when creds/flags absent |
| ACL fragment | `docs/ACL-HUJSON.md` + `/admin/tailscale-acl` |
