# Rain radar: bar widget next to the weather

A 󰐷 button next to the weather icon opens a looping rain radar map centred on
Herent. It shows the last two hours in 10-minute frames. Radar frames come
from [RainViewer](https://www.rainviewer.com) and the basemap is Esri's dark
grey canvas, tinted towards the theme background. The home marker, the
current frame and the timeline use the theme accent colour.

Below the map, **Next 2 hours** is Buienradar's rain forecast for Herent in
5-minute steps, as bars in the accent colour, with a one-line summary such as
"Dry until 21:45" or "Rain from 20:10".

![Rain radar popup](img/radar.jpg)

[Omastorm](https://github.com/wesleygrimes/omastorm) was the first choice, but
it only shows NEXRAD, the US radar network, so it has no data for Belgium.

## Install

```sh
./install.sh radar
```

This copies the plugin to `~/.config/omarchy/plugins/sepro.radar`, puts the
widget after `omarchy.weather` in the bar, and binds SUPER + SHIFT + R.

## Usage

| Action | Result |
|---|---|
| Left-click the button, SUPER + SHIFT + R | Toggle the popup |
| Right-click the button | Open the KMI radar page in the browser |
| Middle-click the button | Refresh the frames |
| Space, click the map | Play / pause |
| ← / → | Step one frame (pauses) |
| Click a timeline tick | Jump to that frame |
| Slow / Medium / Fast, `[` / `]` | Animation speed |
| `+` / `-`, scroll wheel | Zoom (Belgium, Benelux, western Europe) |
| R | Refresh |
| W | Open the KMI radar page |

The newest frame is held a little longer before the loop restarts, and its
time is shown in the accent colour.

## Notes

- To change the location, edit `place`, `lat` and `lon` at the top of
  `plugins/sepro.radar/Panel.qml`.
- The forecast is for Herent only, not a forecast map. RainViewer stopped
  publishing forecast frames, and Buienradar's forecast maps come with their
  own basemap and colours, so they can't follow the theme.
- RainViewer serves radar only up to zoom 7, so the closest zoom is a little
  soft.
- The shell doesn't always pick up edits to the plugin; if a change doesn't
  show, run `omarchy restart shell`.
