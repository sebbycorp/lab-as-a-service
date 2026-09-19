#!/bin/bash
# Provision one EDU-210 student pod on iceman from templates 9101/9111/9112/9113.
# Usage: las-provision-tenant.sh <lab_id> <tenant_slug>
# Example: las-provision-tenant.sh 3 s003
set -euo pipefail

LAB_ID="${1:?lab_id}"
SLUG="${2:?tenant_slug}"
N=$((LAB_ID))
if [[ "$N" -lt 1 || "$N" -gt 200 ]]; then
  N=$(( (LAB_ID % 200) + 1 ))
fi

VMID_PA=$((2000 + N * 10 + 1))
VMID_CLIENT=$((2000 + N * 10 + 2))
VMID_DMZ=$((2000 + N * 10 + 3))
VMID_VROUTER=$((2000 + N * 10 + 4))
CTID_ACCESS=$((3000 + N))

BR_TRUST="vmbr-s$(printf '%03d' "$N")-trust"
BR_UNTRUST="vmbr-s$(printf '%03d' "$N")-unt"
BR_DMZ="vmbr-s$(printf '%03d' "$N")-dmz"
BR_EXTRA4="vmbr-s$(printf '%03d' "$N")-x4"
BR_EXTRA5="vmbr-s$(printf '%03d' "$N")-x5"

TPL_PA=9101
TPL_CLIENT=9111
TPL_DMZ=9112
TPL_VROUTER=9113

ensure_bridge() {
  local br="$1"
  if [[ ! -d "/sys/class/net/$br" ]]; then
    ip link add name "$br" type bridge
    ip link set "$br" up
  fi
  # Persist snippet
  local conf="/etc/network/interfaces.d/${br}"
  if [[ ! -f "$conf" ]]; then
    cat >"$conf" <<CFG
auto $br
iface $br inet manual
        bridge-ports none
        bridge-stp off
        bridge-fd 0
CFG
  fi
}

echo "Provisioning tenant=$SLUG n=$N bridges + VMs + access CT"

for br in "$BR_TRUST" "$BR_UNTRUST" "$BR_DMZ" "$BR_EXTRA4" "$BR_EXTRA5"; do
  ensure_bridge "$br"
done

clone_if_missing() {
  local tpl="$1" newid="$2" name="$3"
  if qm status "$newid" &>/dev/null; then
    echo "VM $newid exists"
    return
  fi
  qm clone "$tpl" "$newid" --name "$name" --full 0
}

clone_if_missing "$TPL_PA" "$VMID_PA" "${SLUG}-pa"
clone_if_missing "$TPL_CLIENT" "$VMID_CLIENT" "${SLUG}-client"
clone_if_missing "$TPL_DMZ" "$VMID_DMZ" "${SLUG}-dmz"
clone_if_missing "$TPL_VROUTER" "$VMID_VROUTER" "${SLUG}-vrouter"

# Rewire NICs to isolated bridges (academy layout)
# PA: net0 trust, net1 untrust, net2 trust, net3 dmz, net4 extra4, net5 extra5, net6 trust/mgmt-ish
qm set "$VMID_PA" \
  --net0 virtio,bridge="$BR_TRUST" \
  --net1 virtio,bridge="$BR_UNTRUST" \
  --net2 virtio,bridge="$BR_TRUST" \
  --net3 virtio,bridge="$BR_DMZ" \
  --net4 virtio,bridge="$BR_EXTRA4" \
  --net5 virtio,bridge="$BR_EXTRA5" \
  --net6 virtio,bridge="$BR_TRUST" || true

qm set "$VMID_CLIENT" --net0 virtio,bridge="$BR_TRUST" || true
qm set "$VMID_DMZ" --net0 virtio,bridge="$BR_DMZ" --net1 virtio,bridge="$BR_EXTRA4" || true
# VRouter stays on isolated bridges only (egress via access LXC / lab design, not home LAN)
qm set "$VMID_VROUTER" \
  --net0 virtio,bridge="$BR_UNTRUST" \
  --net1 virtio,bridge="$BR_TRUST" \
  --net2 virtio,bridge="$BR_UNTRUST" || true

