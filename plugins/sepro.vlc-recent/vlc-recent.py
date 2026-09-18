#!/usr/bin/env python3
"""
Recently-watched helper for the sepro.vlc-recent bar widget.

Reads VLC's own history ([RecentsMRL] in ~/.config/vlc/vlc-qt-interface.conf)
and prints it as JSON for the widget, together with a predicted next episode
of whatever was watched most recently.

    vlc-recent.py            print the JSON the widget reads
    vlc-recent.py --next     play the predicted next episode (or resume the
                             most recent file if there is no next episode)

Nothing writes the history but VLC, so this is read-only and can't corrupt it.
"""

import json
import os
import re
import subprocess
import sys
import urllib.parse

VLC_CONF = os.path.expanduser("~/.config/vlc/vlc-qt-interface.conf")
MAX_ITEMS = 5
VIDEO_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".webm", ".wmv",
             ".mpg", ".mpeg", ".flv", ".ts", ".m2ts", ".ogv"}

# SxxEyy and 1x02 episode numbering.
_PATTERNS = [
    re.compile(r"[sS](\d{1,2})[\s._-]*[eE](\d{1,3})"),
    re.compile(r"(?<![\dxX])(\d{1,2})[xX](\d{2,3})(?!\d)"),
]


# ── VLC history ───────────────────────────────────────────────────────

def _unurl(mrl):
    """file:///a%20b.mkv -> /a b.mkv; anything non-local -> None."""
    mrl = mrl.strip()
    if not mrl.startswith("file://"):
        return None
    return urllib.parse.unquote(mrl[len("file://"):])


def read_recents():
    """The recents list, newest first, stale entries dropped.

    Returns [(path, resume_ms)]. VLC keeps `list` and `times` as parallel
    comma-separated arrays; entries whose file is gone are skipped, and paths
    are canonicalised so one file reached through a symlink is one entry.
    """
    if not os.path.exists(VLC_CONF):
        return []

    section, raw_list, raw_times = None, "", ""
    with open(VLC_CONF, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
            elif section == "RecentsMRL" and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() == "list":
                    raw_list = val
                elif key.strip() == "times":
                    raw_times = val

    # A fresh VLC writes "@Invalid()" for an empty list.
    if not raw_list or raw_list.startswith("@"):
        return []

    mrls = [m for m in (s.strip() for s in raw_list.split(",")) if m]
    times = [t.strip() for t in raw_times.split(",")] if raw_times else []

    out, seen = [], set()
    for i, mrl in enumerate(mrls):
        path = _unurl(mrl)
        if not path or not os.path.isfile(path):
            continue
        path = os.path.realpath(path)
        if path in seen:
            continue
        seen.add(path)
        try:
            resume = int(times[i]) if i < len(times) else 0
        except ValueError:
            resume = 0
        out.append((path, resume))
    return out


# ── episode parsing / prediction ──────────────────────────────────────

def episode_of(name):
    """(season, episode) from a filename, or None."""
    for pat in _PATTERNS:
        m = pat.search(name)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def series_of(name):
    """The show name: everything before the episode tag, cleaned up."""
    stem = os.path.splitext(name)[0]
    for pat in _PATTERNS:
        m = pat.search(stem)
        if m:
            stem = stem[:m.start()]
            break
    return re.sub(r"[\s._-]+", " ", stem).strip(" -") or os.path.splitext(name)[0]


def _natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def predict_next(path):
    """The next episode after `path`, in the same folder.

    Lowest (season, episode) strictly greater than the current one among files
    of the same series, so gaps and season rollovers need no special-casing.
    Folders without episode numbering fall back to natural sort order.
    """
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        return None

    current = os.path.basename(path)
    siblings = [f for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in VIDEO_EXT
                and os.path.isfile(os.path.join(folder, f))]

    here = episode_of(current)
    if here:
        show = series_of(current).lower()
        best, best_key = None, None
        for f in siblings:
            if f == current or series_of(f).lower() != show:
                continue
            key = episode_of(f)
            if key and key > here and (best_key is None or key < best_key):
                best, best_key = f, key
        return os.path.join(folder, best) if best else None

    ordered = sorted(siblings, key=_natural)
    if current in ordered:
        i = ordered.index(current)
        if i + 1 < len(ordered):
            return os.path.join(folder, ordered[i + 1])
    return None


def upcoming(recents):
    """The next episode to suggest, given the whole history.

    Follows the most recent entry that *is* an episode, so a film watched in
    between two episodes doesn't blank the suggestion. If that episode has no
    successor (a finale) there is no suggestion.
    """
    for path, _resume in recents:
        if episode_of(os.path.basename(path)):
            return predict_next(path)
    return None


# ── output ────────────────────────────────────────────────────────────

def describe(path, resume=0):
    name = os.path.basename(path)
    title = series_of(name)
    ep = episode_of(name)
    folder = os.path.basename(os.path.dirname(path))
    return {
        "path": path,
        "title": title,
        "tag": "S%02dE%02d" % ep if ep else "",
        "resumeMs": resume,
        # The folder is usually just the show name again; only surface it when
        # it says something the title doesn't (films, loose files).
        "folder": folder if folder and folder.lower() != title.lower() else "",
    }


def dump():
    recents = read_recents()
    nxt = upcoming(recents)
    print(json.dumps({
        "items": [describe(p, r) for p, r in recents[:MAX_ITEMS]],
        "next": describe(nxt) if nxt else None,
    }))


def play_next():
    recents = read_recents()
    if not recents:
        return
    target = upcoming(recents) or recents[0][0]
    # Same environment as ~/.local/share/applications/vlc.desktop: qt5ct is
    # what gives VLC the Omarchy theme (the session default is gtk3).
    env = dict(os.environ, QT_QPA_PLATFORMTHEME="qt5ct")
    subprocess.Popen(["vlc", "--started-from-file", "--", target], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--next":
        play_next()
    else:
        dump()
