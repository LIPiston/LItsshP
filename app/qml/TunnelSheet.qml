import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core
import QtQuick.Controls as Controls

// Port forwarding panel. A forward is part of a connection: while the host has
// an open tab that session provides it. "Keep running" is the explicit opt-in
// to take it over with `tssh -N` once the session goes away.
Item {
    id: root
    property var window

    readonly property var tunnels: App.tunnels

    function open() {
        scrim.visible = true
    }

    function close() {
        scrim.visible = false
    }

    function stateLabel(state) {
        if (state === "session") return "in session"
        if (state === "pending") return "starting…"
        if (state === "starting") return "starting…"
        if (state === "running") return "running"
        if (state === "failed") return "failed"
        return "stopped"
    }

    function stateColor(state) {
        if (state === "running" || state === "session") return Theme.skin.accent
        if (state === "failed") return Theme.skin.danger
        return Theme.skin.inkFaint
    }

    function canStop(state) {
        return state === "session" || state === "pending"
            || state === "starting" || state === "running"
    }

    function elapsed(startedAt) {
        var seconds = Math.max(0, Math.floor(Date.now() / 1000 - startedAt))
        if (seconds < 60) return seconds + "s"
        if (seconds < 3600) return Math.floor(seconds / 60) + "m"
        return Math.floor(seconds / 3600) + "h"
    }

    // ── Scrim ──────────────────────────────────────────────────────────
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Theme.skin.veil
        opacity: 1
        visible: false
        z: 1000
        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    // ── Sheet ──────────────────────────────────────────────────────────
    Rectangle {
        id: sheet
        z: 1001
        width: Math.min(480, root.width - 60)
        height: root.height
        x: root.width - (scrim.visible ? sheet.width : 0)
        color: Theme.skin.panel

        Rectangle {
            anchors.left: parent.left
            width: 1
            height: parent.height
            color: Theme.skin.hairline
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // Header
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 64

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 24
                    anchors.rightMargin: 16
                    spacing: 8

                    ColumnLayout {
                        spacing: 0
                        Text {
                            text: "Port forwarding"
                            font.family: Theme.typography.titleLarge.family
                            font.pixelSize: 19
                            color: Theme.skin.ink
                        }
                        Text {
                            text: "Rules from ~/.ssh/config"
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 11
                            color: Theme.skin.inkDim
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Stop all"
                        type: "text"
                        visible: root.tunnels.length > 0
                        onClicked: {
                            for (var i = 0; i < root.tunnels.length; i++)
                                App.stopTunnels(root.tunnels[i].alias)
                        }
                    }

                    Item {
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.skin.radiusControl
                            color: closeHover.containsMouse ? root.window.flatHover : "transparent"
                        }
                        Text {
                            anchors.centerIn: parent
                            text: "close"
                            font.family: Theme.iconFont.name
                            font.pixelSize: 17
                            color: Theme.skin.inkDim
                        }
                        MouseArea {
                            id: closeHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.close()
                        }
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.skin.hairline
                }
            }

            // Body
            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentHeight: bodyColumn.height + 32
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

                ColumnLayout {
                    id: bodyColumn
                    x: 20
                    y: 16
                    width: sheet.width - 40
                    spacing: 12

                    Text {
                        Layout.fillWidth: true
                        visible: root.tunnels.length === 0
                        wrapMode: Text.Wrap
                        text: "No forwarding rules are active. Add LocalForward, "
                              + "RemoteForward or DynamicForward rules to a host "
                              + "in the host editor, then open that host."
                        font.family: Theme.typography.bodyMedium.family
                        font.pixelSize: 12
                        color: Theme.skin.inkDim
                    }

                    Repeater {
                        model: root.tunnels

                        delegate: Rectangle {
                            id: card

                            required property var modelData

                            Layout.fillWidth: true
                            Layout.preferredHeight: cardColumn.height + 24
                            radius: Theme.skin.radiusOverlay
                            color: Theme.skin.panel
                            border.width: modelData.state === "failed" ? 1 : 0
                            border.color: Theme.skin.danger

                            ColumnLayout {
                                id: cardColumn
                                x: 14
                                y: 12
                                width: card.width - 28
                                spacing: 6

                                // Host + state
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Rectangle {
                                        width: 8
                                        height: 8
                                        radius: 4
                                        color: root.stateColor(card.modelData.state)
                                    }

                                    Text {
                                        text: card.modelData.alias
                                        font.family: Theme.typography.titleSmall.family
                                        font.pixelSize: 13
                                        color: Theme.skin.ink
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: root.stateLabel(card.modelData.state)
                                        horizontalAlignment: Text.AlignRight
                                        font.family: Theme.typography.labelSmall.family
                                        font.pixelSize: 10
                                        color: root.stateColor(card.modelData.state)
                                    }

                                    Button {
                                        text: "Stop"
                                        type: "text"
                                        visible: root.canStop(card.modelData.state)
                                        onClicked: App.stopTunnels(card.modelData.alias)
                                    }
                                }

                                // Rules
                                Repeater {
                                    model: card.modelData.rules

                                    delegate: RowLayout {
                                        required property var modelData

                                        Layout.fillWidth: true
                                        spacing: 8

                                        Text {
                                            text: modelData.kindName
                                            font.family: Theme.typography.labelSmall.family
                                            font.pixelSize: 10
                                            color: Theme.skin.inkDim
                                            Layout.preferredWidth: 52
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.label
                                            elide: Text.ElideMiddle
                                            font.family: Theme.typography.bodySmall.family
                                            font.pixelSize: 12
                                            color: Theme.skin.ink
                                        }
                                        Text {
                                            visible: !!modelData.source
                                            text: modelData.source
                                            font.family: Theme.typography.labelSmall.family
                                            font.pixelSize: 9
                                            color: Theme.skin.inkDim
                                            opacity: 0.7
                                        }
                                    }
                                }

                                // Keep running
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 2
                                    spacing: 8

                                    Rectangle {
                                        width: 18
                                        height: 18
                                        radius: 3
                                        color: card.modelData.persist ? Theme.skin.accent : "transparent"
                                        border.width: 1
                                        border.color: card.modelData.persist ? Theme.skin.accent
                                                                              : Theme.skin.hairline
                                        Text {
                                            anchors.centerIn: parent
                                            visible: card.modelData.persist
                                            text: "check"
                                            font.family: Theme.iconFont.name
                                            font.pixelSize: 12
                                            color: Theme.skin.inkOnAccent
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: App.setTunnelPersist(card.modelData.alias,
                                                                            !card.modelData.persist)
                                        }
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        wrapMode: Text.Wrap
                                        text: "Keep running after the session ends"
                                        font.family: Theme.typography.bodySmall.family
                                        font.pixelSize: 11
                                        color: Theme.skin.inkDim
                                    }

                                    Text {
                                        visible: card.modelData.state === "running"
                                        text: root.elapsed(card.modelData.startedAt)
                                        font.family: Theme.typography.labelSmall.family
                                        font.pixelSize: 10
                                        color: Theme.skin.inkDim
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    visible: !!card.modelData.error
                                    wrapMode: Text.Wrap
                                    text: card.modelData.error
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 10
                                    color: Theme.skin.danger
                                }

                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.WrapAnywhere
                                    text: card.modelData.command
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 9
                                    color: Theme.skin.inkDim
                                    opacity: 0.6
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
