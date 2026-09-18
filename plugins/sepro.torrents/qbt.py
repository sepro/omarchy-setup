#!/usr/bin/env python3
"""
qBittorrent helper for the sepro.torrents bar widget and the magnet handler.

Talks to qbittorrent-nox's Web API on 127.0.0.1:8080. The daemon skips the
login for localhost (WebUI\\LocalHostAuth=false), so no password is needed.

    qbt.py status              print the JSON the widget reads
    qbt.py add <magnet|file>…  add torrents (starts the daemon if needed)
    qbt.py stop  <hash|all>    stop (pause) torrents
    qbt.py start <hash|all>    resume torrents
    qbt.py remove <hash>       remove a torrent, keeping its files
    qbt.py folder [hash]       open the torrent's folder (or the downloads dir)
    qbt.py webui               open the web interface in the browser
    qbt.py clean               sort finished downloads with Claude, in the background
    qbt.py sync                copy movies/series to Jellyfin, in the background
    qbt.py setup               apply the preferences below to the daemon
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

API = "http://127.0.0.1:8080"
SERVICE = "qbittorrent-nox.service"
DOWNLOADS = "/data/downloads"
VPN_INTERFACE = "surfshark_wg"
CACHE = os.path.expanduser("~/.cache/sepro-torrents")
CLEAN_LOG = os.path.join(CACHE, "clean.log")
CLEAN_LOCK = os.path.join(CACHE, "clean.lock")
SYNC_LOG = os.path.join(CACHE, "sync.log")
SYNC_STATE = os.path.join(CACHE, "sync.json")
SYNC_SCRIPT = os.path.expanduser("~/.local/bin/sync-jellyfin.sh")
MOVIES = "/data/movies"
SERIES = "/data/series"

# The rules live in /data/downloads/CLAUDE.md, which Claude loads from its
# working directory. Nobody is around to answer, so the two points where those
# rules say to ask are settled here instead.
CLEAN_PROMPT = """Organize the downloads following the instructions in CLAUDE.md.
You are running unattended in the background: nobody can answer questions.
- If a destination file already exists, do not overwrite it: leave that item in
  /data/downloads and list both paths in the summary.
- Do not start ~/.local/bin/sync-jellyfin.sh; just end with the summary.
Keep the summary short and plain text: it is shown as a desktop notification."""

# Applied by `setup`. Keys are qBittorrent's Web API preference names.
PREFERENCES = {
    "save_path": DOWNLOADS,
    "temp_path_enabled": False,
    "add_stopped_enabled": False,
    # Only use the VPN: if it drops, torrents stall instead of leaking.
    "current_network_interface": VPN_INTERFACE,
    "current_interface_address": "",
    # No seeding: stop as soon as a download completes (ratio 0 -> Stop).
    "max_ratio_enabled": True,
    "max_ratio": 0,
    "max_ratio_act": 0,
}

# Torrent states grouped for the widget (qBittorrent 5 names).
DOWNLOADING = {"downloading", "forcedDL", "metaDL", "forcedMetaDL", "allocating"}
STALLED = {"stalledDL"}
QUEUED = {"queuedDL", "queuedUP", "checkingDL", "checkingUP", "checkingResumeData", "moving"}
SEEDING = {"uploading", "forcedUP", "stalledUP"}
STOPPED = {"stoppedDL", "stoppedUP"}
ERROR = {"error", "missingFiles", "unknown"}


# ── Web API ───────────────────────────────────────────────────────────

def call(path, data=None, files=None, timeout=3):
    """GET (data None) or POST to /api/v2/<path>; returns the body as text."""
    url = f"{API}/api/v2/{path}"
    headers = {"Referer": API}
    body = None
    if files:
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in (data or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for filename, content in files:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="torrents"; filename="{filename}"\r\n'
                f"Content-Type: application/x-bittorrent\r\n\r\n".encode() + content + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def up():
    try:
        call("app/version", timeout=1)
        return True
    except (urllib.error.URLError, OSError):
        return False


def ensure_up():
    """Start the daemon if it isn't answering, and wait for it."""
    if up():
        return True
    subprocess.run(["systemctl", "--user", "start", SERVICE], check=False)
    for _ in range(40):
        time.sleep(0.25)
        if up():
            return True
    return False


