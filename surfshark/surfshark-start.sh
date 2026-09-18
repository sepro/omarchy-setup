#!/usr/bin/env bash
#
# Start Surfshark at login and take down its "Connected" toast. Surfshark
# sends it with critical urgency, which the Omarchy shell never expires, so
# it would otherwise stay on screen until clicked.
#
# Only toasts in the first two minutes are touched, and only ones whose
# summary contains "Connected" (the shell's dismiss IPC matches on summary).

uwsm-app -- surfshark &

for _ in $(seq 120); do
  sleep 1
  [[ $(omarchy-shell notifications dismiss "Connected" 2>/dev/null) == ok ]] && break
done
