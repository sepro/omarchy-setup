# Pond screensaver: the wallpaper with water ripples

The screensaver shows the current wallpaper as the surface of a pond, instead of
Omarchy's scrolling text. A slow swell keeps the whole picture gently moving,
and about every 10 seconds a drop of water falls somewhere: a small splash, then
a few subtle rings that spread out and fade.

[![Pond screensaver, click for the video](img/screensaver.jpg)](img/screensaver.mp4)

*Click the image for a 12-second clip ([screensaver.mp4](img/screensaver.mp4)).*

It uses whichever theme's background is active, so it works for every theme,
not just Koi Pond. It starts after the usual idle time (`idle.screensaver` in
`~/.config/omarchy/shell.json`, 150 s) and from **SUPER + ESC → Screensaver**.
Any key, mouse click or mouse movement ends it.

## Install

```sh
./install.sh screensaver
```

This:
- installs `mpv` if it is missing
- copies the shader, input bindings and exit script to `~/.config/pond-screensaver/`
- copies the launcher to `~/.local/bin/pond-screensaver`
- overrides the `system.screensaver` entry in
  `~/.config/omarchy/extensions/omarchy-menu.jsonc` so the menu starts it
- adds a `omarchy-launch-screensaver` shell function to `~/.bash_profile` so
  Omarchy's idle service starts it (see below)

## Settings

At the top of `~/.local/bin/pond-screensaver` (or `screensaver/pond-screensaver`
in this repo, then re-run the installer):

| Variable | Default | Meaning |
|---|---|---|
| `DROP_INTERVAL` | `10` | Average seconds between drops; `0` for none |
| `SWELL` | `1` | Strength of the slow wave over the whole picture; `0` for still water |
| `FPS` | `30` | Frame rate; about 6% CPU at 30, 10% at 60 on this laptop |

Ring size, speed and brightness are `#define`s and constants in `ripples.glsl`.

## How it works

`pond-screensaver` runs one full-screen `mpv` per monitor. mpv plays the
wallpaper as an endless 30 fps stream (`lavfi` `loop` filter, so the image is
decoded once), and `ripples.glsl`, an mpv user shader, bends it on the GPU.
The shader builds a height map of the water (the swell plus the rings of the
most recent drops), moves each pixel along the slope of that map to fake
refraction, and brightens the side of each ring that faces the light.

The window gets the class `org.omarchy.screensaver`, the same one as Omarchy's
own screensaver. That way Omarchy's window rules make it full screen, and the
idle service tracks it just like the stock one: closing it cancels the pending
lock, and leaving it running locks the screen at `idle.lock`. It also follows the
**Screensaver** toggle (SUPER + CTRL + O): when that is off, only the menu entry
starts it (`pond-screensaver force`).

Before opening its windows, `pond-screensaver` closes any open bar panel (rain
radar, downloads, clock, network…). An open panel holds the keyboard from a
full-screen overlay layer, so the new window would get no focus, Hyprland would
skip the fullscreen rule, and the screensaver would open as a small floating
window under the panel. Every shell panel answers a `close()` IPC call, so the
script closes each target listed by `qs ipc show` that has one.

`pond.lua` ends the screensaver on mouse movement, or when focus moves to a
window that isn't another screensaver. It waits 1.5 s first, so the window
opening doesn't count. When one monitor's screensaver closes, it closes the
others too. `input.conf` maps every other key and mouse button to quit.

### Why a shell function

Omarchy's idle service starts the screensaver with
`bash -lc "omarchy-launch-screensaver"`, and that name can't be shadowed with a
script in `~/.local/bin`: `/usr/share/omarchy/bin` comes first on `PATH`. A
login shell does read `~/.bash_profile`, though, and shell functions win over
`PATH` lookups, so a function of the same name redirects the call. If Omarchy
ever starts the screensaver another way, it quietly falls back to the stock text
screensaver. `pond-screensaver` also falls back to it when there is no
wallpaper or no mpv.

To go back to Omarchy's screensaver, remove the `sepro.screensaver` lines from
`~/.bash_profile` and `~/.config/omarchy/extensions/omarchy-menu.jsonc`.

## Try it

```sh
pond-screensaver force
```

The video in this page was rendered offline with the same shader through
ffmpeg's `libplacebo` filter:

```sh
ffmpeg -loop 1 -framerate 30 -t 40 -i ~/.local/state/omarchy/current/background \
  -vf "format=yuv420p,libplacebo=custom_shader_path=screensaver/ripples.glsl:format=yuv420p" out.mp4
```
