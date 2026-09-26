import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Mpris

// Spectrum visualizer on the left of the wallpaper: one row of white squares
// per frequency band (bass at the top), growing to the right, with a thin
// peak-hold line past each row. cava does the audio analysis and prints raw
// levels; this file only draws them. Shown only while an MPRIS player plays.
Item {
  id: root

  property var shell: null

  // Geometry in logical px. At 1.25 scale these land on whole pixels:
  // 11 px squares with 4 px gaps, as in the mockup.
  readonly property real square: 8.8
  readonly property real gap: 3.2
  readonly property real step: square + gap
  readonly property real edge: 11.2        // left margin
  readonly property real pad: 12           // top/bottom margin inside the window
  readonly property int maxCells: 38       // longest row, in squares
  readonly property real peakWidth: 2.4

  readonly property int holdMs: 1500       // peak line stays put this long
  readonly property real fallCells: 15     // then falls this many squares/s
  readonly property int graceMs: 2000      // stay up this long after pausing
  readonly property int fadeMs: 400

  // Rows, set from the first screen's window height; cava gets the same count.
  property int rows: 0
  property var levels: []                  // current squares per row
  property var peaks: []                   // peak position per row (squares)
  property var holdUntil: []
  property real lastFrame: 0

  readonly property var players: Mpris.players ? Mpris.players.values : []
  readonly property bool playing: {
    for (var i = 0; i < players.length; i++)
      if (players[i] && players[i].isPlaying) return true
    return false
  }
  readonly property bool shown: playing || grace.running
  property real fade: shown ? 1 : 0
  Behavior on fade { NumberAnimation { duration: root.fadeMs; easing.type: Easing.InOutQuad } }

  onPlayingChanged: if (!playing) grace.restart(); else grace.stop()

  Timer { id: grace; interval: root.graceMs }

  function reset() {
    var z = []
    for (var i = 0; i < rows; i++) z.push(0)
    levels = z.slice(); peaks = z.slice(); holdUntil = z.slice()
    lastFrame = 0
  }
  onRowsChanged: reset()

  function frame(line) {
    var parts = line.split(";")
    var now = Date.now()
    var dt = lastFrame ? Math.min((now - lastFrame) / 1000, 0.1) : 0
    lastFrame = now
    var lv = [], pk = peaks.slice(), hu = holdUntil.slice()
    for (var i = 0; i < rows; i++) {
      var v = parseInt(parts[i]) || 0
      var cells = Math.round(Math.min(v, 1000) / 1000 * maxCells)
      lv.push(cells)
      var p = pk[i] || 0
      if (cells >= p) { p = cells; hu[i] = now + holdMs }
      else if (now > hu[i]) p = Math.max(cells, p - fallCells * dt)
      pk[i] = p
    }
    levels = lv; peaks = pk; holdUntil = hu
  }

  Process {
    id: cava
    running: root.rows > 0 && (root.shown || root.fade > 0)
    onRunningChanged: if (!running) root.reset()
    command: ["bash", "-c",
      'cfg="${XDG_RUNTIME_DIR:-/tmp}/sepro-visualizer.cava"\n' +
      'cat > "$cfg" <<EOF\n' +
      '[general]\nbars = ' + root.rows + '\nframerate = 60\nautosens = 1\n' +
      '[input]\nmethod = pipewire\nsource = auto\n' +
      '[output]\nmethod = raw\nraw_target = /dev/stdout\ndata_format = ascii\n' +
      'ascii_max_range = 1000\nbar_delimiter = 59\nframe_delimiter = 10\nchannels = mono\n' +
      '[smoothing]\nmonstercat = 1\nnoise_reduction = 77\n' +
      'EOF\n' +
      'exec cava -p "$cfg"']
    stdout: SplitParser { onRead: data => root.frame(data) }
  }

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: panel
      required property var modelData
      screen: modelData

      visible: root.fade > 0
      color: "transparent"
      anchors { top: true; bottom: true; left: true }
      implicitWidth: root.edge + (root.maxCells + 1) * root.step + root.peakWidth
      // Keep clear of the bar, but don't reserve any space of our own.
      exclusiveZone: 0
      mask: Region {}                      // click-through: the desktop keeps its clicks

      WlrLayershell.namespace: "sepro-visualizer"
      WlrLayershell.layer: WlrLayer.Bottom // above the wallpaper, below windows
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

      readonly property int fitRows: Math.max(0, Math.floor((height - 2 * root.pad + root.gap) / root.step))
      onFitRowsChanged: if (modelData === Quickshell.screens[0]) root.rows = fitRows
      Component.onCompleted: if (modelData === Quickshell.screens[0]) root.rows = fitRows

      Item {
        anchors.fill: parent
        opacity: root.fade

        Repeater {
          model: root.rows

          Item {
            required property int index
            x: root.edge
            y: root.pad + index * root.step
            width: parent.width - root.edge
            height: root.square

            // The row: a fixed strip of squares, clipped to the current level,
            // so each frame only changes one width.
            Item {
              width: Math.max(0, (root.levels[index] || 0) * root.step - root.gap)
              height: root.square
              clip: true
              opacity: 0.5

              Row {
                spacing: root.gap
                Repeater {
                  model: root.maxCells
                  Rectangle { width: root.square; height: root.square; color: "white" }
                }
              }
            }

            // Peak hold line, in the gap just past the square it marks.
            Rectangle {
              readonly property int cell: Math.ceil((root.peaks[index] || 0) - 0.001)
              visible: cell > 0
              x: cell * root.step - root.gap / 2 - root.peakWidth / 2
              width: root.peakWidth
              height: root.square
              color: "white"
              opacity: 0.75
            }
          }
        }
      }
    }
  }
}
