#!/usr/bin/env python3
"""
Desktop stats panel for Hyprland.

A GTK4 + wlr-layer-shell surface pinned to the BOTTOM layer, so it is
painted on top of the wallpaper and underneath every window. Fully
click-through (empty input region) — purely decorative.

BOTTOM rather than BACKGROUND: the wallpaper also lives on BACKGROUND, and
surfaces within one layer stack in the order they are mapped, so starting
before the wallpaper would leave the panel hidden behind it.

Sections: clock, CPU timeline, RAM timeline, temperatures, disk usage.
"""

import os
import sys

# gtk4-layer-shell must be loaded before libwayland-client, otherwise the layer
# surface silently degrades to a normal toplevel. Re-exec once with LD_PRELOAD.
_PRELOAD = "/usr/lib/libgtk4-layer-shell.so.0"
if os.path.exists(_PRELOAD) and _PRELOAD not in os.environ.get("LD_PRELOAD", ""):
    os.environ["LD_PRELOAD"] = ":".join(
        filter(None, [_PRELOAD, os.environ.get("LD_PRELOAD", "")]))
    os.execv(sys.executable, [sys.executable] + sys.argv)

import time
import math
import glob
import json
import subprocess
import collections

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

import cairo  # noqa: E402
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo, Gtk4LayerShell as LayerShell  # noqa: E402

def hypr_gap(default=10):
    """Hyprland's window gap, in pixels.

    `gaps_out` is the space a tiled window leaves against the screen edge, and
    here it also matches the bare strip between two tiled windows (2 x gaps_in).
    Read at startup rather than hardcoded so the panel lines up with whatever
    the machine's look'n'feel is set to. `css` is "top right bottom left".
    """
    try:
        out = subprocess.run(["hyprctl", "getoption", "general:gaps_out", "-j"],
                             capture_output=True, text=True, timeout=2, check=True)
        parts = json.loads(out.stdout)["css"].split()
        return int(float(parts[1 if len(parts) > 1 else 0]))
    except Exception:
        return default


def hypr_reserved_top(default=26):
    """Pixels the bar reserves at the top of the screen.

    `reserved` is [left, top, right, bottom]; the widest reservation across
    monitors is used so a taller bar on any one of them still clears.
    """
    try:
        out = subprocess.run(["hyprctl", "monitors", "-j"],
                             capture_output=True, text=True, timeout=2, check=True)
        return max(int(m["reserved"][1]) for m in json.loads(out.stdout))
    except Exception:
        return default


# ── layout ────────────────────────────────────────────────────────────
# Backdrop style. True feathers the backdrop's edges so the panel melts into
# the wallpaper; False draws a flat rectangle with hard edges and square
# corners. This is the only line to flip to switch between the two.
SCRIM_SOFT = False

# Occupy exactly the box a tiled window would: inset from every edge by the
# window gap, and below the bar's reserved strip. Both are read from Hyprland
# at startup, so the panel keeps matching if the look'n'feel changes.
GAP = hypr_gap()
MARGIN_RIGHT = GAP
MARGIN_TOP = hypr_reserved_top() + GAP
MARGIN_BOTTOM = GAP

CONTENT_W = 252          # the text column; panel width follows from the padding
# Soft mode needs a generous left pad: the backdrop's left fade-in has to
# finish before the text starts, or the first characters of every line sit on
# a half-transparent backdrop. A hard edge has no fade, so it pads evenly.
PAD_LEFT = 58 if SCRIM_SOFT else 36
PAD_RIGHT = 36
WIDTH = PAD_LEFT + CONTENT_W + PAD_RIGHT
HISTORY = 90             # samples kept per timeline (~90s)
TICK_MS = 1000

# ── palette (white / gray only) ───────────────────────────────────────
FG        = (1.00, 1.00, 1.00, 0.97)   # primary text
FG_DIM    = (1.00, 1.00, 1.00, 0.72)   # secondary text
FG_FAINT  = (1.00, 1.00, 1.00, 0.62)   # labels, units — lifted from the stock
                                       # 0.50, which disappeared over the pale
                                       # lotus flowers in this wallpaper
