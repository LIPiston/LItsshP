import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core

// Transfer list popup behind the transfer icon in the tab strip.
//
// Two sections: transfers in flight, and a short history of finished ones.
// It is a floating panel rather than a page so it can be opened without
// leaving the session you are working in. The root covers the whole workspace
// so a click anywhere else dismisses it.
Item {
    id: root
    property var window
    property bool opened: false

    signal transferRequested(string alias)

    readonly property var active: App.transfers
    readonly property var history: App.transferHistory

    visible: opened
    z: 5000

    function open() { root.opened = true }
    function close() { root.opened = false }
    function toggle() { root.opened = !root.opened }

    MouseArea {
        anchors.fill: parent
        onClicked: root.close()
    }

    Rectangle {
        id: panel
        width: 340
        height: Math.min(root.height - 60, content.implicitHeight + 16)
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: 14
        anchors.topMargin: 8
        radius: Theme.skin.radiusOverlay
        color: Theme.skin.surfaceWash
        border.width: 1
        border.color: Theme.skin.hairline
        clip: true

        // Swallow clicks so the scrim below does not close the panel.
        MouseArea { anchors.fill: parent }

        Flickable {
            id: scroller
            anchors.fill: parent
            anchors.margins: 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
            contentWidth: width
            contentHeight: Math.max(content.implicitHeight, height)
            interactive: content.implicitHeight + 16 > panel.height

            ColumnLayout {
                id: content
                width: scroller.width
                spacing: 2

                // ── In flight ──────────────────────────────────────────
                Text {
                    Layout.leftMargin: 6
                    Layout.topMargin: 2
                    Layout.bottomMargin: 2
                    visible: root.active.length > 0
                    text: "IN PROGRESS"
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    color: Theme.skin.inkDim
                    opacity: 0.8
                }

                Repeater {
                    model: root.active
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                text: "swap_vert"
                                font.family: Theme.iconFont.name
                                font.pixelSize: 13
                                color: Theme.skin.accent
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.route
                                elide: Text.ElideRight
                                font.family: Theme.typography.labelLarge.family
                                font.pixelSize: 11
                                color: Theme.skin.ink
                            }
                            Text {
                                text: Math.round(modelData.fraction * 100) + "%"
                                font.family: Theme.typography.labelSmall.family
                                font.pixelSize: 10
                                color: Theme.skin.inkDim
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 3
                            radius: 2
                            color: Theme.skin.hover
                            Rectangle {
                                width: parent.width * modelData.fraction
                                height: parent.height
                                radius: 2
                                color: Theme.skin.accent
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: modelData.detail
                            elide: Text.ElideRight
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 9
                            color: Theme.skin.inkDim
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    Layout.bottomMargin: 4
                    height: 1
                    visible: root.active.length > 0 && root.history.length > 0
                    color: Theme.skin.hairline
                }

                // ── History ────────────────────────────────────────────
                Text {
                    Layout.leftMargin: 6
                    Layout.topMargin: 2
                    Layout.bottomMargin: 2
                    visible: root.history.length > 0
                    text: "RECENT"
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    color: Theme.skin.inkDim
                    opacity: 0.8
                }

                Repeater {
                    model: root.history.slice(0, 8)
                    delegate: Item {
                        id: histRow
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 34

                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.skin.radiusControl
                            color: histMouse.containsMouse ? root.window.flatHover : "transparent"
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 8
                            spacing: 7

                            Text {
                                text: histRow.modelData.status === "failed"
                                      ? "error" : "check_circle"
                                font.family: Theme.iconFont.name
                                font.pixelSize: 13
                                color: histRow.modelData.status === "failed"
                                       ? Theme.skin.danger : Theme.skin.info
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: -1
                                Text {
                                    Layout.fillWidth: true
                                    text: histRow.modelData.route
                                    elide: Text.ElideRight
                                    font.family: Theme.typography.labelLarge.family
                                    font.pixelSize: 11
                                    color: Theme.skin.ink
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: histRow.modelData.status === "failed"
                                          ? (histRow.modelData.detail || "Failed")
                                          : histRow.modelData.ago
                                    elide: Text.ElideRight
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 9
                                    color: histRow.modelData.status === "failed"
                                           ? Theme.skin.danger
                                           : Theme.skin.inkDim
                                }
                            }

                            Text {
                                text: "chevron_right"
                                font.family: Theme.iconFont.name
                                font.pixelSize: 13
                                color: Theme.skin.inkDim
                                opacity: 0.6
                            }
                        }

                        MouseArea {
                            id: histMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var alias = histRow.modelData.alias
                                root.close()
                                root.transferRequested(alias)
                            }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    Layout.bottomMargin: 10
                    visible: root.active.length === 0 && root.history.length === 0
                    text: "No transfers yet."
                    horizontalAlignment: Text.AlignHCenter
                    font.family: Theme.typography.bodySmall.family
                    font.pixelSize: 11
                    color: Theme.skin.inkDim
                }
            }
        }
    }
}
