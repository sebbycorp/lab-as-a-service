# Tailscale access (lab-as-a-service)

Students join the tailnet and reach **only**:

- the portal on **TCP 8080** (`tag:lab-portal`)
- advertised lab routes in **10.50.0.0/16** (their `10.50.N.0/24`)

They must **never** reach instructor LAN **172.16.10.0/24**.

Full ACL text: `docs/ACL-HUJSON.md`. Portal copy: `/admin/tailscale-acl`.

## Student flow
1. Request a lab on the portal (reachable via Tailscale once CT 145 is tagged `tag:lab-portal`).
2. Instructor approves → portal mints a **device auth key** via Tailscale API.
3. Student runs `tailscale up --auth-key=... --accept-routes`.
4. Student opens PAN/client IPs from their `/h/<token>` page.
5. There is no destroy control on student pages.

## Key minting (mirrors live CT 145)

`app/tailscale.py` `create_student_auth_key()`:

1. **Tagged** — `tag:lab-student` + `tag:lab-access` (+ optional `tag:student-sNNN`)
2. If the API rejects tags (ACL missing `tagOwners`), retry without the per-tenant tag
3. If tags still fail, mint an **untagged** key so approve still succeeds

Untagged keys are a compatibility bridge. After Phase 1 (ACL merge),
re-approve and confirm `minted_untagged` is false.

Requires `TAILSCALE_API_KEY` starting with `tskey-api-`.
A device auth key (`tskey-auth-`) can join one machine; it cannot mint.

## Instructor setup
1. Create an **API access token** in Tailscale admin (`tskey-api-...`), store in Vault
   `secret/lab/tailscale` as `TS_API_KEY` / `TAILSCALE_API_KEY`.
2. Put `TAILSCALE_API_KEY` in portal LXC `/opt/lab-as-service/.env` (not git).
3. Merge `docs/ACL-HUJSON.md` (tagOwners + grants). Confirm no `172.16.10.0/24` grant.
4. Join portal LXC to the tailnet with tag `tag:lab-portal` (separate reusable key).
5. Set `PORTAL_PUBLIC_URL` to the Tailscale IP or MagicDNS name.
6. Later: dual-homed access LXC per pod advertises `10.50.N.0/24` with `tag:lab-access`.

Optional env (defaults shown):

```
TAILSCALE_TAILNET=-
TAILSCALE_TAG_STUDENT=tag:lab-student
TAILSCALE_TAG_ACCESS=tag:lab-access
```

## Tags

| Tag | Purpose |
|-----|---------|
| `tag:lab-portal` | Portal LXC (CT 145). Students may hit **:8080** only. |
| `tag:lab-student` | Student devices. Source of student grants. |
| `tag:lab-access` | Per-lab subnet router. May auto-approve `10.50.0.0/16` routes. |

## Destroy
Admin destroy clears the stored key from SQLite and calls the PDM destroy
hook (offline no-op today). Revoke the device in Tailscale admin if it
already joined. Students cannot destroy labs.
