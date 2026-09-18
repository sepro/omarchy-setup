# Desktop stats panel — for Omarchy

A translucent clock / CPU / RAM / temperature / disk column painted on the
wallpaper, underneath every window.

![Desktop stats panel](img/desktop-stats.jpg)

---

## Install

```sh
./install.sh desktop-stats
```


It will:

1. install `python-gobject`, `python-cairo`, `gtk4-layer-shell` if missing
2. copy both scripts into `~/.config/hypr/scripts/`
3. append the launch line to `~/.config/hypr/autostart.lua`
4. start the panel (when run inside Hyprland)

There is no geometry to patch — the panel reads the bar height and window gap
from Hyprland itself at startup. `DISKS` is the only constant worth checking by
eye, compare it with `findmnt`.

Nothing here touches `/usr/share/omarchy/`, so `omarchy update` won't fight it.

## Uninstall

```sh
pkill -f desktop-stats.py
rm ~/.config/hypr/scripts/desktop-stats*.{py,sh}
```

…then delete the `desktop-stats` block from `~/.config/hypr/autostart.lua`.

---

## What it is

A **GTK4 + wlr-layer-shell** surface pinned to the `BACKGROUND` layer, so it
paints over the wallpaper and under every window. Its input region is empty, so
it is entirely click-through — you cannot focus, move or close it by clicking,
and it never steals a click meant for the desktop.

It reads `/proc` and `/sys` directly; **`python-psutil` is not required**.

| Section | Source |
|---|---|
| CPU % + per-core bars | `/proc/stat`, sampled as a delta between ticks |
| RAM | `/proc/meminfo` (`MemTotal - MemAvailable`) |
| Temperatures | `/sys/class/hwmon/hwmon*/temp*_input` |
| Disks | `statvfs` |

Runtime cost is negligible: one `GLib.timeout` per second, with temps and disks
re-read only every 5s.

---

## The LD_PRELOAD trick (do not remove)

The first thing the script does is re-exec itself with

```
LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so.0
```

`gtk4-layer-shell` **must** be loaded before `libwayland-client`. If it isn't,
the layer surface silently degrades into an ordinary toplevel — the panel then
shows up as a regular tiled window in your layout instead of sitting on the
wallpaper. **If you ever see that, this is the reason.** Verify with:

```sh
hyprctl layers | grep desktop-stats     # should list a 'desktop-stats' namespace
```

---

## Restarting after an edit

```sh
~/.config/hypr/scripts/desktop-stats-restart.sh
```

Kills any running instance and relaunches detached, logging to
`/tmp/desktop-stats.log`. The panel does **not** hot-reload on save.

---

## Tuning

All constants live at the top of `desktop-stats.py`.

### Machine-specific — check these on every new install

| Constant | Meaning |
|---|---|
| `MARGIN_TOP` | Clears the Omarchy bar. Computed at startup from the bar height reported by `hyprctl monitors` plus the window gap. |
| `DISKS` | `[(label, mountpoint), …]`. **Ships as `root` + `boot`.** A mountpoint that doesn't exist is skipped silently, so a stale entry shows as a missing row rather than an error. |

On btrfs installs where `/` and `/home` are subvolumes of one pool, `statvfs`
reports identical figures for both — list only one, or you get a duplicated row
saying the same thing twice.

### Geometry

**The panel occupies exactly the box a tiled window would.** Nothing about its
position is hardcoded — it asks Hyprland at startup, so it keeps matching if
the look'n'feel changes:

```python
GAP           = hypr_gap()                      # general:gaps_out      -> 10
MARGIN_RIGHT  = GAP
MARGIN_TOP    = hypr_reserved_top() + GAP       # bar reserve (26) + gap -> 36
MARGIN_BOTTOM = GAP
```

On this machine that puts the surface at y 36→758 with its right edge at
x 1356 — pixel-identical to a tiled window's outer box, borders included.

| Helper | Reads | Falls back to |
|---|---|---|
| `hypr_gap()` | `hyprctl getoption general:gaps_out`, the `css` field's *right* value | `10` |
| `hypr_reserved_top()` | `hyprctl monitors`, the largest `reserved[1]` across monitors | `26` |

`gaps_out` is the window-to-screen-edge gap, and on a stock Omarchy install it
also equals the bare strip between two tiled windows (`2 × gaps_in`). To
override, assign a literal instead — `MARGIN_RIGHT = 20`.

| Constant | Value | Meaning |
|---|---|---|
| `CONTENT_W` | `252` | The text column. `WIDTH` is derived from this plus the padding, so widen the panel here. |
| `PAD_LEFT` | `36` / `58` | Inner padding. `58` in soft mode, where the backdrop's left fade has to *finish* before the text starts; `36` in hard mode, which needs no such room. |
| `PAD_RIGHT` | `36` | Inner padding on the right. |
| `HISTORY` | `90` | Samples per timeline, ≈90s. |
| `TICK_MS` | `1000` | Refresh interval. |

Content is vertically centred in whatever height the surface gets, so it stays
put on any screen. Sized for **1366×768**; on a bigger one there is plenty of
headroom, so you may want a larger `CONTENT_W` and a bigger clock.

### Keeping edges crisp

The backdrop's edges must land on whole pixels or cairo antialiases them into a
visible blur. Two things guarantee that, and both are easy to undo by accident:

