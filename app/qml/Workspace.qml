import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core

// Right side: flat tab strip + terminal stack + empty state + status bar.
// This item lives inside the workspace card, so it must not paint its own
// background: the card's surface shows through, and only hairlines divide the
// regions. Pebrel's tab state is a pill fill (accent wash when active), never
// an underline — an underline would add a second selection voice.
Item {
    id: root
    property var window

    readonly property var skin: Theme.skin
    readonly property color hairline: skin.hairline
    readonly property color hoverColor: skin.hover

    // The pane QML-side shortcuts act on: Ctrl+Shift+C/V and the composer.
    // This is a function rather than a bound property on purpose: a Repeater
    // fills itemAt() only after its delegates are created, and a property
    // binding that resolved to null in that window would stay null forever,
    // because nothing in the dependency graph changes when the delegate
    // appears.
    function activeTerminal() {
        if (paneRepeater.count === 0) return null
        var idx = App.activeIndex
        if (idx < 0 || idx >= paneRepeater.count) return null
        return paneRepeater.itemAt(idx)
    }

    readonly property bool composerVisible: App.hasTabs
                                             && App.settings.composerVisible !== false

    // Kept here rather than inside the terminal pane so the strip survives
    // tab switches: a queued command belongs to the window, not the session,
    // and the last thing typed should still be there when you come back.
    property string draft: ""

    function focusComposer() {
        if (composerVisible) composer.focusInput()
        else root.window.openSettings()
    }

    function openSearch() {
        var pane = root.activeTerminal()
        if (pane) pane.openSearch()
    }

    // ── Empty state ────────────────────────────────────────────────────
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(420, Math.max(280, parent.width - 80))
        spacing: 10
        visible: !App.hasTabs

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 48
            Layout.preferredHeight: 48
            radius: root.skin.radiusControl + 2
            color: root.skin.accentSoft
            Text {
                anchors.centerIn: parent
                text: "terminal"
                font.family: Theme.iconFont.name
                font.pixelSize: 24
                color: root.skin.accent
            }
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 4
            text: App.hosts.length === 0 ? "No hosts yet" : "Pick a host to connect"
            font.family: Theme.typography.titleMedium.family
            font.pixelSize: 16
            font.weight: Font.Medium
            color: root.skin.ink
        }

        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignHCenter
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: App.hosts.length === 0
                  ? "Hosts are read from ~/.ssh/config — the same file tssh uses. Add one to get started."
                  : "Sessions open as tabs. Everything runs through tssh, so stored passwords, jump hosts and trzsz file transfer keep working."
            font.family: Theme.typography.bodySmall.family
            font.pixelSize: 12
            color: root.skin.inkDim
            opacity: 0.9
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            spacing: 8

            Button {
                text: App.hosts.length === 0 ? "Add your first host" : "Browse hosts"
                icon: "add"
                onClicked: {
                    if (App.hosts.length === 0) root.window.openHostEditor("")
                    else root.window.focusSearch()
                }
            }
            Button {
                text: "Quick connect"
                icon: "keyboard_command_key"
                type: "tonal"
                visible: App.hosts.length > 0
                onClicked: root.window.openPalette()
            }
            // Restoring is explicit: opening several SSH connections on start
            // is not something a GUI should do unasked.
            Button {
                text: "Reopen last session"
                icon: "history"
                type: "text"
                visible: App.canRestore
                onClicked: {
                    var res = App.restoreLayout()
                    if (!res.ok) App.toast(res.error || "Nothing to restore")
                }
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 14
            spacing: 14

            Repeater {
                model: ["Ctrl+N  new host", "Ctrl+T  search", "Ctrl+,  settings"]
                Text {
                    required property string modelData
                    text: modelData
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 10
                    color: root.skin.inkFaint
                }
            }
        }
    }

    // ── Tab strip ──────────────────────────────────────────────────────
    // No fill and no bottom border: the strip is part of the card surface, and
    // the active tab is a pill (accent wash). An underline on top of that
    // would be a second selection cue, which Pebrel avoids.
    Rectangle {
        id: tabBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: App.hasTabs ? 38 : 0
        visible: App.hasTabs
        color: "transparent"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            spacing: 2

            ListView {
                id: tabList
                Layout.fillWidth: true
                Layout.fillHeight: true
                orientation: ListView.Horizontal
                model: App.tabs
                currentIndex: App.activeIndex
                clip: true
                spacing: 2
                boundsBehavior: Flickable.StopAtBounds
                onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)

                delegate: Item {
                    id: tabItem
                    required property var modelData
                    required property int index
                    property bool isActive: index === App.activeIndex

                    width: Math.min(220, 104 + String(modelData.host).length * 5)
                    height: tabList.height

                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: 5
                        anchors.bottomMargin: 5
                        radius: root.skin.radiusControl
                        color: tabItem.isActive
                               ? root.skin.accentSoft
                               : (tabMouse.containsMouse ? root.hoverColor : "transparent")

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 9
                            anchors.rightMargin: 3
                            spacing: 6

                            Rectangle {
                                Layout.preferredWidth: 6
                                Layout.preferredHeight: 6
                                radius: 3
                                color: {
                                    if (modelData.state === "connected") return root.skin.accent
                                    if (modelData.state === "failed") return root.skin.danger
                                    if (modelData.state === "closed") return root.skin.inkFaint
                                    return root.skin.warn
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.host
                                elide: Text.ElideRight
                                font.family: Theme.typography.labelLarge.family
                                font.pixelSize: 11
                                font.weight: tabItem.isActive ? Font.Medium : Font.Normal
                                color: tabItem.isActive ? root.skin.inkStrong : root.skin.inkDim
                            }

                            Item {
                                Layout.preferredWidth: 18
                                Layout.preferredHeight: 18

                                Rectangle {
                                    anchors.fill: parent
                                    radius: root.skin.radiusChip
                                    color: closeMouse.containsMouse ? root.hoverColor : "transparent"
                                }
                                Text {
                                    anchors.centerIn: parent
                                    text: "close"
                                    font.family: Theme.iconFont.name
                                    font.pixelSize: 12
                                    color: closeMouse.containsMouse ? root.skin.iconHover : root.skin.icon
                                }
                                MouseArea {
                                    id: closeMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.window.requestCloseTab(tabItem.index)
                                }
                            }
                        }
                    }

                    MouseArea {
                        id: tabMouse
                        anchors.fill: parent
                        anchors.rightMargin: 22
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: (mouse) => {
                            if (mouse.button === Qt.MiddleButton) root.window.requestCloseTab(tabItem.index)
                            else if (mouse.button === Qt.RightButton) tabMenu.open(tabItem, 0, tabItem.height)
                            else App.setActiveIndex(tabItem.index)
                        }
                    }
                }
            }

            HeaderIconButton {
                icon: App.settings.sidebarVisible !== false ? "left_panel_close" : "left_panel_open"
                tooltip: "Toggle sidebar (Ctrl+B)"
                onActivated: App.setSetting("sidebarVisible", !(App.settings.sidebarVisible !== false))
            }
            TransferIndicator {
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredWidth: implicitWidth
                Layout.preferredHeight: implicitHeight
                onClicked: transferPopover.toggle()
            }
            // Port forwarding. The icon tints when a forward is live; the
            // panel explains whether each is provided by a session or by its
            // own process.
            Item {
                id: tunnelButton
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28

                Rectangle {
                    anchors.fill: parent
                    radius: root.skin.radiusControl
                    color: tunnelMouse.containsMouse ? root.hoverColor : "transparent"
                }
                Text {
                    anchors.centerIn: parent
                    text: "swap_horiz"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 17
                    color: App.tunnelActive ? root.skin.accent : root.skin.icon
                }
                MouseArea {
                    id: tunnelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.window.openTunnels()
                }
                ToolTip {
                    visible: tunnelMouse.containsMouse
                    text: App.tunnelCount > 0
                          ? "Port forwarding · " + App.tunnelCount + " active (Ctrl+Shift+T)"
                          : "Port forwarding (Ctrl+Shift+T)"
                    timeout: 8000
                }
            }
            HeaderIconButton {
                icon: App.settings.composerVisible !== false ? "keyboard_hide" : "keyboard"
                tooltip: (App.settings.composerVisible !== false ? "Hide" : "Show") + " command composer"
                onActivated: App.setSetting("composerVisible", !(App.settings.composerVisible !== false))
            }
            // Opens the transfer list. `swap_vert` reads as "moving things
            // between two places", which is what the panel is for.
            Item {
                id: transferButton
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28

                Rectangle {
                    anchors.fill: parent
                    radius: root.skin.radiusControl
                    color: (transferMouse.containsMouse || transferPopover.opened)
                           ? root.hoverColor : "transparent"
                }
                Text {
                    anchors.centerIn: parent
                    text: "swap_vert"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 17
                    color: (App.transferActive || transferPopover.opened)
                           ? root.skin.accent : root.skin.icon
                }
                // No count badge here: a dot anchored to the icon's top-right
                // sits on top of the glyph and reads as a close control. The
                // icon tint carries the state instead, and the count lives in
                // the tooltip and in the panel.
                MouseArea {
                    id: transferMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: transferPopover.toggle()
                }
                ToolTip {
                    visible: transferMouse.containsMouse && !transferPopover.opened
                    text: App.transferCount > 0
                          ? "Transfers · " + App.transferCount + " running"
                          : "Transfers"
                    timeout: 8000
                }
            }
        }
    }

    // Sits above everything in the workspace so it can dim the pane below.
    TransferPopover {
        id: transferPopover
        anchors.fill: parent
        anchors.topMargin: tabBar.height
        window: root.window
        onTransferRequested: (alias) => root.window.openTransfer(alias)
    }

    // ── Terminal stack ─────────────────────────────────────────────────
    // With a split, two panes share the area side by side. Both are ordinary
    // TerminalPane instances; the split only changes which are visible.
    Item {
        id: terminalArea
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: tabBar.bottom
        anchors.bottom: composer.visible ? composer.top : statusBar.top
        clip: true

        readonly property bool split: App.splitActive
        readonly property int splitAt: App.splitIndex

        Repeater {
            id: paneRepeater
            model: App.tabs

            delegate: TerminalPane {
                required property var modelData
                required property int index
                visible: index === App.activeIndex
                         || (terminalArea.split && index === terminalArea.splitAt)
                // The split bar sits above both panes, so they start below it
                // when it is visible.
                y: terminalArea.split ? splitBar.height : 0
                // The active pane leads; the split takes the right half.
                x: !terminalArea.split ? 0
                   : (index === App.activeIndex ? 0 : terminalArea.width / 2 + 1)
                width: !terminalArea.split ? terminalArea.width
                     : Math.max(120, terminalArea.width / 2 - 1)
                height: terminalArea.height - y
                sessionIndex: index
                focused: index === App.activeIndex && root.window.active
                window: root.window
                onRequestReconnect: App.reconnectTab(index)
            }
        }

        // Divider between the two panes, with a click target for swapping
        // which side leads (the small chevrons). A hairline, not a 2px rule:
        // the split is a seam inside one card.
        Rectangle {
            visible: terminalArea.split
            x: Math.round(terminalArea.width / 2) - 1
            width: 1
            height: parent.height
            color: root.hairline

            Rectangle {
                anchors.centerIn: parent
                width: 16
                height: 48
                radius: Theme.skin.radiusChip
                color: root.skin.panel
                border.width: 1
                border.color: root.hairline

                Text {
                    anchors.centerIn: parent
                    text: "swap_horiz"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 14
                    color: swapHover.containsMouse ? root.skin.accent : root.skin.icon
                }
                MouseArea {
                    id: swapHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: App.swapSplit(0)
                }
            }
        }
    }

    // ── Split toolbar ──────────────────────────────────────────────────
    // Appears only while a split exists: it names the two panes and carries
    // the broadcast toggle, which is the reason to split in the first place.
    Rectangle {
        id: splitBar
        visible: terminalArea.split
        anchors.left: terminalArea.left
        anchors.right: terminalArea.right
        anchors.top: terminalArea.top
        height: 28
        z: 5
        color: root.skin.panel

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: root.hairline
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 6
            spacing: 8

            Text {
                text: "vertical_split"
                font.family: Theme.iconFont.name
                font.pixelSize: 14
                color: root.skin.icon
            }
            Text {
                text: App.tabs[App.activeIndex] ? App.tabs[App.activeIndex].host : ""
                font.family: Theme.typography.labelMedium.family
                font.pixelSize: 11
                color: root.skin.ink
            }
            Text {
                text: "│"
                font.pixelSize: 10
                color: root.hairline
            }
            Text {
                text: App.tabs[App.splitIndex] ? App.tabs[App.splitIndex].host : ""
                font.family: Theme.typography.labelMedium.family
                font.pixelSize: 11
                color: root.skin.ink
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: broadcastRow.width + 14
                Layout.preferredHeight: 20
                radius: root.skin.radiusChip
                color: App.settings.broadcastInput === true
                       ? root.skin.accentSoft : "transparent"
                border.width: 1
                border.color: App.settings.broadcastInput === true
                              ? "transparent" : root.hairline

                Row {
                    id: broadcastRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "campaign"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 12
                        color: App.settings.broadcastInput === true
                               ? root.skin.accent : root.skin.icon
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Broadcast"
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: App.settings.broadcastInput === true
                               ? root.skin.inkStrong : root.skin.inkDim
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: App.setSetting("broadcastInput",
                                             !(App.settings.broadcastInput === true))
                }
            }

            Text {
                visible: App.settings.broadcastInput === true
                text: "composer sends to both"
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 9
                color: root.skin.inkFaint
            }

            Item {
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
                Text {
                    anchors.centerIn: parent
                    text: "close"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 14
                    color: splitCloseHover.containsMouse ? root.skin.ink : root.skin.icon
                }
                MouseArea {
                    id: splitCloseHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: App.closeSplit()
                }
            }
        }
    }

    // ── Command composer ───────────────────────────────────────────────
    CommandComposer {
        id: composer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: statusBar.top
        visible: root.composerVisible
        // Notifying property: App.terminalModel() is a slot with no change
        // signal, so binding to it would never re-run on tab changes.
        model: App.activeModel
        broadcast: terminalArea.split && App.settings.broadcastInput === true
        onEscapePressed: {
            var pane = root.activeTerminal()
            if (pane) pane.takeFocus()
        }
    }

    // ── Status bar ─────────────────────────────────────────────────────
    // A quiet footer line: no fill, one hairline above, ink-faint type. The
    // only accent is the reconnect action.
    Rectangle {
        id: statusBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: App.hasTabs ? 24 : 0
        visible: App.hasTabs
        color: "transparent"

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: root.hairline
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 12

            Text {
                text: {
                    if (!App.hasTabs) return ""
                    var t = App.tabs[App.activeIndex]
                    if (!t) return ""
                    if (t.state === "connecting") return "Connecting to " + t.host + "…"
                    if (t.state === "failed") return "tssh could not be started"
                    if (t.state === "closed") return "Session ended · exit " + t.exitStatus
                    return "tssh " + t.host
                }
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 10
                color: root.skin.inkFaint
            }

            Item { Layout.fillWidth: true }

            Text {
                visible: App.hasTabs && App.tabs[App.activeIndex]
                         && (App.tabs[App.activeIndex].state === "closed"
                             || App.tabs[App.activeIndex].state === "failed")
                text: "Reconnect"
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 10
                color: root.skin.accent
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: App.reconnectActive()
                }
            }

            // Split controls live in the status bar so they are reachable
            // without a menu: opening a split is otherwise a right-click
            // discovery problem.
            Text {
                visible: App.hasTabs && App.tabs.length > 1
                text: App.splitActive ? "Unsplit" : "Split"
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 10
                color: root.skin.accent
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (App.splitActive) App.closeSplit()
                        else root.window.openSplitPicker()
                    }
                }
            }

            Text {
                text: App.configPath()
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 10
                color: root.skin.inkFaint
                opacity: 0.8
            }
        }
    }

    Menu {
        id: tabMenu
        model: [
            { text: "Reconnect", icon: "refresh", action: function() { App.reconnectTab(App.activeIndex) } },
            { text: "Duplicate session", icon: "content_copy", action: function() { App.duplicateTab(App.activeIndex) } },
            { text: "Split with…", icon: "vertical_split", action: function() { root.window.openSplitPicker() } },
            { type: "separator" },
            { text: "Close tab", icon: "close", action: function() { root.window.requestCloseTab(App.activeIndex) } },
            { text: "Close other tabs", icon: "clear_all", action: function() { App.closeOtherTabs(App.activeIndex) } }
        ]
    }

    component HeaderIconButton: Item {
        id: hib
        property string icon: ""
        property string tooltip: ""
        signal activated()
        Layout.preferredWidth: 28
        Layout.preferredHeight: 28

        Rectangle {
            anchors.fill: parent
            radius: root.skin.radiusControl
            color: hibMouse.containsMouse ? root.hoverColor : "transparent"
        }
        Text {
            anchors.centerIn: parent
            text: hib.icon
            font.family: Theme.iconFont.name
            font.pixelSize: 17
            color: hibMouse.containsMouse ? root.skin.iconHover : root.skin.icon
        }
        MouseArea {
            id: hibMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: hib.activated()
        }
        ToolTip {
            visible: hibMouse.containsMouse && hib.tooltip.length > 0
            text: hib.tooltip
            timeout: 8000
        }
    }
}