def notify(title, body="", urgent=False):
    cmd = ["notify-send", "-a", "qBittorrent", "-i", "folder-download", title, body]
    if urgent:
        cmd[1:1] = ["-u", "critical"]
    subprocess.run(cmd, check=False)


# ── commands ──────────────────────────────────────────────────────────

def cmd_status():
    try:
        torrents = json.loads(call("torrents/info"))
        transfer = json.loads(call("transfer/info"))
    except (urllib.error.URLError, OSError, ValueError):
        print(json.dumps({"running": False, "torrents": [], **_jobs()}))
        return

    out = []
    for t in torrents:
        state = t.get("state", "unknown")
        done = t.get("progress", 0) >= 1
        if state in ERROR:
            group = "error"
        elif state in STOPPED:
            group = "done" if done else "stopped"
        elif state in DOWNLOADING:
            group = "downloading"
        elif state in STALLED:
            group = "stalled"
        elif state in SEEDING:
            group = "seeding"
        elif state in QUEUED:
            group = "queued"
        else:
            group = "queued"
        out.append({
            "hash": t["hash"],
            "name": t.get("name", ""),
            "progress": t.get("progress", 0),
            "size": t.get("size", 0),
            "dlspeed": t.get("dlspeed", 0),
            "upspeed": t.get("upspeed", 0),
            "eta": t.get("eta", 8640000),
            "state": state,
            "group": group,
            "done": done,
            "added": t.get("added_on", 0),
        })

    # Unfinished first (newest first), then finished ones.
    out.sort(key=lambda t: (t["done"], -t["added"]))
    active = [t for t in out if not t["done"] or t["group"] == "seeding"]
    remaining = sum(t["size"] * (1 - t["progress"]) for t in out if not t["done"])
    total = sum(t["size"] for t in out if not t["done"])
    print(json.dumps({
        "running": True,
        "torrents": out,
        "active": len(active),
        "downloading": sum(1 for t in out if t["group"] == "downloading"),
        "progress": (1 - remaining / total) if total else 1,
        "dlspeed": transfer.get("dl_info_speed", 0),
        "upspeed": transfer.get("up_info_speed", 0),
        "connection": transfer.get("connection_status", ""),
        "unfinished": sum(1 for t in out if not t["done"]),
        **_jobs(),
    }))


def _magnet_name(link):
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    return qs.get("dn", ["magnet link"])[0]


def cmd_add(items):
    if not items:
        sys.exit("usage: qbt.py add <magnet|file>…")
    if not ensure_up():
        notify("Torrent not added", "qBittorrent isn't running and couldn't be started.", urgent=True)
        sys.exit(1)

    links, files, names = [], [], []
    for item in items:
        if item.startswith("file://"):
            item = urllib.parse.unquote(item[len("file://"):])
        if item.startswith(("magnet:", "http://", "https://")):
            links.append(item)
            names.append(_magnet_name(item) if item.startswith("magnet:") else os.path.basename(item))
        elif os.path.isfile(item):
            with open(item, "rb") as fh:
                files.append((os.path.basename(item), fh.read()))
            names.append(os.path.basename(item))
        else:
            notify("Torrent not added", f"Not a magnet link or .torrent file:\n{item}", urgent=True)

    try:
        if links:
            call("torrents/add", {"urls": "\n".join(links), "savepath": DOWNLOADS})
        if files:
            call("torrents/add", {"savepath": DOWNLOADS}, files=files, timeout=10)
    except (urllib.error.URLError, OSError) as e:
        notify("Torrent not added", str(e), urgent=True)
        sys.exit(1)
    if names:
        notify("Downloading", "\n".join(names))


def cmd_hashes(action, target):
    if not target:
        sys.exit(f"usage: qbt.py {action} <hash|all>")
    call(f"torrents/{action}", {"hashes": target})


