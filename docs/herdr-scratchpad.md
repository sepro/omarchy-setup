# herdr scratchpad — for Omarchy

At login, a terminal running [herdr](https://herdr.dev) opens on Hyprland's
built-in scratchpad, with a Claude agent already started in its first pane.
Press **SUPER+S** to show or hide it. Nothing appears on your normal
workspaces.

---

## Install

```sh
./install.sh herdr-scratchpad
```

It will:

1. warn if `herdr` or `claude` isn't installed, and install `jq` if it's missing
2. copy `herdr-scratchpad.sh` into `~/.config/hypr/scripts/`
3. add a window rule and a launch line to `~/.config/hypr/autostart.lua`
4. start it right away (when run inside Hyprland)

## How it works

- `autostart.lua` runs the script once Hyprland starts. A window rule sends
  any window with class `org.omarchy.herdr-scratchpad` to
  `special:scratchpad`, and `silent` stops it from taking focus.
- The script opens herdr in the default terminal with that class, using
  `omarchy-launch-tui`. If that window is already open, it skips this step.
- It waits for the herdr server to report a pane. If no agent is running yet,
  it calls `herdr agent start claude --kind claude --pane <pane>`, so herdr
  tracks Claude as an agent.

Running the script a second time won't open another window or start another
Claude. herdr keeps its session on a server, so closing the terminal doesn't
stop Claude. Run the script again, or run `herdr`, to reattach.

## Uninstall

Delete the three `herdr-scratchpad` lines from `~/.config/hypr/autostart.lua`,
then `rm ~/.config/hypr/scripts/herdr-scratchpad.sh`.