RULE      = (1.00, 1.00, 1.00, 0.20)   # hairlines
TRACK     = (0.00, 0.00, 0.00, 0.48)   # bar/graph backgrounds (dark, for contrast)
GUIDE     = (1.00, 1.00, 1.00, 0.16)   # guide lines inside graphs
LINE      = (1.00, 1.00, 1.00, 0.85)   # graph stroke
FILL_TOP  = (1.00, 1.00, 1.00, 0.26)
FILL_BOT  = (1.00, 1.00, 1.00, 0.03)
SHADOW    = (0.00, 0.00, 0.00, 0.70)   # 1px drop shadow, so text stays legible
                                       # over light patches of the wallpaper

# Soft scrim painted behind the content. The stock palette assumed a flat dark
# charcoal wallpaper; on a busy/light one (koi pond's pale lotus flowers sit
# right under this panel) white-on-wallpaper text washes out. SCRIM_ALPHA 0 to
# disable and fall back to the original bare look.
SCRIM_ALPHA = 0.58
# In soft mode these are fade distances; in hard mode they are plain padding
# between the box edge and the content, so they want to be even and smaller.
SCRIM_HEAD  = 46 if SCRIM_SOFT else 22   # above the content
SCRIM_TAIL  = 58 if SCRIM_SOFT else 22   # below it
SCRIM_SIDE  = 46         # soft mode only: fade-in distance from the left edge
SCRIM_PAD   = PAD_LEFT   # scrim starts at the panel edge, clear of the content

MONO = "JetBrainsMono Nerd Font"

# / and /home are subvolumes of one btrfs pool here, so statvfs reports
# identical figures for both — listing only root avoids a duplicated row.
DISKS = [("root", "/"), ("boot", "/boot")]


# ── collectors ────────────────────────────────────────────────────────
class Stats:
    def __init__(self):
        self.cpu_hist = collections.deque(maxlen=HISTORY)
        self.ram_hist = collections.deque(maxlen=HISTORY)
        self._prev = self._read_cpu()
        self.cpu = 0.0
        self.cores = []
        self.mem_used = self.mem_total = 0
        self.ram = 0.0
        self.temps = []
        self.disks = []
        self._slow_at = 0.0
        time.sleep(0.05)          # short delta so the first cpu sample is real
        self.sample()

    @staticmethod
    def _read_cpu():
        out = {}
        with open("/proc/stat") as fh:
            for line in fh:
                if not line.startswith("cpu"):
                    break
                parts = line.split()
                vals = [int(v) for v in parts[1:]]
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                out[parts[0]] = (sum(vals), idle)
        return out

    def _cpu_pct(self):
        cur = self._read_cpu()
        pcts = {}
        for key, (total, idle) in cur.items():
            ptotal, pidle = self._prev.get(key, (total, idle))
            dt, di = total - ptotal, idle - pidle
            pcts[key] = max(0.0, min(100.0, 100.0 * (dt - di) / dt)) if dt > 0 else 0.0
        self._prev = cur
        self.cpu = pcts.pop("cpu", 0.0)
        self.cores = [pcts[k] for k in sorted(pcts, key=lambda s: int(s[3:]))]

    def _mem(self):
        info = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                info[k] = int(v.split()[0])
        self.mem_total = info["MemTotal"]
        self.mem_used = info["MemTotal"] - info["MemAvailable"]
        self.ram = 100.0 * self.mem_used / self.mem_total

    def _temperatures(self):
        rows = []
        for hw in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
            try:
                name = open(os.path.join(hw, "name")).read().strip()
            except OSError:
                continue
            for inp in sorted(glob.glob(os.path.join(hw, "temp*_input"))):
                try:
                    value = int(open(inp).read()) / 1000.0
                except (OSError, ValueError):
                    continue
                if value <= 0 or value > 150:
                    continue
                label_file = inp.replace("_input", "_label")
                label = (open(label_file).read().strip()
                         if os.path.exists(label_file) else name)
                crit = 100.0
                for suffix in ("_crit", "_max"):
                    path = inp.replace("_input", suffix)
                    if os.path.exists(path):
                        try:
                            crit = int(open(path).read()) / 1000.0
                            break
                        except (OSError, ValueError):
                            pass
                if label.lower().startswith("package"):
                    label = "cpu package"
                elif name == "pch_skylake":
                    label = "chipset"
                rows.append((label.lower(), value, crit or 100.0))
        # cpu package first, then cores, then the rest
        order = {"cpu package": 0}
        rows.sort(key=lambda r: (order.get(r[0], 1 if r[0].startswith("core") else 2), r[0]))
        self.temps = rows[:5]

    def _disk(self):
        rows = []
        for label, path in DISKS:
            try:
                st = os.statvfs(path)
            except OSError:
                continue
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            if total == 0:
                continue
            rows.append((label, total - free, total))
        self.disks = rows

    def sample(self):
        self._cpu_pct()
        self._mem()
        self.cpu_hist.append(self.cpu)
        self.ram_hist.append(self.ram)
        now = time.monotonic()
        if now - self._slow_at > 5:      # temps/disks change slowly
            self._slow_at = now
            self._temperatures()
            self._disk()


