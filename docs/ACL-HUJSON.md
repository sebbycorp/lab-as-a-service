# Tailscale ACL (HuJSON) — lab-as-a-service

Merge this into the tailnet **Access Controls**. Students must reach the
portal on **:8080** and their lab supernet **10.50.0.0/16** only.

**NEVER** grant `172.16.10.0/24` (instructor / home lab LAN on iceman `vmbr0`).

Grants are default-deny. Omitting `172.16.10.0/24` is the deny. Do not add
it as a `dst` for `tag:lab-student`.

Portal UI also shows the same fragment at `/admin/tailscale-acl`.

## tagOwners

| Tag | Who may apply it | Used on |
|-----|------------------|---------|
| `tag:lab-portal` | `autogroup:admin` | Portal LXC (CT 145 `lab-portal`) |
| `tag:lab-student` | `autogroup:admin` | Student devices / student auth keys |
| `tag:lab-access` | `autogroup:admin` | Per-pod dual-homed access LXC (subnet router) |

Optional later: `tag:student-sNNN` owned by admin, for per-tenant ACLs.

## Grants (students)

1. `tag:lab-student` → `tag:lab-portal` **TCP 8080** only
2. `tag:lab-student` → `10.50.0.0/16` (per-device routes later narrow this to `10.50.N.0/24`)

No grant to `172.16.10.0/24`. No grant to `vmbr0` hosts.

## autoApprovers

`tag:lab-access` may advertise routes inside `10.50.0.0/16` only.

## Copy-paste HuJSON

```jsonc
// Lab-as-a-service — merge into Tailscale Access Controls (HuJSON)
{
  "tagOwners": {
    "tag:lab-portal": ["autogroup:admin"],
    "tag:lab-student": ["autogroup:admin"],
    "tag:lab-access": ["autogroup:admin"]
  },
  "autoApprovers": {
    "routes": {
      "10.50.0.0/16": ["tag:lab-access"]
    }
  },
  "grants": [
    {
      "src": ["tag:lab-student"],
      "dst": ["tag:lab-portal"],
      "ip": ["8080"]
    },
    {
      "src": ["tag:lab-student"],
      "dst": ["10.50.0.0/16"],
      "ip": ["*"]
    }
  ]
}
// NEVER grant 172.16.10.0/24 to tag:lab-student.
```

If the tailnet still uses legacy `"acls"` instead of `"grants"`, translate
the same intent: allow student → portal:8080 and student → 10.50.0.0/16,
and do not allow student → 172.16.10.0/24.

## After merge

1. Join portal LXC to the tailnet with `tag:lab-portal`.
2. Portal minting prefers `tag:lab-student` + `tag:lab-access`. Until
   tagOwners exist, CT 145 / this repo fall back to an **untagged** key
   so approve still works (see `docs/TAILSCALE.md`).
3. Per-student access LXCs advertise only `10.50.N.0/24` with `tag:lab-access`.
