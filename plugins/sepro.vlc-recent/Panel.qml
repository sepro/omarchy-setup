import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Bar icon + popup listing what VLC was last playing, plus a guess at the next
// episode. History comes from vlc-recent.py, which reads VLC's own config.
//
//   left-click   open / close the popup
//   right-click  play the predicted next episode straight away
//   middle-click refresh
//
// In the popup: click / Enter plays in VLC, right-click / O opens the folder.
Panel {
  id: root
  moduleName: "sepro.vlc-recent"
  ipcTarget: "sepro.vlc-recent"

  readonly property string script: Qt.resolvedUrl("vlc-recent.py").toString().replace("file://", "")
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color accent: Color.accent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  property var recents: []
  property var upNext: null
  property int cursor: 0
  property bool cursorActive: false

  // The list rows and the UP NEXT row are one keyboard-navigable sequence.
  readonly property var entries: upNext ? recents.concat([upNext]) : recents

  function refresh() {
    if (!fetch.running) fetch.running = true
  }

  function hms(ms) {
    var total = Math.floor(ms / 1000)
    var h = Math.floor(total / 3600)
    var m = Math.floor((total % 3600) / 60)
    var s = total % 60
    var pad = function(n) { return (n < 10 ? "0" : "") + n }
    return h > 0 ? h + ":" + pad(m) + ":" + pad(s) : m + ":" + pad(s)
  }

  function play(entry) {
    if (!entry) return
    Quickshell.execDetached(["env", "QT_QPA_PLATFORMTHEME=qt5ct", "vlc", "--started-from-file", "--", entry.path])
    root.close()
  }

  function reveal(entry) {
    if (!entry) return
    Quickshell.execDetached(["nautilus", "--select", entry.path])
    root.close()
  }

  function playNext() {
    Quickshell.execDetached(["python", root.script, "--next"])
    root.close()
  }

  function moveCursor(dy) {
    if (entries.length === 0) return
    if (!cursorActive) { cursorActive = true; return }
    cursor = Math.max(0, Math.min(entries.length - 1, cursor + dy))
  }

  function setCursor(index) {
    cursorActive = true
    cursor = index
  }

  function cursorEntry() {
    return cursorActive && cursor < entries.length ? entries[cursor] : null
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onOpenedChanged: if (opened) {
    cursorActive = false
    cursor = 0
    refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  // Keep the list fresh while the popup is closed too, so opening it never
  // flashes stale entries.
  Timer {
    interval: 30000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Process {
    id: fetch
    command: ["python", root.script]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var data = JSON.parse(text)
          root.recents = data.items || []
          root.upNext = data.next || null
        } catch (e) {
          root.recents = []
          root.upNext = null
        }
        if (root.cursor >= root.entries.length) root.cursor = Math.max(0, root.entries.length - 1)
      }
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰕧"
    tooltipText: root.opened ? "" : "Recently watched"
    onPressed: function(b) {
      if (b === Qt.RightButton) root.playNext()
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
    contentWidth: panel.fittedContentWidth(Style.space(400))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(560))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) { if (dy !== 0) root.moveCursor(dy) }
      onActivateRequested: if (root.cursorActive) root.play(root.cursorEntry())
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "o" || t === "O") root.reveal(root.cursorEntry())
        else if (t === "n" || t === "N") root.playNext()
        else if (t === "r" || t === "R") root.refresh()
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

          PanelSectionHeader {
            text: "RECENTLY WATCHED"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Text {
            visible: root.recents.length === 0
            width: parent.width
            text: "Nothing watched recently."
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
            topPadding: Style.space(8)
            bottomPadding: Style.space(8)
          }

          Column {
            visible: root.recents.length > 0
            width: parent.width
            spacing: Style.space(6)

            Repeater {
              model: root.recents
              MediaRow {
                required property var modelData
                required property int index
                width: parent.width
                entry: modelData
                rowIndex: index
              }
            }
          }

          Column {
            visible: root.upNext !== null
            width: parent.width
            spacing: Style.space(10)

            PanelSeparator { foreground: root.foreground }

            PanelSectionHeader {
              text: "UP NEXT"
              foreground: root.accent
              fontFamily: root.fontFamily
            }

            MediaRow {
              width: parent.width
              entry: root.upNext
              rowIndex: root.recents.length
              next: true
            }
          }

          Text {
            visible: root.recents.length > 0
            width: parent.width
            text: "Enter play  ·  O open folder  ·  N play next  ·  Esc close"
            color: root.dim
            opacity: 0.7
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }
    }
  }

  component MediaRow: CursorSurface {
    id: row
    property var entry: null
    property int rowIndex: 0
    property bool next: false

    hasCursor: root.cursorActive && root.cursor === rowIndex
    foreground: root.foreground

    implicitHeight: rowContent.implicitHeight + Style.spacing.rowPaddingX

    MouseArea {
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      onEntered: root.setCursor(row.rowIndex)
      onClicked: function(mouse) {
        if (mouse.button === Qt.RightButton) root.reveal(row.entry)
        else root.play(row.entry)
      }
    }

    RowLayout {
      id: rowContent
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      anchors.leftMargin: Style.space(10)
      anchors.rightMargin: Style.space(10)
      spacing: Style.space(8)

      Text {
        visible: row.next
        text: "󰒭"
        color: root.accent
        font.family: root.fontFamily
        font.pixelSize: Style.font.icon
        Layout.alignment: Qt.AlignVCenter
      }

      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(1)

        RowLayout {
          Layout.fillWidth: true
          spacing: Style.space(8)

          Text {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            text: row.entry ? row.entry.title : ""
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            elide: Text.ElideRight
          }

          Text {
            visible: row.entry && row.entry.tag !== ""
            textFormat: Text.PlainText
            text: row.entry ? row.entry.tag : ""
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }

          Text {
            visible: row.entry && row.entry.resumeMs > 0
            textFormat: Text.PlainText
            text: row.entry ? "󰐎 " + root.hms(row.entry.resumeMs) : ""
            color: Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }
        }

        Text {
          visible: row.entry && row.entry.folder !== ""
          textFormat: Text.PlainText
          Layout.fillWidth: true
          text: row.entry ? row.entry.folder : ""
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }
}