# ── cairo helpers ─────────────────────────────────────────────────────
def rgba(cr, color):
    cr.set_source_rgba(*color)


def text(cr, x, y, string, size, color, weight=Pango.Weight.NORMAL,
         align="left", width=None, letter_spacing=0, family=MONO):
    layout = PangoCairo.create_layout(cr)
    desc = Pango.FontDescription()
    desc.set_family(family)
    desc.set_absolute_size(size * Pango.SCALE)
    desc.set_weight(weight)
    layout.set_font_description(desc)
    if letter_spacing:
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_letter_spacing_new(int(letter_spacing * Pango.SCALE)))
        layout.set_attributes(attrs)
    layout.set_text(string, -1)
    tw, th = layout.get_pixel_size()
    if align == "right":
        x -= tw
    elif align == "center":
        x -= tw / 2
    rgba(cr, (SHADOW[0], SHADOW[1], SHADOW[2], SHADOW[3] * color[3]))
    cr.move_to(x + 1, y + 1)
    PangoCairo.show_layout(cr, layout)
    rgba(cr, color)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return tw, th


def rule(cr, x, y, w):
    rgba(cr, (0, 0, 0, 0.35))
    cr.rectangle(x, y + 1, w, 1)
    cr.fill()
    rgba(cr, RULE)
    cr.rectangle(x, y, w, 1)
    cr.fill()


def section(cr, x, y, w, title):
    """Small caps label with a hairline running to the right edge."""
    tw, th = text(cr, x, y, title.upper(), 9.5, FG_FAINT,
                  weight=Pango.Weight.MEDIUM, letter_spacing=2.2)
    rule(cr, x + tw + 8, y + th / 2, w - tw - 8)
    return y + th + 9


def bar(cr, x, y, w, h, frac, radius=None):
    r = radius if radius is not None else h / 2
    def rounded(width):
        if width < 0.5:
            return
        width = max(width, min(2 * r, w))
        cr.new_sub_path()
        cr.arc(x + width - r, y + r, r, -math.pi / 2, math.pi / 2)
        cr.arc(x + r, y + r, r, math.pi / 2, 3 * math.pi / 2)
        cr.close_path()
    rgba(cr, TRACK)
    rounded(w)
    cr.fill()
    rgba(cr, FG)
    rounded(w * max(0.0, min(1.0, frac)))
    cr.fill()


def timeline(cr, x, y, w, h, values):
    """Filled area chart of a 0-100 series, oldest sample on the left."""
    rgba(cr, TRACK)
    cr.rectangle(x, y, w, h)
    cr.fill()

    # faint 50% guide
    cr.save()
    cr.set_dash([1, 3])
    cr.set_line_width(1)
    rgba(cr, GUIDE)
    cr.move_to(x, y + h / 2 + 0.5)
    cr.line_to(x + w, y + h / 2 + 0.5)
    cr.stroke()
    cr.restore()

    n = len(values)
    if n < 2:
        return
    step = w / (HISTORY - 1)
    x0 = x + w - (n - 1) * step
    pts = [(x0 + i * step, y + h - (min(100.0, v) / 100.0) * (h - 1) - 0.5)
           for i, v in enumerate(values)]

    grad = cairo.LinearGradient(0, y, 0, y + h)
    grad.add_color_stop_rgba(0, *FILL_TOP)
    grad.add_color_stop_rgba(1, *FILL_BOT)
    cr.move_to(pts[0][0], y + h)
    for px, py in pts:
        cr.line_to(px, py)
    cr.line_to(pts[-1][0], y + h)
    cr.close_path()
    cr.set_source(grad)
    cr.fill()

    rgba(cr, LINE)
    cr.set_line_width(1.2)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.move_to(*pts[0])
    for pt in pts[1:]:
        cr.line_to(*pt)
    cr.stroke()

    # leading-edge dot
    rgba(cr, FG)
    cr.arc(pts[-1][0] - 1, pts[-1][1], 1.8, 0, 2 * math.pi)
    cr.fill()


