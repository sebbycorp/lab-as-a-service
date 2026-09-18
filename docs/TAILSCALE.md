# Tailscale access (lab-as-a-service)

## Student flow
1. Request a lab on the portal (reachable via Tailscale once portal LXC is tagged `tag:lab-portal`).
2. Instructor approves → portal mints a **device auth key** via Tailscale API.
3. Student runs `tailscale up --auth-key=... --accept-routes`.
4. Student opens PAN/client IPs from their `/h/<token>` page. No home LAN (`172.16.10.0/24`).

## Instructor setup
1. Create an **API access token** in Tailscale admin (`tskey-api-...`), store in Vault `secret/lab/tailscale` as `TS_API_KEY` / `TAILSCALE_API_KEY`.
   - Device auth keys (`tskey-auth-...`) only join *one* machine; they cannot mint student keys.
2. Put `TAILSCALE_API_KEY` in portal LXC `/opt/lab-as-service/.env`.
3. Merge ACL fragment from `/admin/tailscale-acl` (tagOwners + grants).
4. Join portal LXC to the tailnet with tag `tag:lab-portal` (separate reusable auth key).
5. Later: dual-homed access LXC per pod advertises `10.50.N.0/24` with `tag:lab-access`.

## Destroy
Admin destroy clears the stored key from SQLite; revoke the device in Tailscale admin if it already joined.
