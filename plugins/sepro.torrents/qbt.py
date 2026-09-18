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
    qbt.py setup               apply the preferences below to the daemon
"""

import json
import os
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
        print(json.dumps({"running": False, "torrents": []}))
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
    elif cmd == "setup":
        cmd_setup()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
