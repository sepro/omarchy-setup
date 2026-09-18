#!/usr/bin/env bash
#
# Open herdr in a terminal on Hyprland's scratchpad (SUPER+S) and make sure
# a Claude agent is running inside it. Started at login from autostart.lua;
# the window rule there sends the terminal to special:scratchpad silently.
#
# Safe to run again: it won't start a second Claude if herdr already has one.

APP_ID=org.omarchy.herdr-scratchpad

# When run from inside herdr (e.g. by the installer), drop its env vars or
# the new client thinks it is nested and exits.
unset $(compgen -e | grep '^HERDR_')

# Terminal on the scratchpad, unless one is already open there.
if ! hyprctl clients -j | jq -e --arg c "$APP_ID" 'any(.class == $c)' >/dev/null; then
  omarchy-launch-tui --app-id="$APP_ID" herdr
fi

# Wait for the herdr server to come up with a shell pane.
pane=
for _ in $(seq 60); do
  pane=$(herdr pane list 2>/dev/null | jq -r '.result.panes[0].pane_id // empty')
  [[ -n $pane ]] && break
  sleep 0.5
done
[[ -n $pane ]] || { echo "herdr-scratchpad: herdr server did not start" >&2; exit 1; }

# Start Claude in that pane unless an agent is already running.
if [[ $(herdr agent list 2>/dev/null | jq '.result.agents | length') == 0 ]]; then
  sleep 1   # let the shell reach its prompt
  herdr agent start claude --kind claude --pane "$pane"
fi
