# Tailscale ACL for lab-as-a-service

Merge into https://login.tailscale.com/admin/acls

```jsonc
{
  "tagOwners": {
    "tag:lab-portal": ["autogroup:admin"],
    "tag:lab-access": ["autogroup:admin"],
    "tag:lab-student": ["autogroup:admin"]
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
    },
    {
      "src": ["autogroup:admin"],
      "dst": ["*"],
      "ip": ["*"]
    }
  ]
}
```

Students must not be granted `172.16.10.0/24`. Prefer grants-only ACLs (no broad accept for tag:lab-student).
