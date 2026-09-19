# FortiGate isolation for student labs

Goal: nothing from student lab VRFs / Tailscale-advertised `10.50.0.0/16` (or jump hosts) can reach instructor LAN `172.16.10.0/24` except the portal/access path you explicitly allow.

## Recommended policy (FortiGate 172.16.10.1)

1. Address objects
   - `LAB_STUDENT_NETS` = `10.50.0.0/16` (Tailscale advertised trusts if used)
   - `HOME_LAB_LAN` = `172.16.10.0/24`
   - `LAB_PORTAL` = `172.16.10.150` (and/or Tailscale portal)
2. Policy (deny)
   - src `LAB_STUDENT_NETS` → dst `HOME_LAN` → **DENY** (log)
3. Policy (allow narrow)
   - src Tailscale / admin → `LAB_PORTAL` :8080 ALLOW
4. Do **not** put student bridges on `vmbr0`.

Apply via FortiGate API (`secret/lab/fortigate`) or GUI. Automation hook: future `app/fortigate.py` on destroy/approve.

## Status
- Portal/access model uses isolated Proxmox bridges (no L2 to home LAN).
- FortiGate deny is belt-and-suspenders for any accidental route leak.
