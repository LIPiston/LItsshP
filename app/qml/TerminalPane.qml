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

    property bool searchVisible: false
    property bool searchCaseSensitive: false

    function openSearch() {
        if (!root.model) return
        root.searchVisible = true
        Qt.callLater(function () {
            searchField.forceActiveFocus()
            searchField.selectAll()
        })
    }

    function closeSearch() {
        root.searchVisible = false
        if (root.model) root.model.clearSearch()
        takeFocus()
    }

    // Window-level shortcuts (Ctrl+Shift+C/V) resolve through these; keeping
    // them on the pane means the shortcut does not need to know where the
    // terminal model lives.
    function copySelection() {
        if (!root.model) return
        if (!root.model.copySelectionIfAny())
            App.toast("Select some text first")
    }
    function pasteClipboard() { if (root.model) root.model.pasteClipboard() }
    function selectAll() { if (root.model) root.model.selectAll() }
    function hasSelection() { return root.model !== null && root.model.hasSelection }

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
                // Right click opens our menu unless the app is tracking the
                // mouse; then the press was forwarded above and a popup would
                // fight vim's own context menu. Shift always forces ours.
                if (e.button === Qt.RightButton) {
                    var appOwnsMouse = root.model.mouseReporting
                                       && !(e.modifiers & Qt.ShiftModifier)
                    if (!appOwnsMouse) paneMenu.open(surface, e.x, e.y)
                }
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
            var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
            var shift = (event.modifiers & Qt.ShiftModifier) !== 0
            // Ctrl+Shift+C / Ctrl+Shift+V are the terminal copy/paste bindings
            // (Ctrl+C alone must stay SIGINT, Ctrl+V stays literal input).
            // They are handled here as well as in the window shortcut so the
            // key never reaches handleKey(), which would send a control byte.
            if (ctrl && shift) {
                if (event.key === Qt.Key_C) {
                    root.copySelection(); event.accepted = true; return
                }
                if (event.key === Qt.Key_V) {
                    root.pasteClipboard(); event.accepted = true; return
                }
                if (event.key === Qt.Key_A) {
                    root.selectAll(); event.accepted = true; return
                }
            }
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
            if (event.key === Qt.Key_F && event.modifiers & Qt.ControlModifier) {
                root.openSearch(); event.accepted = true; return
            }
            if (event.key === Qt.Key_Escape && root.searchVisible) {
                root.closeSearch(); event.accepted = true; return
            }
            if (root.model.handleKey(event.key, event.text, event.modifiers))
                event.accepted = true
        }

        onWidthChanged: root.syncViewport()
        onHeightChanged: root.syncViewport()
        Component.onCompleted: Qt.callLater(root.syncViewport)
    }

    // Full terminal selection semantics need the model, so "Select all" is a
    // model call rather than a QML loop over rows.
    Menu {
        id: paneMenu
        model: [
            { text: "Copy", icon: "content_copy",
              enabled: root.model !== null && root.model.hasSelection,
              action: function() {
                  if (root.model && !root.model.copySelectionIfAny())
                      App.toast("Nothing is selected")
              } },
            { text: "Paste", icon: "content_paste",
              action: function() { if (root.model) root.model.pasteClipboard() } },
            { type: "separator" },
            { text: "Select all", icon: "select_all",
              action: function() { if (root.model) root.model.selectAll() } },
            { text: "Clear selection", icon: "deselect",
              enabled: root.model !== null && root.model.hasSelection,
              action: function() { if (root.model) root.model.clearSelection() } }
        ]
    }

    // ── Scrollback search ──────────────────────────────────────────────
    // Ctrl+F opens this strip over the top of the pane. The model owns the
    // hits and their row coordinates; the strip only drives it, so matches
    // found before new output arrived stay valid.
    Rectangle {
        id: searchBar
        visible: root.searchVisible
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 10
        width: Math.min(420, parent.width - 20)
        height: 40
        radius: 8
        color: Theme.color.surfaceContainerHigh
        border.width: 1
        border.color: Theme.color.outlineVariant
        z: 20

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 6
            spacing: 6

            Text {
                text: "search"
                font.family: Theme.iconFont.name
                font.pixelSize: 16
                color: Theme.color.onSurfaceVariantColor
            }

            TextInput {
                id: searchField
                Layout.fillWidth: true
                verticalAlignment: TextInput.AlignVCenter
                font.family: Theme.typography.bodyMedium.family
                font.pixelSize: 13
                color: Theme.color.onSurfaceColor
                selectionColor: Theme.color.primary
                selectedTextColor: Theme.color.onPrimaryColor
                clip: true
                onTextChanged: if (root.model)
                                   root.model.setSearch(text, root.searchCaseSensitive)
                Keys.onDownPressed: if (root.model) root.model.nextMatch(1)
                Keys.onUpPressed: if (root.model) root.model.nextMatch(-1)
                Keys.onPressed: function(event) {
                    if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) return
                    if (root.model) root.model.nextMatch(
                        (event.modifiers & Qt.ShiftModifier) ? -1 : 1)
                    event.accepted = true
                }
                Keys.onEscapePressed: root.closeSearch()

                Text {
                    anchors.fill: parent
                    verticalAlignment: Text.AlignVCenter
                    visible: !parent.text
                    text: "Find in scrollback"
                    font: parent.font
                    color: Theme.color.onSurfaceVariantColor
                    opacity: 0.6
                }
            }

            Text {
                visible: searchField.text.length > 0
                text: root.model && root.model.searchCount > 0
                      ? root.model.searchCurrent + " / " + root.model.searchCount
                      : "0"
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 10
                color: root.model && root.model.searchCount > 0
                       ? Theme.color.onSurfaceVariantColor : Theme.color.error
            }

            // Match case. Toggling re-runs the query through the same setSearch
            // call the field uses, so the hit list and the highlight agree.
            Rectangle {
                Layout.preferredWidth: 34
                Layout.preferredHeight: 24
                radius: 4
                color: root.searchCaseSensitive
                       ? Theme.color.secondaryContainer
                       : (caseHover.containsMouse ? Theme.color.surfaceContainerHighest
                                                  : "transparent")
                Text {
                    anchors.centerIn: parent
                    text: "Aa"
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    color: root.searchCaseSensitive
                           ? Theme.color.onSecondaryContainerColor
                           : Theme.color.onSurfaceVariantColor
                }
                MouseArea {
                    id: caseHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.searchCaseSensitive = !root.searchCaseSensitive
                        if (root.model)
                            root.model.setSearch(searchField.text,
                                                 root.searchCaseSensitive)
                    }
                }
            }

            Item {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                Text {
                    anchors.centerIn: parent
                    text: "keyboard_arrow_up"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: prevHover.containsMouse ? Theme.color.onSurfaceColor
                                                   : Theme.color.onSurfaceVariantColor
                }
                MouseArea {
                    id: prevHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (root.model) root.model.nextMatch(-1)
                }
            }
            Item {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                Text {
                    anchors.centerIn: parent
                    text: "keyboard_arrow_down"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: nextHover.containsMouse ? Theme.color.onSurfaceColor
                                                   : Theme.color.onSurfaceVariantColor
                }
                MouseArea {
                    id: nextHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (root.model) root.model.nextMatch(1)
                }
            }
            Item {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                Text {
                    anchors.centerIn: parent
                    text: "close"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 15
                    color: closeSearchHover.containsMouse ? Theme.color.onSurfaceColor
                                                          : Theme.color.onSurfaceVariantColor
                }
                MouseArea {
                    id: closeSearchHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.closeSearch()
                }
            }
        }
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
