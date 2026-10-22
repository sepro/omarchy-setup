# Tweaks

Small one-off settings that don't belong to a bigger feature.

## Install

```sh
./install.sh tweaks
```

Each tweak below says what it changes and where.

## Browser keeps its address bar in full screen

`Super + F` fills the screen with the window, but Chrome (and other Chromium
browsers) hid its tabs and address bar. Hyprland normally tells the window it is
fullscreen too, and Chrome reacts by switching to its own F11-style fullscreen.

This adds one window rule to `~/.config/hypr/hyprland.lua` (marker
`sepro.browser-fullscreen`):

```lua
o.window({ tag = "chromium-based-browser" }, { sync_fullscreen = false })
```

With `sync_fullscreen` off, `Super + F` only changes Hyprland's own fullscreen
state; the browser still thinks it is a normal window and keeps its toolbar.
The `chromium-based-browser` tag comes from Omarchy's
`default/hypr/apps/browser.lua`, so Chromium, Brave, Edge, Vivaldi and Helium are
covered as well. Pressing F11 inside the browser still gives a real fullscreen
without the toolbar.

Check it with `hyprctl activewindow -j`: in full screen `fullscreen` is `2` and
`fullscreenClient` stays `0`.
