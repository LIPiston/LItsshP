import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import md3.Core

// One terminal pane: a GPU-friendly rasterised surface plus input handling.
// Keys and mouse go through the Python model so a single object owns screen
// state, selection and the PTY.
Item {
    id: root
    property int sessionIndex: 0
    property bool focused: false
    property var window

    signal requestReconnect()

    readonly property var session: App.tabs.length > sessionIndex ? App.tabs[sessionIndex] : null
    readonly property var model: App.terminalModel(sessionIndex)
    readonly property bool isClosed: session !== null
                                      && (session.state === "closed" || session.state === "failed")

    function takeFocus() { surface.forceActiveFocus() }

    Component.onCompleted: Qt.callLater(takeFocus)
    onFocusedChanged: if (focused) Qt.callLater(takeFocus)
    onModelChanged: Qt.callLater(syncViewport)

    function syncViewport() {
        if (!root.model) return
        root.model.setViewport(surface.width, surface.height, Screen.devicePixelRatio)
    }

    Item {
        id: surface
        anchors.fill: parent
        focus: true
        clip: true

        Image {
            id: display
            anchors.fill: parent
            source: root.model ? root.model.source : ""
            cache: false
            smooth: false
            // The provider hands back a raster at device resolution, so the
            // texture maps 1:1 onto the item's device pixels. Image.Pad would
            // draw it at its raw pixel size (1.5x too large at 150% scaling)
            // and clip the result.
            fillMode: Image.Stretch
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
            cursorShape: Qt.IBeamCursor

            property real pressX: 0
            property real pressY: 0

            onPressed: (e) => {
                surface.forceActiveFocus()
                if (!root.model) return
                pressX = e.x
                pressY = e.y
                root.model.mousePress(e.x, e.y, e.button, e.modifiers)
            }
            onPositionChanged: (e) => {
                if (root.model) root.model.mouseMove(e.x, e.y, e.buttons, e.modifiers)
            }
            onReleased: (e) => {
                if (root.model) root.model.mouseRelease(e.x, e.y, e.button, e.modifiers)
            }
            onDoubleClicked: (e) => {
                if (root.model) root.model.mouseDoubleClick(e.x, e.y)
            }
            onWheel: (e) => {
                if (root.model) root.model.wheel(e.x, e.y, e.angleDelta.y, e.modifiers)
            }
        }

        Keys.onPressed: (event) => {
            if (!root.model) return
            var page = Math.max(1, root.model.rows - 1)
            // Shift is the escape hatch for scrollback; a bare PgUp/PgDn has to
            // reach the application so vim, less and tmux keep paging.
            if (event.modifiers & Qt.ShiftModifier) {
                if (event.key === Qt.Key_PageUp) {
                    root.model.scrollLines(page); event.accepted = true; return
                }
                if (event.key === Qt.Key_PageDown) {
                    root.model.scrollLines(-page); event.accepted = true; return
                }
                if (event.key === Qt.Key_Up) {
                    root.model.scrollLines(1); event.accepted = true; return
                }
                if (event.key === Qt.Key_Down) {
                    root.model.scrollLines(-1); event.accepted = true; return
                }
            }
            if (event.key === Qt.Key_Home && (event.modifiers & Qt.ControlModifier)) {
                root.model.scrollLines(root.model.historySize); event.accepted = true; return
            }
            if (event.key === Qt.Key_End && (event.modifiers & Qt.ControlModifier)) {
                root.model.scrollToBottom(); event.accepted = true; return
            }
            if (root.model.handleKey(event.key, event.text, event.modifiers))
                event.accepted = true
        }

        onWidthChanged: root.syncViewport()
        onHeightChanged: root.syncViewport()
        Component.onCompleted: Qt.callLater(root.syncViewport)
    }

    // Overlay for terminated sessions; scrollback stays readable underneath.
    Rectangle {
        anchors.fill: parent
        visible: root.isClosed
        color: Qt.rgba(Theme.color.surface.r, Theme.color.surface.g,
                       Theme.color.surface.b, 0.68)

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 12

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.session && root.session.state === "failed" ? "error" : "power_settings_new"
                font.family: Theme.iconFont.name
                font.pixelSize: 34
                color: root.session && root.session.state === "failed"
                       ? Theme.color.error : Theme.color.onSurfaceVariantColor
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.session && root.session.state === "failed"
                      ? "tssh could not be started"
                      : "Session ended" + (root.session && root.session.exitStatus >= 0
                                           ? " · exit " + root.session.exitStatus : "")
                font.family: Theme.typography.titleMedium.family
                font.pixelSize: 15
                color: Theme.color.onSurfaceColor
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 8
                Button {
                    text: "Reconnect"
                    icon: "refresh"
                    onClicked: root.requestReconnect()
                }
                Button {
                    text: "Close tab"
                    type: "tonal"
                    onClicked: App.closeTab(root.sessionIndex)
                }
            }
        }
    }
}
