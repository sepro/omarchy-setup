# Recently watched (VLC) — bar widget

An Omarchy shell plugin (`sepro.vlc-recent`) that puts a 󰕧 button in the bar.
It shows the last five videos you played in VLC, where you stopped in each, and
predicts the **next episode** of the series you were watching.

![Recently watched popup](img/vlc-recent-popup.png)

## Install

```sh
./install.sh vlc-recent
```

This copies the plugin to `~/.config/omarchy/plugins/sepro.vlc-recent/`, adds it
to the right side of the bar (`omarchy bar put sepro.vlc-recent`) and binds
**Super + M** to toggle the popup in `~/.config/hypr/bindings.lua`.

## Usage

| Action | Result |
|---|---|
| Left-click / Super + M | Toggle the popup |
| Right-click the button | Play the predicted next episode |
| Middle-click | Refresh |
| Click / Enter on an entry | Play it in VLC (resumes where you stopped) |
| Right-click / O on an entry | Open its folder |
| N | Play next episode |
| Esc | Close |

The list refreshes every 30 s.

## How it works

| File | Role |
|---|---|
| `manifest.json` | Registers the bar widget with the Omarchy shell |
| `Panel.qml` | The button and popup (Quickshell / QML) |
| `vlc-recent.py` | Reads VLC's history and prints JSON; `--next` plays the next episode |

- History comes from `[RecentsMRL]` in `~/.config/vlc/vlc-qt-interface.conf`,
  which VLC writes itself. The helper is read-only. Missing files and non-local
  URLs are skipped.
- Episodes are recognised by `S01E02` or `1x02` in the filename. The *next*
  episode is the file that follows in natural sort order in the same folder.
  The helper follows the most recent **episode**, so a film watched in between
  doesn't clear the suggestion. If that episode is the finale, nothing is
  suggested.
- VLC is launched with `QT_QPA_PLATFORMTHEME=qt5ct` so it picks up the
  [VLC theme](themes.md#vlc).

Check it from a terminal with `python ~/.config/omarchy/plugins/sepro.vlc-recent/vlc-recent.py`.

**VLC must remember history:** *Tools → Preferences → Interface → Save recently
played items* has to be on (the default).
