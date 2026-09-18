# Surfshark tweaks — for Omarchy

Two fixes for the Surfshark VPN client:

- **Tray icon always visible.** The icon is pinned in the bar's tray instead
  of sitting in the collapsed drawer.
- **No sticky toast at login.** When Auto-Connect is on, Surfshark shows a
  "Connected" notification with *critical* urgency. The Omarchy shell never
  expires critical toasts, so it stayed on screen until you clicked it. It is
  now dismissed as soon as it appears. You can still find it in the
  notification history.

---

## Install

```sh
./install.sh surfshark
```

It will:

1. copy `surfshark-start.sh` into `~/.config/hypr/scripts/`
2. replace `o.launch_on_start("surfshark")` in `~/.config/hypr/autostart.lua`
   with a line that runs the wrapper
3. add `chrome_status_icon_1` to the tray's `pinned` list in
   `~/.config/omarchy/shell.json`, which reloads right away

## How it works

- The wrapper starts Surfshark. For up to two minutes, it then calls
  `omarchy-shell notifications dismiss "Connected"` once a second, and stops
  after the first dismissal.
- The shell's dismiss call matches on the notification summary only, not the
  app name. If another app shows a toast with "Connected" in its summary in
  that same window, it gets dismissed too.
- Surfshark is an Electron app, so its tray item has Electron's generic id,
  `chrome_status_icon_1`. If another Electron app with a tray icon starts
  first, the ids can swap. Check which is which with:
  `busctl --user get-property <service> /StatusNotifierItem org.kde.StatusNotifierItem Id`.

## Uninstall

Put `o.launch_on_start("surfshark")` back in `autostart.lua` in place of the
wrapper line, and remove the id from `pinned` in `shell.json`, or unpin it
from the tray menu.
