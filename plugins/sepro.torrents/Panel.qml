import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Bar icon + popup for qbittorrent-nox. State comes from qbt.py, which talks
// to the daemon's Web API.
//
//   left-click   open / close the popup
//   right-click  open the Web UI in the browser
//   middle-click stop everything (or resume if everything is stopped)
//
// In the popup: Enter / Space stops or resumes the row, O opens its folder,
// X removes it (files are kept), S / R stop / resume all, W opens the Web UI,
// C cleans the downloads with Claude, J syncs to Jellyfin. SUPER+D toggles it.
Panel {
  id: root
  moduleName: "sepro.torrents"
  ipcTarget: "sepro.torrents"

  readonly property string script: Qt.resolvedUrl("qbt.py").toString().replace("file://", "")
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color accent: Color.accent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  property var status: ({ running: false, torrents: [] })
  readonly property var torrents: status.torrents || []
  readonly property bool anyRunning: torrents.some(function(t) { return !t.done && t.group !== "stopped" && t.group !== "error" })
  readonly property var sync: status.sync || null
  // Clean and sync only make sense once every download has finished, and
  // never while the other one (or another run of itself) is going.
  readonly property string jobBlocker: !status.running ? "qBittorrent is not running"
    : status.unfinished > 0 ? "downloads still running"
    : status.clean ? "clean downloads is running"
    : sync ? "sync is running"
    : ""
  property int cursor: 0
  property bool cursorActive: false

  function refresh() {
    if (!fetch.running) fetch.running = true
  }

  function run(args) {
    Quickshell.execDetached(["python", root.script].concat(args))
    settle.restart()
  }

  function toggleTorrent(t) {
    if (!t || t.done) return
    run([t.group === "stopped" || t.group === "error" ? "start" : "stop", t.hash])
  }
  function removeTorrent(t) { if (t) run(["remove", t.hash]) }
  function openFolder(t) { run(["folder", t ? t.hash : ""]); root.close() }
  function openWebUi() { run(["webui"]); root.close() }
  function cleanDownloads() { if (!jobBlocker) run(["clean"]) }
  function syncJellyfin() { if (!jobBlocker) run(["sync"]) }
  function stopAll() { run(["stop", "all"]) }
  function startAll() { run(["start", "all"]) }

  function size(bytes) {
    var units = ["B", "KB", "MB", "GB", "TB"]
    var i = 0
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
    return (i === 0 ? bytes : bytes.toFixed(1)) + " " + units[i]
  }

  function eta(seconds) {
    if (seconds >= 8640000 || seconds < 0) return "∞"
    var h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60)
    if (h >= 24) return Math.floor(h / 24) + "d " + (h % 24) + "h"
    if (h > 0) return h + "h " + m + "m"
    return m > 0 ? m + "m" : seconds + "s"
  }

  function detail(t) {
    var pct = Math.floor(t.progress * 100) + "%"
    switch (t.group) {
      case "downloading": return pct + "  ·  ↓ " + size(t.dlspeed) + "/s  ·  " + eta(t.eta) + " left"
      case "stalled":     return pct + "  ·  stalled, looking for peers"
      case "queued":      return pct + "  ·  queued"
      case "stopped":     return pct + "  ·  stopped"
      case "seeding":     return "done  ·  seeding ↑ " + size(t.upspeed) + "/s"
      case "error":       return pct + "  ·  error (" + t.state + ")"
      default:            return "done  ·  " + size(t.size)
    }
  }

  function tooltip() {
    if (sync) return "Syncing to Jellyfin: " + Math.floor(sync.progress * 100) + "%"
    if (status.clean) return "Cleaning downloads…"
    if (!status.running) return "qBittorrent is not running"
    if (!status.active) return "Torrents: idle"
    var parts = []
    if (status.downloading > 0) parts.push(status.downloading + " downloading")
    parts.push(Math.floor((status.progress || 0) * 100) + "%")
    if (status.dlspeed > 0) parts.push("↓ " + size(status.dlspeed) + "/s")
    if (status.connection === "disconnected") parts.push("no connection (VPN down?)")
    return "Torrents: " + parts.join("  ·  ")
  }

  function moveCursor(dy) {
    if (torrents.length === 0) return
    if (!cursorActive) { cursorActive = true; return }
    cursor = Math.max(0, Math.min(torrents.length - 1, cursor + dy))
  }
  function setCursor(index) { cursorActive = true; cursor = index }
  function cursorTorrent() { return cursorActive && cursor < torrents.length ? torrents[cursor] : null }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onOpenedChanged: if (opened) {
    cursorActive = false
    cursor = 0
    refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  Timer {
    interval: root.opened ? 1500 : 4000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // Re-read shortly after an action so the popup reflects it.
  Timer {
    id: settle
    interval: 500
    onTriggered: root.refresh()
  }

  Process {
    id: fetch
    command: ["python", root.script, "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          root.status = JSON.parse(text)
        } catch (e) {
          root.status = { running: false, torrents: [] }
        }
        if (root.cursor >= root.torrents.length) root.cursor = Math.max(0, root.torrents.length - 1)
      }
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰇚"
    tooltipText: root.opened ? "" : root.tooltip()
    onPressed: function(b) {
      if (b === Qt.RightButton) root.openWebUi()
      else if (b === Qt.MiddleButton) root.anyRunning ? root.stopAll() : root.startAll()
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
    contentWidth: panel.fittedContentWidth(Style.space(440))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(560))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) { if (dy !== 0) root.moveCursor(dy) }
      onActivateRequested: root.toggleTorrent(root.cursorTorrent())
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        var k = t.toLowerCase()
        if (k === " ") root.toggleTorrent(root.cursorTorrent())
        else if (k === "o") root.openFolder(root.cursorTorrent())
        else if (k === "x") root.removeTorrent(root.cursorTorrent())
        else if (k === "s") root.stopAll()
        else if (k === "r") root.startAll()
        else if (k === "w") root.openWebUi()
        else if (k === "c") root.cleanDownloads()
        else if (k === "j") root.syncJellyfin()
      }

      Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: column
          width: flick.width
          spacing: Style.space(10)

          RowLayout {
            width: parent.width
            spacing: Style.space(4)

            PanelSectionHeader {
              Layout.fillWidth: true
              text: "TORRENTS"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            PanelActionButton {
              iconText: root.anyRunning ? "󰏤" : "󰐊"
              tooltipText: root.anyRunning ? "Stop all (S)" : "Resume all (R)"
              enabled: root.torrents.length > 0
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.anyRunning ? root.stopAll() : root.startAll()
            }
            PanelActionButton {
              iconText: "󰉋"
              tooltipText: "Open downloads folder"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.openFolder(null)
            }
            PanelActionButton {
              iconText: "󰃢"
              tooltipText: root.jobBlocker ? "Clean downloads: unavailable, " + root.jobBlocker
                : "Clean downloads (C): sort into movies/series with Claude"
              enabled: !root.jobBlocker
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.cleanDownloads()
            }
            PanelActionButton {
              iconText: "󰑓"
              tooltipText: root.jobBlocker ? "Sync to Jellyfin: unavailable, " + root.jobBlocker
                : "Sync to Jellyfin (J)"
              enabled: !root.jobBlocker
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.syncJellyfin()
            }
            PanelActionButton {
              iconText: "󰖟"
              tooltipText: "Open Web UI (W)"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.openWebUi()
            }
          }

          Text {
            visible: !root.status.running || root.status.connection === "disconnected"
            width: parent.width
            wrapMode: Text.WordWrap
            text: !root.status.running
              ? "qBittorrent is not running.  systemctl --user start qbittorrent-nox"
              : "No connection. Torrents only use the Surfshark VPN; is it connected?"
            color: Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          Text {
            visible: root.status.clean === true
            width: parent.width
            text: "󰃢  Claude is cleaning downloads…"
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          Column {
            visible: root.sync !== null
            width: parent.width
            spacing: Style.space(3)

            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: !root.sync ? ""
                : root.sync.phase === "scanning" ? "󰑓  Jellyfin sync: checking what's new…"
                : "󰑓  Jellyfin sync: file " + Math.min(root.sync.files + 1, root.sync.total_files) + " of " + root.sync.total_files
                  + "  ·  " + Math.floor(root.sync.progress * 100) + "%" + (root.sync.speed ? "  ·  " + root.sync.speed : "")
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
            }
            Rectangle {
              width: parent.width
              height: Style.space(4)
              radius: height / 2
              color: Qt.darker(root.foreground, 3.5)
              Rectangle {
                width: parent.width * (root.sync ? root.sync.progress : 0)
                height: parent.height
                radius: parent.radius
                color: root.accent
              }
            }
            Text {
              visible: root.sync && root.sync.file !== ""
              width: parent.width
              textFormat: Text.PlainText
              text: root.sync ? root.sync.file : ""
              color: root.dim
              elide: Text.ElideMiddle
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
          }

          Text {
            visible: root.status.running && root.torrents.length === 0
            width: parent.width
            text: "No torrents."
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
            topPadding: Style.space(8)
            bottomPadding: Style.space(8)
          }

          Column {
            visible: root.torrents.length > 0
            width: parent.width
            spacing: Style.space(6)

            Repeater {
              model: root.torrents
              TorrentRow {
                required property var modelData
                required property int index
                width: parent.width
                torrent: modelData
                rowIndex: index
              }
            }
          }

          Text {
            visible: root.status.running
            width: parent.width
            text: "↓ " + root.size(root.status.dlspeed || 0) + "/s   ↑ " + root.size(root.status.upspeed || 0) + "/s"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }

          Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: (root.torrents.length > 0 ? "Enter stop/resume  ·  O folder  ·  X remove  ·  S/R all  ·  " : "")
              + "W Web UI  ·  C clean  ·  J sync"
            color: root.dim
            opacity: 0.7
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }
    }
  }

  component TorrentRow: CursorSurface {
    id: row
    property var torrent: null
    property int rowIndex: 0
    readonly property bool paused: torrent && (torrent.group === "stopped" || torrent.group === "error")

    hasCursor: root.cursorActive && root.cursor === rowIndex
    foreground: root.foreground
    implicitHeight: rowContent.implicitHeight + Style.spacing.rowPaddingX

    MouseArea {
      anchors.fill: parent
      hoverEnabled: true
      onEntered: root.setCursor(row.rowIndex)
    }

    RowLayout {
      id: rowContent
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      anchors.leftMargin: Style.space(10)
      anchors.rightMargin: Style.space(6)
      spacing: Style.space(6)

      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(3)

        Text {
          textFormat: Text.PlainText
          Layout.fillWidth: true
          text: row.torrent ? row.torrent.name : ""
          color: row.torrent && row.torrent.done ? root.dim : root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          elide: Text.ElideMiddle
        }

        Rectangle {
          visible: row.torrent && !row.torrent.done
          Layout.fillWidth: true
          implicitHeight: Style.space(4)
          radius: height / 2
          color: Qt.darker(root.foreground, 3.5)

          Rectangle {
            width: parent.width * (row.torrent ? row.torrent.progress : 0)
            height: parent.height
            radius: parent.radius
            color: row.torrent && row.torrent.group === "error" ? Color.urgent
              : (row.paused ? root.dim : root.accent)
          }
        }

        Text {
          textFormat: Text.PlainText
          Layout.fillWidth: true
          text: row.torrent ? root.detail(row.torrent) : ""
          color: row.torrent && row.torrent.group === "error" ? Color.urgent : root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }

      PanelActionButton {
        visible: row.torrent && !row.torrent.done
        iconText: row.paused ? "󰐊" : "󰏤"
        tooltipText: row.paused ? "Resume" : "Stop"
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.toggleTorrent(row.torrent)
      }
      PanelActionButton {
        iconText: "󰉋"
        tooltipText: "Open folder"
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.openFolder(row.torrent)
      }
      PanelActionButton {
        iconText: "󰆴"
        tooltipText: "Remove (keeps files)"
        foreground: root.foreground
        hoverColor: Color.urgent
        fontFamily: root.fontFamily
        onClicked: root.removeTorrent(row.torrent)
      }
    }
  }
}
