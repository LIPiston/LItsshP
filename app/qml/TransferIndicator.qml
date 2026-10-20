import QtQuick
import QtQuick.Layouts
import md3.Core

// Live transfer indicator for the main window's top-right corner.
//
// The bar is a plain Rectangle rather than md3's LinearProgress: that control
// drives its fill through a Behaviour animation, and this machine's render
// loop does not advance animations, which would freeze the value.
Item {
    id: root

    readonly property var transfers: App.transfers
    readonly property var current: transfers.length > 0 ? transfers[0] : null
    readonly property int extra: Math.max(0, transfers.length - 1)

    signal clicked()

    implicitWidth: visible ? 232 : 0
    implicitHeight: visible ? 34 : 0
    visible: App.transferActive

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.skin.radiusOverlay
        color: Theme.skin.surfaceWash
        border.width: 1
        border.color: Theme.skin.hairline

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 9
            anchors.rightMargin: 10
            spacing: 8

            Text {
                text: root.current && root.current.label === "Download"
                      ? "download" : "upload"
                font.family: Theme.iconFont.name
                font.pixelSize: 15
                color: Theme.skin.accent
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 5

                    Text {
                        Layout.fillWidth: true
                        // Route rather than "Upload/Download": the arrow shows
                        // which machine is the destination.
                        text: root.current ? root.current.route : ""
                        elide: Text.ElideRight
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: Theme.skin.ink
                    }
                    Text {
                        visible: root.extra > 0
                        text: "+" + root.extra
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: Theme.skin.inkDim
                    }
                }

                // Track + fill. No Behaviour: see the note above.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 3
                    radius: 2
                    color: Theme.skin.hover

                    Rectangle {
                        width: parent.width * (root.current ? root.current.fraction : 0)
                        height: parent.height
                        radius: parent.radius
                        color: Theme.skin.accent
                    }
                }
            }

            Text {
                text: root.current ? Math.round(root.current.fraction * 100) + "%" : ""
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 10
                color: Theme.skin.inkDim
            }
        }
    }
}