def scrim(cr, x, y, w, h):
    """Soft translucent band behind the content.

    The stock palette assumed a flat dark wallpaper; over a busy or light one
    (koi pond's pale lotus flowers sit right under this panel) white-on-image
    text washes out. A hard-edged box would read as a window, so this fades in
    at the top, out at the bottom and in from the left, and runs off the right
    screen edge — no visible border anywhere.
    """
    if SCRIM_ALPHA <= 0 or h <= 0 or w <= 0:
        return

    if not SCRIM_SOFT:
        # Flat rectangle: hard edges, square corners, uniform opacity.
        cr.set_source_rgba(0, 0, 0, SCRIM_ALPHA)
        cr.rectangle(x, y, w, h)
        cr.fill()
        return

    head = min(SCRIM_HEAD, h / 3.0)
    tail = min(SCRIM_TAIL, h / 3.0)

    vert = cairo.LinearGradient(0, y, 0, y + h)
    vert.add_color_stop_rgba(0.0, 0, 0, 0, 0.0)
    vert.add_color_stop_rgba(head / h, 0, 0, 0, SCRIM_ALPHA)
    vert.add_color_stop_rgba(1.0 - tail / h, 0, 0, 0, SCRIM_ALPHA)
    vert.add_color_stop_rgba(1.0, 0, 0, 0, 0.0)

    side = min(SCRIM_SIDE, w / 2.0)
    horiz = cairo.LinearGradient(x, 0, x + side, 0)
    horiz.add_color_stop_rgba(0.0, 0, 0, 0, 0.0)
    horiz.add_color_stop_rgba(1.0, 0, 0, 0, 1.0)

    cr.save()
    cr.rectangle(x, y, w, h)
    cr.clip()
    cr.set_source(vert)
    cr.mask(horiz)          # alphas multiply: vertical profile × left fade-in
    cr.restore()


def human_bytes(n):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if (n >= 10 or unit in "BK") else f"{n:.1f}{unit}"
        n /= 1024.0


# ── sections ──────────────────────────────────────────────────────────
def draw_clock(cr, x, y, w):
    now = time.localtime()
    _, h = text(cr, x - 2, y, time.strftime("%H:%M", now), 52,
                FG, weight=Pango.Weight.THIN)
    y += h - 6
    text(cr, x + w, y - 20, time.strftime("%S", now), 15,
         FG_FAINT, weight=Pango.Weight.LIGHT, align="right")
    text(cr, x, y, time.strftime("%A, %d %B %Y", now).lower(), 11,
         FG_DIM, weight=Pango.Weight.NORMAL, letter_spacing=0.6)
    return y + 22


def draw_cpu(cr, x, y, w, st):
    y = section(cr, x, y, w, "processor")
    tw, _ = text(cr, x, y, f"{st.cpu:.1f}", 22, FG, weight=Pango.Weight.LIGHT)
    text(cr, x + tw + 3, y + 11, "%", 10, FG_FAINT)
    load = os.getloadavg()
    text(cr, x + w, y + 6, f"load {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}",
         9.5, FG_FAINT, align="right")
    y += 30
    timeline(cr, x, y, w, 44, list(st.cpu_hist))
    y += 50

    n = len(st.cores) or 1
    gap = 3
    cw = (w - gap * (n - 1)) / n
    for i, core in enumerate(st.cores):
        bar(cr, x + i * (cw + gap), y, cw, 3, core / 100.0, radius=1.5)
    y += 8
    text(cr, x, y, f"{n} threads", 9, FG_FAINT)
    return y + 16


def draw_ram(cr, x, y, w, st):
    y = section(cr, x, y, w, "memory")
    tw, _ = text(cr, x, y, f"{st.ram:.1f}", 22, FG, weight=Pango.Weight.LIGHT)
    text(cr, x + tw + 3, y + 11, "%", 10, FG_FAINT)
    used = human_bytes(st.mem_used * 1024)
    total = human_bytes(st.mem_total * 1024)
    text(cr, x + w, y + 6, f"{used} / {total}", 9.5, FG_FAINT, align="right")
    y += 30
    timeline(cr, x, y, w, 34, list(st.ram_hist))
    return y + 46


