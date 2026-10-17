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
            HeaderIconButton {
                icon: "add"
                tooltip: "New host (Ctrl+N)"
                onActivated: root.window.openHostEditor("")
            }
        }
    }

    // ── Terminal stack ─────────────────────────────────────────────────
    Item {
        id: terminalArea
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: tabBar.bottom
        anchors.bottom: statusBar.top
        clip: true

        Repeater {
            model: App.tabs

            delegate: TerminalPane {
                required property var modelData
                required property int index
                anchors.fill: parent
                visible: index === App.activeIndex
                sessionIndex: index
                focused: index === App.activeIndex && root.window.active
                window: root.window
                onRequestReconnect: App.reconnectTab(index)
            }
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
