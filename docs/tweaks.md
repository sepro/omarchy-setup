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

## Weather widget: metric units and a fixed location

The system locale is `en_US`, so Omarchy's weather widget (`omarchy.weather`)
showed °F and mph. This sets `"unit": "metric"` on its entry in
`~/.config/omarchy/shell.json`, so it shows °C and km/h.

It also stores the location with coordinates via `omarchy-weather-location`
(`WEATHER_NAME` / `WEATHER_COORDS` at the top of `install.sh`, default Herent).
With only a name, the widget needs wttr.in for current conditions. When wttr.in
is down (it was, with a TLS error), the widget has nothing to show and hides
itself from the bar. With coordinates it fetches from Open-Meteo directly.