def draw_temps(cr, x, y, w, st):
    y = section(cr, x, y, w, "temperature")
    for label, value, crit in st.temps:
        text(cr, x, y, label, 10, FG_DIM)
        text(cr, x + w, y, f"{value:.0f}°", 10, FG, align="right")
        bar(cr, x, y + 15, w, 3, value / max(crit, 1.0), radius=1.5)
        y += 25
    return y + 8


def draw_disks(cr, x, y, w, st):
    y = section(cr, x, y, w, "storage")
    for label, used, total in st.disks:
        text(cr, x, y, label, 10, FG_DIM)
        text(cr, x + w, y, f"{human_bytes(used)} / {human_bytes(total)}",
             9.5, FG_FAINT, align="right")
        bar(cr, x, y + 15, w, 3, used / total, radius=1.5)
        y += 25
    return y


# ── window ────────────────────────────────────────────────────────────
class Panel(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.stats = Stats()

        LayerShell.init_for_window(self)
        LayerShell.set_layer(self, LayerShell.Layer.BOTTOM)
        LayerShell.set_namespace(self, "desktop-stats")
        for edge, margin in ((LayerShell.Edge.RIGHT, MARGIN_RIGHT),
                             (LayerShell.Edge.TOP, MARGIN_TOP),
                             (LayerShell.Edge.BOTTOM, MARGIN_BOTTOM)):
            LayerShell.set_anchor(self, edge, True)
            LayerShell.set_margin(self, edge, margin)
        LayerShell.set_exclusive_zone(self, -1)   # never reserve screen space
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.NONE)

        self._content_h = 560    # measured on the previous frame; see draw()
        self.set_default_size(WIDTH, 400)
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(WIDTH, -1)
        self.area.set_draw_func(self.draw)
        self.set_child(self.area)

        css = Gtk.CssProvider()
        css.load_from_data(b"window { background: transparent; }")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.connect("realize", self._make_click_through)
        self._margin_top = MARGIN_TOP
        self._ticks = 0
        GLib.timeout_add(TICK_MS, self._tick)

    def _sync_top(self):
        # The panel usually starts before the bar has claimed its strip, so
        # the reservation read at startup can be 0. Re-read it and follow.
        top = hypr_reserved_top(default=self._margin_top - GAP) + GAP
        if top != self._margin_top:
            self._margin_top = top
            LayerShell.set_margin(self, LayerShell.Edge.TOP, top)

    def _make_click_through(self, *_):
        surface = self.get_surface()
        if surface is not None:
            surface.set_input_region(cairo.Region())

    def _tick(self):
        if self._ticks % 5 == 0:
            self._sync_top()
        self._ticks += 1
        self.stats.sample()
        self.area.queue_draw()
        return GLib.SOURCE_CONTINUE

    def draw(self, _area, cr, width, height):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_antialias(cairo.ANTIALIAS_BEST)

        x = PAD_LEFT
        w = width - PAD_LEFT - PAD_RIGHT

        # The content is shorter than the panel, so centre it in the gap
        # between bar and screen foot rather than letting it ride at the top.
        # Both this and the scrim use the height measured on the previous
        # frame; it only changes when a temp or disk row appears or goes, and
        # one stale frame is imperceptible.
        # Rounded to a whole pixel: text and hairlines drawn at a fractional y
        # get antialiased into a soft blur.
        top = float(round(max(0.0, (height - self._content_h) / 2.0)))

        if SCRIM_SOFT:
            scrim(cr, x - SCRIM_PAD, top - SCRIM_HEAD,
                  width - (x - SCRIM_PAD), self._content_h + SCRIM_HEAD + SCRIM_TAIL)
        else:
            # Fill the surface exactly. The surface is already the size and
            # position of a tiled window, so the backdrop matches one — and
            # landing on the surface bounds keeps all four edges pixel-crisp.
            scrim(cr, 0, 0, width, height)

        y = top
        y = draw_clock(cr, x, y, w) + 10
        y = draw_cpu(cr, x, y, w, self.stats)
        y = draw_ram(cr, x, y, w, self.stats)
        y = draw_temps(cr, x, y, w, self.stats)
        self._content_h = draw_disks(cr, x, y, w, self.stats) - top


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.local.desktop-stats")

    def do_activate(self):
        # Single-instance: a second launch just re-presents the existing panel
        # instead of stacking another layer surface on top of it.
        windows = self.get_windows()
        (windows[0] if windows else Panel(self)).present()


if __name__ == "__main__":
    App().run(None)
