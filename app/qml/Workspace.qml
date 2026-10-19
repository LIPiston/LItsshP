import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core

// Right side: flat tab strip + terminal stack + empty state + status bar.
Item {
    id: root
    property var window

    readonly property var c: Theme.color
    readonly property color hairline: c.outlineVariant
    readonly property color hoverColor: window ? window.flatHover : "#22ffffff"

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
        width: Math.min(460, Math.max(280, parent.width - 80))
        spacing: 14
        visible: !App.hasTabs

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 64
            Layout.preferredHeight: 64
            radius: 32
            color: root.window ? root.window.flatPanelHigh : Theme.color.surfaceContainer
            Text {
                anchors.centerIn: parent
                text: "terminal"
                font.family: Theme.iconFont.name
                font.pixelSize: 30
                color: Theme.color.primary
            }
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: App.hosts.length === 0 ? "No hosts yet" : "Pick a host to connect"
            font.family: Theme.typography.headlineSmall.family
            font.pixelSize: 22
            color: Theme.color.onSurfaceColor
        }

        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignHCenter
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: App.hosts.length === 0
                  ? "Hosts are read from ~/.ssh/config — the same file tssh uses. Add one to get started."
                  : "Sessions open as tabs. Everything runs through tssh, so stored passwords, jump hosts and trzsz file transfer keep working."
            font.family: Theme.typography.bodyMedium.family
            font.pixelSize: 13
            color: Theme.color.onSurfaceVariantColor
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 10

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
            Layout.topMargin: 16
            spacing: 16

            Repeater {
                model: ["Ctrl+N  new host", "Ctrl+T  search", "Ctrl+,  settings"]
                Text {
                    required property string modelData
                    text: modelData
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 10
                    color: Theme.color.onSurfaceVariantColor
                    opacity: 0.7
                }
            }
        }
    }

    // ── Tab strip ──────────────────────────────────────────────────────
    Rectangle {
        id: tabBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: App.hasTabs ? 44 : 0
        visible: App.hasTabs
        color: Theme.color.surface

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: root.hairline
            opacity: 0.7
        }

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

                    width: Math.min(240, 112 + String(modelData.host).length * 5.5)
                    height: tabList.height

                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: 6
                        radius: root.window ? root.window.radiusSmall : 6
                        color: tabItem.isActive
                               ? Theme.color.surfaceContainerHigh
                               : (tabMouse.containsMouse ? root.hoverColor : "transparent")

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 4
                            spacing: 7

                            Rectangle {
                                Layout.preferredWidth: 7
                                Layout.preferredHeight: 7
                                radius: 4
                                color: {
                                    if (modelData.state === "connected") return Theme.color.primary
                                    if (modelData.state === "failed") return Theme.color.error
                                    if (modelData.state === "closed") return Theme.color.outline
                                    return Theme.color.tertiary
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.host
                                elide: Text.ElideRight
                                font.family: Theme.typography.labelLarge.family
                                font.pixelSize: 12
                                color: tabItem.isActive ? Theme.color.onSurfaceColor
                                                        : Theme.color.onSurfaceVariantColor
                            }

                            Item {
                                Layout.preferredWidth: 20
                                Layout.preferredHeight: 20

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 4
                                    color: closeMouse.containsMouse ? root.hoverColor : "transparent"
                                }
                                Text {
                                    anchors.centerIn: parent
                                    text: "close"
                                    font.family: Theme.iconFont.name
                                    font.pixelSize: 13
                                    color: Theme.color.onSurfaceVariantColor
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

                    Rectangle {
                        visible: tabItem.isActive
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width - 16
                        height: 2
                        radius: 1
                        color: Theme.color.primary
                    }

                    MouseArea {
                        id: tabMouse
                        anchors.fill: parent
                        anchors.rightMargin: 24
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
            // Port forwarding. Counts active forwards; the panel explains
            // whether each is provided by a session or by its own process.
            Item {
                id: tunnelButton
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30

                Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: tunnelMouse.containsMouse ? root.hoverColor : "transparent"
                }
                Text {
                    anchors.centerIn: parent
                    text: "swap_horiz"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 17
                    color: App.tunnelActive ? Theme.color.primary
                                            : Theme.color.onSurfaceVariantColor
                }
                Rectangle {
                    visible: App.tunnelCount > 0
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.rightMargin: 3
                    anchors.topMargin: 2
                    width: Math.max(13, tunnelBadge.implicitWidth + 6)
                    height: 13
                    radius: 7
                    color: Theme.color.primary
                    Text {
                        id: tunnelBadge
                        anchors.centerIn: parent
                        text: App.tunnelCount
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                        color: Theme.color.onPrimaryColor
                    }
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
                    text: "Port forwarding (Ctrl+Shift+T)"
                    timeout: 8000
                }
            }
            HeaderIconButton {
                icon: App.settings.composerVisible !== false ? "keyboard_hide" : "keyboard"
                tooltip: (App.settings.composerVisible !== false ? "Hide" : "Show") + " command composer"
                onActivated: App.setSetting("composerVisible", !(App.settings.composerVisible !== false))
            }
            // Opens the transfer list. The badge shows how many are running;
            // `swap_vert` reads as "moving things between two places", which
            // is what the panel is for.
            Item {
                id: transferButton
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30

                Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: (transferMouse.containsMouse || transferPopover.opened)
                           ? root.hoverColor : "transparent"
                }
                Text {
                    anchors.centerIn: parent
                    text: "swap_vert"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 17
                    color: (App.transferActive || transferPopover.opened)
                           ? Theme.color.primary : Theme.color.onSurfaceVariantColor
                }
                // Small running-count dot; also the only hint that transfers
                // are happening when the indicator is collapsed.
                Rectangle {
                    visible: App.transferCount > 0
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.rightMargin: 3
                    anchors.topMargin: 2
                    width: Math.max(13, badgeText.implicitWidth + 6)
                    height: 13
                    radius: 7
                    color: Theme.color.primary
                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: App.transferCount
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                        color: Theme.color.onPrimaryColor
                    }
                }
                MouseArea {
                    id: transferMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: transferPopover.toggle()
                }
                ToolTip {
                    visible: transferMouse.containsMouse && !transferPopover.opened
                    text: "Transfers"
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
        // which side leads (the small chevrons).
        Rectangle {
            visible: terminalArea.split
            x: Math.round(terminalArea.width / 2) - 1
            width: 2
            height: parent.height
            color: Theme.color.outlineVariant

            Rectangle {
                anchors.centerIn: parent
                width: 18
                height: 54
                radius: 9
                color: Theme.color.surfaceContainerHigh
                border.width: 1
                border.color: Theme.color.outlineVariant

                Text {
                    anchors.centerIn: parent
                    text: "swap_horiz"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 14
                    color: swapHover.containsMouse ? Theme.color.primary
                                                   : Theme.color.onSurfaceVariantColor
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
        height: 30
        z: 5
        color: Theme.color.surfaceContainerHigh

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: root.hairline
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 8
            spacing: 10

            Text {
                text: "vertical_split"
                font.family: Theme.iconFont.name
                font.pixelSize: 14
                color: Theme.color.onSurfaceVariantColor
            }
            Text {
                text: App.tabs[App.activeIndex] ? App.tabs[App.activeIndex].host : ""
                font.family: Theme.typography.labelMedium.family
                font.pixelSize: 11
                color: Theme.color.onSurfaceColor
            }
            Text {
                text: "│"
                font.pixelSize: 11
                color: Theme.color.outline
            }
            Text {
                text: App.tabs[App.splitIndex] ? App.tabs[App.splitIndex].host : ""
                font.family: Theme.typography.labelMedium.family
                font.pixelSize: 11
                color: Theme.color.onSurfaceColor
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: broadcastRow.width + 16
                Layout.preferredHeight: 22
                radius: 11
                color: App.settings.broadcastInput === true
                       ? Theme.color.primaryContainer : "transparent"
                border.width: 1
                border.color: App.settings.broadcastInput === true
                              ? "transparent" : root.hairline

                Row {
                    id: broadcastRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "campaign"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 13
                        color: App.settings.broadcastInput === true
                               ? Theme.color.onPrimaryContainerColor
                               : Theme.color.onSurfaceVariantColor
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Broadcast"
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: App.settings.broadcastInput === true
                               ? Theme.color.onPrimaryContainerColor
                               : Theme.color.onSurfaceVariantColor
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
                text: "open composer to send to both"
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 9
                color: Theme.color.onSurfaceVariantColor
            }

            Item {
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
                Text {
                    anchors.centerIn: parent
                    text: "close"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 14
                    color: splitCloseHover.containsMouse ? Theme.color.onSurfaceColor
                                                         : Theme.color.onSurfaceVariantColor
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
    Rectangle {
        id: statusBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: App.hasTabs ? 26 : 0
        visible: App.hasTabs
        color: Theme.color.surface

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: root.hairline
            opacity: 0.7
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 14

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
                color: Theme.color.onSurfaceVariantColor
            }

            Item { Layout.fillWidth: true }

            Text {
                visible: App.hasTabs && App.tabs[App.activeIndex]
                         && (App.tabs[App.activeIndex].state === "closed"
                             || App.tabs[App.activeIndex].state === "failed")
                text: "Reconnect"
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 10
                color: Theme.color.primary
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
                color: Theme.color.primary
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
                color: Theme.color.onSurfaceVariantColor
                opacity: 0.7
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
        Layout.preferredWidth: 30
        Layout.preferredHeight: 30

        Rectangle {
            anchors.fill: parent
            radius: 6
            color: hibMouse.containsMouse ? root.hoverColor : "transparent"
        }
        Text {
            anchors.centerIn: parent
            text: hib.icon
            font.family: Theme.iconFont.name
            font.pixelSize: 17
            color: Theme.color.onSurfaceVariantColor
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
