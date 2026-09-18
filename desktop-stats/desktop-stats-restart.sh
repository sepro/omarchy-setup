#!/usr/bin/env bash
# Restart the desktop stats panel (stop any running instance, then start one).
set -u
SCRIPT="$HOME/.config/hypr/scripts/desktop-stats.py"
pkill -x -f "$(command -v python) $SCRIPT" 2>/dev/null
sleep 0.5
setsid nohup python "$SCRIPT" >/tmp/desktop-stats.log 2>&1 </dev/null &
disown 2>/dev/null || true
