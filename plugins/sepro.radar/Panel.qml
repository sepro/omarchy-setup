import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Ui

// Bar icon + popup with a looping rain radar map around home. Radar frames
// come from RainViewer (10-minute steps, last two hours), drawn over Esri's
// dark grey canvas, which is tinted towards the theme background. Below it,
// Buienradar's two-hour rain forecast for home.
//
//   left-click   open / close the popup
//   right-click  open the KMI radar page in the browser
//   middle-click refresh
//
// In the popup: Space plays / pauses, ←/→ step frames, [/] change speed,
// +/- zoom, R refreshes, W opens the KMI radar page.
Panel {
  id: root
  moduleName: "sepro.radar"
  ipcTarget: "sepro.radar"

  // Home: Herent, Belgium
  readonly property string place: "Herent"
  readonly property real lat: 50.9086
  readonly property real lon: 4.6711
  readonly property string esri: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/"
  readonly property string webUrl: "https://www.meteo.be/nl/weer/verwachtingen/radar"

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color accent: Color.accent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // Basemap zoom. RainViewer serves radar up to zoom 7, so radar is fetched as
  // 512px tiles one zoom level lower, which line up with the basemap exactly.
  property int zoom: 8
  readonly property int minZoom: 6
  readonly property int maxZoom: 8

  property string host: ""
  property var frames: []          // [{time, path}], oldest first
  property int frame: 0
  property bool playing: true
  property real speed: 1
  readonly property var speeds: [0.5, 1, 2]
  readonly property var speedNames: ["Slow", "Medium", "Fast"]
  property string error: ""
  property var forecast: []       // [{time: "HH:mm", mm: mm/h}], next two hours
  property double now: Date.now()

  readonly property int viewSize: mapRect.width
  readonly property real cx: worldX(lon, zoom)
  readonly property real cy: worldY(lat, zoom)
  readonly property real viewLeft: cx - viewSize / 2
  readonly property real viewTop: cy - viewSize / 2

  function worldX(lo, z) { return (lo + 180) / 360 * 256 * Math.pow(2, z) }
  function worldY(la, z) {
    var r = la * Math.PI / 180
    return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * 256 * Math.pow(2, z)
  }

  // Tile indices [x, y] of size `size` covering the view.
  function tilesFor(size) {
    var out = []
    var x0 = Math.floor(viewLeft / size), x1 = Math.floor((viewLeft + viewSize - 1) / size)
    var y0 = Math.floor(viewTop / size), y1 = Math.floor((viewTop + viewSize - 1) / size)
    for (var y = y0; y <= y1; y++)
      for (var x = x0; x <= x1; x++) out.push([x, y])
    return out
  }

  function refresh() {
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      try {
        if (xhr.status !== 200) throw "HTTP " + xhr.status
        var data = JSON.parse(xhr.responseText)
        var past = data.radar.past || []
        if (past.length === 0) throw "no frames"
        var atEnd = root.frame >= root.frames.length - 1
        root.host = data.host
        root.frames = past
        if (atEnd || root.frame >= past.length) root.frame = past.length - 1
        root.error = ""
      } catch (e) {
        root.error = "Radar unavailable (" + e + ")"
      }
    }
    xhr.open("GET", "https://api.rainviewer.com/public/weather-maps.json")
    xhr.send()
    refreshForecast()
  }

  // Buienradar's point forecast: "value|HH:mm" per 5 minutes for two hours,
  // where value 0-255 maps to mm/h as 10^((value - 109) / 32).
  function refreshForecast() {
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      if (xhr.status !== 200) { root.forecast = []; return }
      var out = []
      xhr.responseText.trim().split("\n").forEach(function(line) {
        var parts = line.trim().split("|")
        if (parts.length !== 2) return
        var v = parseInt(parts[0], 10)
        out.push({ time: parts[1], mm: v > 0 ? Math.pow(10, (v - 109) / 32) : 0 })
      })
      root.forecast = out
    }
    xhr.open("GET", "https://gpsgadget.buienradar.nl/data/raintext?lat=" + lat.toFixed(2) + "&lon=" + lon.toFixed(2))
    xhr.send()
  }

  // One line on what the next two hours hold.
  function forecastSummary() {
    if (forecast.length === 0) return "No forecast"
    var wet = function(f) { return f.mm >= 0.1 }
    var first = forecast.findIndex(wet)
    var last = forecast[forecast.length - 1].time
    if (first < 0) return "Dry until " + last
    if (first === 0) {
      var stop = forecast.findIndex(function(f) { return !wet(f) })
      return stop < 0 ? "Rain until at least " + last : "Rain until " + forecast[stop].time
    }
    return "Rain from " + forecast[first].time
  }

  function step(d) {
    if (frames.length === 0) return
    playing = false
    frame = (frame + d + frames.length) % frames.length
  }

  function changeSpeed(d) {
    var i = Math.max(0, Math.min(speeds.length - 1, speeds.indexOf(speed) + d))
    speed = speeds[i]
  }

  function setZoom(z) { zoom = Math.max(minZoom, Math.min(maxZoom, z)) }

  function openWeb() {
    Qt.openUrlExternally(root.webUrl)
    root.close()
  }

  function clock(t) {
    var d = new Date(t * 1000)
    var pad = function(n) { return (n < 10 ? "0" : "") + n }
    return pad(d.getHours()) + ":" + pad(d.getMinutes())
  }

  function age(t) {
    var m = Math.max(0, Math.round((now - t * 1000) / 60000))
    return m < 1 ? "now" : m < 60 ? m + " min ago" : Math.floor(m / 60) + " h " + (m % 60) + " min ago"
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onOpenedChanged: if (opened) {
    now = Date.now()
    playing = true
    if (frames.length) frame = frames.length - 1
    refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  // RainViewer publishes a frame every 10 minutes.
  Timer {
    interval: 5 * 60000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: { root.now = Date.now(); root.refresh() }
  }

  // Loop through the frames, holding a little longer on the newest one.
  Timer {
    running: root.opened && root.playing && root.frames.length > 1
    repeat: true
    interval: (root.frame === root.frames.length - 1 ? 1500 : 450) / root.speed
    onTriggered: root.frame = (root.frame + 1) % root.frames.length
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰐷"
    tooltipText: root.opened ? "" : "Rain radar"
    onPressed: function(b) {
      if (b === Qt.RightButton) Qt.openUrlExternally(root.webUrl)
      else if (b === Qt.MiddleButton) root.refresh()
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(440)
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) { if (dx !== 0) root.step(dx) }
      onActivateRequested: root.playing = !root.playing
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "+" || t === "=") root.setZoom(root.zoom + 1)
        else if (t === "-" || t === "_") root.setZoom(root.zoom - 1)
        else if (t === "r" || t === "R") root.refresh()
        else if (t === "w" || t === "W") root.openWeb()
        else if (t === "[") root.changeSpeed(-1)
        else if (t === "]") root.changeSpeed(1)
      }

      Column {
        id: column
        width: parent.width
        spacing: Style.space(10)

        RowLayout {
          width: parent.width
          spacing: Style.space(8)

          PanelSectionHeader {
            Layout.fillWidth: true
            text: "RAIN RADAR · " + root.place.toUpperCase()
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Text {
            visible: root.frames.length > 0
            text: root.frames.length ? root.clock(root.frames[root.frame].time) : ""
            color: root.frame === root.frames.length - 1 ? root.accent : root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            font.bold: true
          }
        }

        // The map
        Rectangle {
          id: mapRect
          width: parent.width
          height: width
          color: Color.background
          border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
          border.width: 1
          clip: true

          Item {
            id: world
            x: -root.viewLeft
            y: -root.viewTop

            Repeater {
              model: root.tilesFor(256)
              Image {
                required property var modelData
                x: modelData[0] * 256
                y: modelData[1] * 256
                width: 256
                height: 256
                asynchronous: true
                source: root.esri + "World_Dark_Gray_Base/MapServer/tile/" + root.zoom + "/" + modelData[1] + "/" + modelData[0]
              }
            }
          }

          // Pull the basemap towards the theme background.
          Rectangle {
            anchors.fill: parent
            color: Color.background
            opacity: 0.35
          }

          // One layer per frame, all loaded up front so playback never waits.
          Item {
            x: -root.viewLeft
            y: -root.viewTop

            Repeater {
              model: root.frames.length
              Item {
                id: frameLayer
                required property int index
                readonly property string framePath: root.frames[index] ? root.frames[index].path : ""
                visible: index === root.frame

                Repeater {
                  model: root.tilesFor(512)
                  Image {
                    required property var modelData
                    x: modelData[0] * 512
                    y: modelData[1] * 512
                    width: 512
                    height: 512
                    asynchronous: true
                    opacity: 0.8
                    source: frameLayer.framePath === "" ? "" : root.host + frameLayer.framePath + "/512/" + (root.zoom - 1) + "/"
                            + modelData[0] + "/" + modelData[1] + "/2/1_1.png"
                  }
                }
              }
            }
          }

          Item {
            x: -root.viewLeft
            y: -root.viewTop

            Repeater {
              model: root.tilesFor(256)
              Image {
                required property var modelData
                x: modelData[0] * 256
                y: modelData[1] * 256
                width: 256
                height: 256
                asynchronous: true
                opacity: 0.8
                source: root.esri + "World_Dark_Gray_Reference/MapServer/tile/" + root.zoom + "/" + modelData[1] + "/" + modelData[0]
              }
            }
          }

          // Home marker
          Rectangle {
            width: Style.space(12)
            height: width
            radius: width / 2
            x: (root.viewSize - width) / 2
            y: (root.viewSize - height) / 2
            color: "transparent"
            border.color: root.accent
            border.width: 2
            Rectangle {
              anchors.centerIn: parent
              width: 4
              height: 4
              radius: 2
              color: root.accent
            }
          }

          Text {
            visible: root.error !== ""
            anchors.centerIn: parent
            text: root.error
            color: Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }

          Text {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Style.space(4)
            text: "RainViewer · Esri"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }

          MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            onClicked: root.playing = !root.playing
            onWheel: function(wheel) { root.setZoom(root.zoom + (wheel.angleDelta.y > 0 ? 1 : -1)) }
          }
        }

        // Timeline: one tick per frame, the current one in the accent colour.
        RowLayout {
          width: parent.width
          spacing: Style.space(8)

          Text {
            text: root.playing ? "󰏤" : "󰐊"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.icon
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.playing = !root.playing
            }
          }

          Row {
            Layout.fillWidth: true
            spacing: 2
            Repeater {
              model: root.frames.length
              Rectangle {
                required property int index
                width: (parent.width - 2 * (root.frames.length - 1)) / Math.max(1, root.frames.length)
                height: Style.space(6)
                radius: 1
                color: index === root.frame ? root.accent : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.2)
                MouseArea {
                  anchors.fill: parent
                  anchors.topMargin: -6
                  anchors.bottomMargin: -6
                  cursorShape: Qt.PointingHandCursor
                  onClicked: { root.playing = false; root.frame = parent.index }
                }
              }
            }
          }

          // Fixed width (the widest label it can show), so the timeline
          // doesn't resize every frame as the text changes.
          Text {
            text: root.frames.length ? root.age(root.frames[root.frame].time) : "loading…"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            horizontalAlignment: Text.AlignRight
            Layout.preferredWidth: ageMetrics.advanceWidth

            TextMetrics {
              id: ageMetrics
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              text: "0 h 00 min ago"
            }
          }
        }

        // Rain forecast for home, next two hours
        PanelSeparator { foreground: root.foreground }

        RowLayout {
          width: parent.width
          spacing: Style.space(8)

          PanelSectionHeader {
            Layout.fillWidth: true
            text: "NEXT 2 HOURS"
            foreground: root.accent
            fontFamily: root.fontFamily
          }

          Text {
            text: root.forecastSummary()
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }
        }

        Item {
          width: parent.width
          height: Style.space(48)

          // Baseline
          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.2)
          }

          Row {
            anchors.fill: parent
            spacing: 2

            Repeater {
              model: root.forecast
              Item {
                required property var modelData
                width: (parent.width - 2 * (root.forecast.length - 1)) / Math.max(1, root.forecast.length)
                height: parent.height

                // Height on a log-ish scale: drizzle is visible, 10 mm/h fills it.
                Rectangle {
                  anchors.bottom: parent.bottom
                  width: parent.width
                  radius: 1
                  height: modelData.mm < 0.1 ? 0
                        : Math.max(3, parent.height * Math.min(1, Math.log(1 + modelData.mm) / Math.log(11)))
                  color: root.accent
                  opacity: 0.85
                }
              }
            }
          }
        }

        Item {
          width: parent.width
          height: startLabel.implicitHeight
          visible: root.forecast.length > 0

          Text {
            id: startLabel
            text: root.forecast.length ? root.forecast[0].time : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.forecast.length ? root.forecast[Math.floor(root.forecast.length / 2)].time : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
          Text {
            anchors.right: parent.right
            text: root.forecast.length ? root.forecast[root.forecast.length - 1].time + " · Buienradar" : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }

        // Playback speed
        Row {
          spacing: Style.space(6)

          Text {
            text: "SPEED"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            anchors.verticalCenter: parent.verticalCenter
          }

          Repeater {
            model: root.speeds
            Rectangle {
              required property real modelData
              readonly property bool active: root.speed === modelData
              width: label.implicitWidth + Style.space(12)
              height: label.implicitHeight + Style.space(4)
              radius: 3
              color: active ? root.accent : "transparent"
              border.width: 1
              border.color: active ? root.accent : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.25)

              Text {
                id: label
                anchors.centerIn: parent
                text: root.speedNames[root.speeds.indexOf(modelData)]
                color: parent.active ? Color.background : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: parent.active
              }

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.speed = parent.modelData; root.playing = true }
              }
            }
          }
        }

      }
    }
  }
}