* In hard mode the backdrop is drawn as `scrim(cr, 0, 0, width, height)` — the
  surface bounds exactly, which are integers by definition. Insetting it by a
  computed amount reintroduces the problem.
* The content origin is `round()`ed. Text and hairlines drawn at a fractional
  `y` blur the same way.

### Readability over the wallpaper

This is the part that needed the most work, and the part most likely to need
redoing on a different theme.

The original targeted a flat dark charcoal wallpaper, where white text plus a
1px shadow was enough. Omarchy's stock themes are mostly busy photographic or
illustrated backgrounds — on Koi Pond the pale lotus flowers sit directly under
the panel and the stock palette was simply unreadable there.

So the panel paints a **scrim** — a dark backdrop behind the content — in one
of two styles, chosen by a single line:

```python
SCRIM_SOFT = False   # False = flat rectangle (shipped);  True = feathered
```

**Hard** (shipped) fills the surface with a flat rectangle: uniform opacity,
square corners, crisp edges. Because the surface is already a tiled window's
box, the backdrop reads as a window among windows.

**Soft** ignores the surface bounds and draws a feathered band hugging the
content instead — fading in at the top, out at the bottom, in from the left —
so it melts into the wallpaper with no visible border. Set `MARGIN_RIGHT = 0`
alongside it to let it bleed off the screen edge, which is how it was
originally tuned.

Padding and fade extents key off `SCRIM_SOFT`, so flipping it is all that is
needed; nothing else has to change.

| Constant | Value | Meaning |
|---|---|---|
| `SCRIM_ALPHA` | `0.58` | Backdrop opacity, both modes. **`0` disables it entirely** and restores the original bare look — do that on a dark, flat wallpaper. |
| `SCRIM_HEAD` / `SCRIM_TAIL` | `46`/`58` soft, `22`/`22` hard | Fade distances above and below the content in soft mode; plain padding in hard mode. |
| `SCRIM_SIDE` | `46` | Soft mode only: left fade-in distance. Must be **less than `PAD_LEFT`**, or the fade eats the first characters of every line. |
| `FG`, `FG_DIM`, `FG_FAINT`, … | — | Text and graph palette, deliberately white/grey so it reads as part of the image rather than competing with the theme accent. |

`FG_FAINT` is `0.62` here, up from the original `0.50` — the load averages and
byte totals vanished over the light patches at the stock value.

**Checking it rather than eyeballing it.** Screenshot an empty workspace and
compare against the wallpaper file; guessing from a thumbnail is unreliable:

```sh
hyprctl dispatch 'hl.dsp.focus({ workspace = "9" })'   # an empty workspace
sleep 2 && grim /tmp/panel.png
hyprctl dispatch 'hl.dsp.focus({ workspace = "1" })'

# effective opacity in a text-free patch of the backdrop: expect ~SCRIM_ALPHA
W=$(magick ~/.local/state/omarchy/current/background -crop 60x15+1240+430 +repage -format '%[fx:mean*255]' info:)
S=$(magick /tmp/panel.png                            -crop 60x15+1240+430 +repage -format '%[fx:mean*255]' info:)
python -c "print(f'alpha = {1 - $S/$W:.2f}')"
```

Sample a patch with no text or graph track in it, or the number comes out high.

---

## Omarchy notes

**Autostart.** Omarchy's Hyprland config is Lua, not `.conf`. The launch line is

```lua
o.exec_on_start("python " .. os.getenv("HOME") .. "/.config/hypr/scripts/desktop-stats.py")
```

in `~/.config/hypr/autostart.lua`. Use `o.exec_on_start` (raw command), not
`o.launch_on_start` (which wraps it in `uwsm-app` for a graphical app).

**`hyprctl dispatch` is Lua too.** The old `hyprctl dispatch workspace 9` is a
syntax error on Omarchy; it is
`hyprctl dispatch 'hl.dsp.focus({ workspace = "9" })'`.

**This coexists with the Omarchy bar** — it sits on the BACKGROUND layer with
`exclusive_zone = -1`, so it reserves no space and the bar is unaffected. It is
a plain layer surface, not a Quickshell plugin, so `omarchy refresh shell` and
`omarchy update` leave it alone.

**Theme changes.** The panel does not follow the Omarchy theme — it is
monochrome by design. What a theme change *can* break is readability, since the
wallpaper changes with it. If you switch to a much darker background, drop
`SCRIM_ALPHA`; a much lighter one, raise it. To re-check automatically on every
theme change, drop a script in `~/.config/omarchy/hooks/` via
`omarchy hook install theme-set <script>`.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Appears as a normal tiled window | `LD_PRELOAD` re-exec failed — see above |
| Nothing appears at all | `cat /tmp/desktop-stats.log`; usually a missing dependency |
| Hidden behind the wallpaper | Some wallpaper tools also use the BACKGROUND layer and can cover it; Omarchy's own does not |
| Text unreadable on a new theme | Raise `SCRIM_ALPHA` |
| A disk row never resolves | Stale entry in `DISKS` |
| Sits under the bar, or misaligned with windows | `hyprctl` unreachable at startup, so `hypr_gap()` / `hypr_reserved_top()` fell back to their defaults |
| Backdrop edges look soft | An edge landed on a fractional pixel — see *Keeping edges crisp* |
| Squeezed / clipped on a small screen | Content is centred vertically; if it exceeds the screen, reduce the temp rows or `HISTORY` |