def cmd_remove(target):
    if not target or target == "all":
        sys.exit("usage: qbt.py remove <hash>")
    call("torrents/delete", {"hashes": target, "deleteFiles": "false"})


def cmd_folder(target):
    path = DOWNLOADS
    if target:
        info = json.loads(call("torrents/info?" + urllib.parse.urlencode({"hashes": target})))
        if info:
            path = info[0].get("content_path") or info[0].get("save_path") or DOWNLOADS
    if os.path.isdir(path):
        subprocess.Popen(["nautilus", path])
    elif os.path.exists(path):
        subprocess.Popen(["nautilus", "--select", path])
    else:
        # Not written to disk yet: open where it will land.
        subprocess.Popen(["nautilus", os.path.dirname(path) if target else DOWNLOADS])


def cmd_webui():
    ensure_up()
    subprocess.Popen(["xdg-open", API])


# ── clean / sync jobs ─────────────────────────────────────────────────
# Both run detached from the bar (their own session), so closing the popup or
# restarting the shell doesn't kill them. Each job leaves a file holding its
# pid; a pid that no longer exists means the job died and the file is stale.

def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def _clean_running():
    try:
        with open(CLEAN_LOCK) as f:
            return _alive(f.read().strip())
    except OSError:
        return False


def _sync_state():
    try:
        with open(SYNC_STATE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return None
    return state if _alive(state.get("pid")) else None


def _jobs():
    return {"clean": _clean_running(), "sync": _sync_state()}


def _unfinished():
    """Torrents still downloading (or stopped halfway): None if the daemon is down."""
    try:
        return sum(1 for t in json.loads(call("torrents/info")) if t.get("progress", 0) < 1)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _spawn(job):
    subprocess.Popen([sys.executable, os.path.abspath(__file__), job],
                     start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _refuse_busy(title):
    """Clean and sync both need the downloads settled and each other finished."""
    if _clean_running():
        notify(title, "Clean downloads is still running")
    elif _sync_state():
        notify(title, "The Jellyfin sync is still running")
    elif _unfinished():
        notify(title, "Wait until the downloads have finished")
    else:
        return False
    return True


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def cmd_clean():
    if not _refuse_busy("Clean downloads"):
        _spawn("clean-run")


def cmd_clean_run():
    os.makedirs(CACHE, exist_ok=True)
    with open(CLEAN_LOCK, "w") as f:
        f.write(str(os.getpid()))
    notify("Clean downloads", "Claude is sorting /data/downloads…")
    try:
        with open(CLEAN_LOG, "w") as log:
            result = subprocess.run(
                ["claude", "-p", CLEAN_PROMPT, "--model", "sonnet",
                 "--effort", "medium", "--permission-mode", "auto"],
                cwd=DOWNLOADS, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=log, text=True)
            log.write(result.stdout)
        summary = result.stdout.strip() or "(no output)"
        if len(summary) > 1500:
            summary = summary[:1500] + "…"
        notify("Downloads cleaned" if result.returncode == 0 else "Clean downloads failed",
               summary + "\n\nFull log: " + CLEAN_LOG, urgent=result.returncode != 0)
    finally:
        os.remove(CLEAN_LOCK)


def _sync_line(base, line):
    """Follow `sync-jellyfin.sh -v` output one line at a time.

    The script prints a header before each rsync call, and rsync's paths are
    relative to that call's source directory. Returns the (possibly new) source
    directory and the source file the line names, or None.
    """
    line = line.strip()
    if line.startswith("== Movies:"):
        return MOVIES, None
    if line.startswith("-- ") and " / Season " in line:
        return os.path.join(SERIES, line[3:].rsplit(" / Season ", 1)[0]), None
    if base and line and not line.endswith("/"):
        path = os.path.join(base, line)
        if os.path.isfile(path):
            return base, path
    return base, None


PROGRESS = re.compile(r"^\s*[\d.,]+[KMGT]?\s+(\d+)%\s+(\S+/s)")


def cmd_sync():
    if not _refuse_busy("Sync to Jellyfin"):
        _spawn("sync-run")


def cmd_sync_run():
    os.makedirs(CACHE, exist_ok=True)
    state = {"pid": os.getpid(), "phase": "scanning", "file": "", "progress": 0,
             "speed": "", "files": 0, "total_files": 0}
    _write_json(SYNC_STATE, state)
    try:
        # A dry run first to learn what will be copied, so progress can be
        # given over the whole sync rather than one file at a time.
        dry = subprocess.run([SYNC_SCRIPT, "-n", "-v"], capture_output=True, text=True)
        if dry.returncode != 0:
            notify("Jellyfin sync failed", (dry.stderr.strip() or dry.stdout.strip())[-1500:], urgent=True)
            return
        sizes, base = {}, None
        for line in dry.stdout.splitlines():
            base, path = _sync_line(base, line)
            if path:
                sizes[path] = os.path.getsize(path)
        total = sum(sizes.values()) or 1
        if not sizes:
            notify("Jellyfin is up to date", "Nothing new to copy")
            return
        state.update(phase="copying", total_files=len(sizes))
        _write_json(SYNC_STATE, state)

        with open(SYNC_LOG, "w") as log:
            proc = subprocess.Popen([SYNC_SCRIPT, "-v"], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            done_bytes, current, lines, last, base, buf = 0, None, [], 0, None, ""
            while True:
                chunk = proc.stdout.read(1)
                if not chunk:
                    break
                if chunk not in "\r\n":
                    buf += chunk
                    continue
                line, buf = buf, ""
                if chunk == "\n":
                    log.write(line + "\n")
                    lines.append(line)
                m = PROGRESS.match(line)
                if m and current:
                    pct = int(m.group(1)) / 100
                    state.update(progress=(done_bytes + pct * sizes[current]) / total, speed=m.group(2))
                else:
                    base, path = _sync_line(base, line)
                    if path in sizes:
                        if current:
                            done_bytes += sizes[current]
                            state["files"] += 1
                        current = path
                        state.update(file=os.path.basename(path), progress=done_bytes / total)
                now = time.monotonic()
                if now - last > 0.5:
                    _write_json(SYNC_STATE, state)
                    last = now
            proc.wait()

        warnings = [l for l in lines if l.startswith(("WARN", "ERROR"))]
        summary = next((l.strip() for l in reversed(lines) if l.startswith("== Done")), "")
        body = f"{len(sizes)} file(s) copied.\n{summary}"
        if warnings:
            body += "\n" + "\n".join(warnings[:10])
        notify("Jellyfin sync finished" if proc.returncode == 0 else "Jellyfin sync failed",
               body + "\n\nFull log: " + SYNC_LOG, urgent=proc.returncode != 0 or bool(warnings))
    finally:
        try:
            os.remove(SYNC_STATE)
        except OSError:
            pass


def cmd_setup():
    if not ensure_up():
        sys.exit("qbittorrent-nox isn't answering on " + API)
    call("app/setPreferences", {"json": json.dumps(PREFERENCES)})
    prefs = json.loads(call("app/preferences"))
    for key, want in PREFERENCES.items():
        print(f"  {key} = {prefs.get(key)!r}" + ("" if prefs.get(key) == want else f"  (wanted {want!r})"))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    arg = args[1] if len(args) > 1 else ""
    if cmd == "status":
        cmd_status()
    elif cmd == "add":
        cmd_add(args[1:])
    elif cmd in ("stop", "start"):
        cmd_hashes(cmd, arg)
    elif cmd == "remove":
        cmd_remove(arg)
    elif cmd == "folder":
        cmd_folder(arg)
    elif cmd == "webui":
        cmd_webui()
    elif cmd == "clean":
        cmd_clean()
    elif cmd == "clean-run":
        cmd_clean_run()
    elif cmd == "sync":
        cmd_sync()
    elif cmd == "sync-run":
        cmd_sync_run()
    elif cmd == "setup":
        cmd_setup()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
