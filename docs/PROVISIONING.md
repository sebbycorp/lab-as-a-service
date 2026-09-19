# EDU-210 provisioning

## Templates (iceman)
| VMID | Name | Source |
|------|------|--------|
| 9101 | tpl-edu210-pa | clone of 301 |
| 9111 | tpl-edu210-client | clone of 311 |
| 9112 | tpl-edu210-dmz | clone of 312 |
| 9113 | tpl-edu210-vrouter | clone of 313 |

## Per-tenant
- Bridges: `vmbr-sNNN-{trust,unt,dmz,x4,x5}` (isolated, no uplink to home LAN)
- VMs: `20NN+` range from linked clones
- Access LXC `3NNN`: eth0=`vmbr0`, eth1=trust `192.168.1.5/24`, Tailscale `tag:lab-access` (jump host; lab stays on 192.168.1.0/24)

## Portal env
```
LAS_PROVISION=true
PVE_SSH_HOST=172.16.10.5
PVE_SSH_PASSWORD=...   # or PROXMOX_PASSWORD
```

Host scripts: `/usr/local/sbin/las-provision-tenant.sh` and `las-destroy-tenant.sh`.
