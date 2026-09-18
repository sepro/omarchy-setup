# Torrents: qbittorrent-nox with a bar widget

qBittorrent runs headless as a user service. Magnet links and `.torrent` files
download straight to `/data/downloads` with no dialog. A 󰇚 button in the bar
opens a popup that shows progress and lets you stop, resume and remove torrents.

## Install

```sh
./install.sh torrents
```

This does five things:
- installs `qbittorrent-nox`
- enables `~/.config/systemd/user/qbittorrent-nox.service`, which starts at login
- seeds `~/.config/qBittorrent/qBittorrent.conf` on the first install only
- registers `qbt-magnet.desktop` for `magnet:` links and `.torrent` files
- adds the `sepro.torrents` widget to the bar

## Usage

| Action | Result |
|---|---|
| Click a magnet link / open a `.torrent` | Starts downloading; a notification shows the name |
| Left-click the button | Toggle the popup |
| SUPER + D | Toggle the popup from the keyboard |
| Right-click the button | Open the Web UI (http://127.0.0.1:8080) in the browser |
| Middle-click the button | Stop all (or resume all if everything is stopped) |
| 󰏤 / 󰐊 on a row, Enter | Stop / resume that torrent |
| 󰉋 on a row, O | Open its folder |
| 󰆴 on a row, X | Remove it from qBittorrent; **files are kept** |
| Header 󰏤/󰐊, S / R | Stop / resume all |
| Header 󰉋 | Open `/data/downloads` |
| Header 󰖟, W | Open the Web UI |
| Header 󰃢, C | Clean downloads: runs Claude (Sonnet, medium effort, auto mode) in the background on the rules in `/data/downloads/CLAUDE.md`; the summary arrives as a notification, the full log is in `~/.cache/sepro-torrents/clean.log` |
| Header 󰑓, J | Sync to Jellyfin: runs `sync-jellyfin.sh` in the background with a progress bar in the popup; log in `~/.cache/sepro-torrents/sync.log` |

Clean and sync are disabled while any torrent is unfinished, and while either of them is already running.

The Web UI is the full qBittorrent interface: priorities, files, trackers, settings.

## Settings

`qbt.py setup` (run by the installer) applies these through the Web API:

| Setting | Value |
|---|---|
| Save path | `/data/downloads` |
| Network interface | `surfshark_wg`. Torrents **only** use the Surfshark VPN, so if it drops they stall instead of leaking; the popup warns "No connection". |
| Seeding | none: a torrent stops as soon as it completes (ratio limit 0 → Stop) |

To change them, edit `PREFERENCES` at the top of
`~/.config/omarchy/plugins/sepro.torrents/qbt.py` and rerun it with `setup`, or
use the Web UI.

**Web UI login:** the UI listens on 127.0.0.1 only, and localhost doesn't need a
password (`WebUI\LocalHostAuth=false`). The trade-off is that any program
running as any user on this machine can control qBittorrent.

## How it works

| File | Role |
|---|---|
| `plugins/sepro.torrents/Panel.qml` | Bar button and popup; polls every 4 s (1.5 s while open) |
| `plugins/sepro.torrents/qbt.py` | Web API client: `status`, `add`, `stop`, `start`, `remove`, `folder`, `webui`, `clean`, `sync`, `setup` |
| `torrents/qbittorrent-nox.service` | User service (`--confirm-legal-notice`) |
| `torrents/qBittorrent.conf` | First-run config: Web UI on 127.0.0.1:8080, no localhost login |
| `torrents/qbt-magnet.desktop` | Magnet / `.torrent` handler → `qbt.py add` |

`qbt.py add` starts the service if it isn't running. Finished torrents stay in
the list (dimmed) until you remove them.

Check from a terminal:

```sh
systemctl --user status qbittorrent-nox
python3 ~/.config/omarchy/plugins/sepro.torrents/qbt.py status | jq
```
