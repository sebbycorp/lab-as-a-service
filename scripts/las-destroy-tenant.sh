#!/bin/bash
set -euo pipefail
LAB_ID="${1:?lab_id}"
N=$((LAB_ID)); [[ "$N" -lt 1 || "$N" -gt 200 ]] && N=$(( (LAB_ID % 200) + 1 ))
for id in $((2000+N*10+1)) $((2000+N*10+2)) $((2000+N*10+3)) $((2000+N*10+4)); do
  qm stop "$id" --timeout 30 2>/dev/null || true
  qm destroy "$id" --purge 1 2>/dev/null || true
done
CT=$((3000+N))
pct stop "$CT" 2>/dev/null || true
pct destroy "$CT" 2>/dev/null || true
echo "destroyed lab_id=$LAB_ID n=$N"
