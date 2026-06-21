#!/usr/bin/env bash
# Log a boot milestone to ~/.vinyl-boot.log (same format as src/boot_timing.py).
boot_milestone() {
  local label="${1:?label required}"
  local log="${HOME}/.vinyl-boot.log"
  local uptime
  uptime="$(awk '{print $1}' /proc/uptime)"
  printf '%7.2fs  %s\n' "$uptime" "$label" >>"$log"
}

boot_milestone_reset() {
  : >"${HOME}/.vinyl-boot.log"
}