qm start "$VMID_PA" || true
qm start "$VMID_CLIENT" || true
qm start "$VMID_DMZ" || true
qm start "$VMID_VROUTER" || true

# Access LXC: dual-homed vmbr0 + trust; Tailscale jump host (no route advertise of overlapping 192.168.1.0/24)
if ! pct status "$CTID_ACCESS" &>/dev/null; then
  # reuse debian template if present
  TPL=$(pveam list local | awk '/debian-12-standard/ {print $1; exit}')
  if [[ -z "${TPL:-}" ]]; then
    echo "WARN: no debian-12 template; skip access CT"
  else
    pct create "$CTID_ACCESS" "$TPL" \
      --arch amd64 \
      --hostname "${SLUG}-access" \
      --storage local-lvm --rootfs local-lvm:4 \
      --memory 512 --cores 1 \
      --net0 name=eth0,bridge=vmbr0,ip=dhcp \
      --net1 name=eth1,bridge="$BR_TRUST",ip=192.168.1.5/24 \
      --unprivileged 1 --features nesting=1,keyctl=1 \
      --onboot 1 --start 1 || true
    # TUN for Tailscale
    CONF="/etc/pve/lxc/${CTID_ACCESS}.conf"
    grep -q 'dev/net/tun' "$CONF" 2>/dev/null || {
      echo 'lxc.cgroup2.devices.allow: c 10:200 rwm' >>"$CONF"
      echo 'lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file' >>"$CONF"
      pct stop "$CTID_ACCESS" 2>/dev/null || true
      pct start "$CTID_ACCESS"
    }
  fi
fi


# Optional: join access CT to Tailscale with tag:lab-access
# Usage: pass auth key as $3 or set LAS_ACCESS_TS_AUTHKEY
join_access_tailscale() {
  local key="${3:-${LAS_ACCESS_TS_AUTHKEY:-}}"
  [[ -z "$key" ]] && return 0
  pct status "$CTID_ACCESS" &>/dev/null || return 0
  pct exec "$CTID_ACCESS" -- bash -lc 'command -v tailscale >/dev/null || (export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq curl ca-certificates && curl -fsSL https://tailscale.com/install.sh | sh)'
  # ensure eth1 up
  pct exec "$CTID_ACCESS" -- bash -lc 'ip link set eth1 up 2>/dev/null; ip addr add 192.168.1.5/24 dev eth1 2>/dev/null || true; ip -4 addr show eth0 | grep -q inet || dhclient -v eth0 || true'
  echo "$key" > /tmp/las-ts-${CTID_ACCESS}.key
  pct push "$CTID_ACCESS" /tmp/las-ts-${CTID_ACCESS}.key /tmp/ts.key
  pct exec "$CTID_ACCESS" -- bash -lc 'chmod 600 /tmp/ts.key; systemctl enable --now tailscaled; tailscale up --authkey="$(cat /tmp/ts.key)" --hostname='"${SLUG}"'-access --accept-routes=false --advertise-tags=tag:lab-access --ssh; rm -f /tmp/ts.key; sleep 2; tailscale ip -4'
  rm -f /tmp/las-ts-${CTID_ACCESS}.key
  echo "access_tailscale=joined"
}

join_access_tailscale "$@" || echo "WARN: access tailscale join failed"

cat <<OUT
OK tenant=$SLUG
vmid_pa=$VMID_PA
vmid_client=$VMID_CLIENT
vmid_dmz=$VMID_DMZ
vmid_vrouter=$VMID_VROUTER
ctid_access=$CTID_ACCESS
bridge_trust=$BR_TRUST
trust_lab=192.168.1.0/24
pa_ip=192.168.1.254
client_ip=192.168.1.20
access_ip=192.168.1.5
OUT
