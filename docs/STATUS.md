# Status (2026-09-18)

## Live
- Portal LXC on Proxmox **iceman**: CT **145** hostname `lab-portal`
- URL: http://172.16.10.150:8080 (lab LAN / VPN)
- systemd: `lab-portal` (onboot)
- Admin password: on operator machine only (not in git)

## MVP features
- Student request / status / personal Homepage links (`/h/<token>`) — no destroy
- Admin approve / stop / start / destroy
- Approve allocates `10.50.N.0/24` + VMID base (PDM clone stubbed)
- Tailscale helper + ACL fragment docs; minting needs `tskey-api-…`

## Access model
- Tailscale-only for students (not public GCP)
- Students must not reach instructor LAN `172.16.10.0/24`
- Destroy admin-only

## Vault
- `secret/lab/tailscale`: device auth keys (`TS_AUTHKEY` / `TAILSCALE_AUTHKEY`)
- Still need API access token field `TS_API_KEY` (`tskey-api-…`) for per-student key minting

## Next
1. Store/use Tailscale API token; mint keys on approve
2. Join portal LXC to tailnet with `tag:lab-portal`
3. Merge ACL fragment (`/admin/tailscale-acl`)
4. PDM linked-clone EDU-210 template pack onto isolated bridges
5. FortiGate deny lab VRFs → `172.16.10.0/24`
6. Scale on dedicated 128 GiB / 8 TB Proxmox host when ready
