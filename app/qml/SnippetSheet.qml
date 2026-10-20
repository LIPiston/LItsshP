import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core

// Snippet library: named commands the palette can type into a session.
// Snippets live in the app's own state file, not in ~/.ssh/config, because
// they are a UI convenience rather than something tssh or ssh should see.
Item {
    id: root
    property var window

    readonly property var items: App.snippets

    property string editingName: ""
    property string nameText: ""
    property string commandText: ""
    property string statusError: ""
    property string statusOk: ""

    function open() {
        scrim.visible = true
        editingName = ""
        nameText = ""
        commandText = ""
        statusError = ""
        statusOk = ""
        Qt.callLater(function () { nameField.forceActiveFocus() })
    }

    function close() { scrim.visible = false }

    function edit(item) {
        editingName = item.name
        nameText = item.name
        commandText = item.command
        statusError = ""
        statusOk = ""
        Qt.callLater(function () { nameField.forceActiveFocus() })
    }

    function submit() {
        statusError = ""
        statusOk = ""
        var result = App.saveSnippet({
            "originalName": editingName,
            "name": nameText,
            "command": commandText
        })
        if (!result.ok) {
            statusError = result.error
            return
        }
        statusOk = "Saved " + result.name
        editingName = result.name
    }

    function remove(name) {
        var result = App.deleteSnippet(name)
        if (!result.ok) {
            statusError = result.error
            return
        }
        if (editingName === name) {
            editingName = ""
            nameText = ""
            commandText = ""
        }
        statusOk = "Deleted " + name
    }

    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Theme.skin.veil
        opacity: 1
        visible: false
        z: 1250
        MouseArea { anchors.fill: parent; onClicked: root.close() }
    }

    Rectangle {
        id: panel
        z: 1251
        visible: scrim.visible
        width: Math.min(680, root.width - 90)
        height: Math.min(560, root.height - 80)
        anchors.centerIn: parent
        radius: Theme.skin.radiusOverlay
        color: Theme.skin.panel
        border.width: 1
        border.color: Theme.skin.hairline

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // Header
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 22
                    anchors.rightMargin: 12
                    Text {
                        text: "Snippets"
                        font.family: Theme.typography.titleLarge.family
                        font.pixelSize: 18
                        color: Theme.skin.ink
                    }
                    Text {
                        text: "Ctrl+Shift+P to run"
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: Theme.skin.inkDim
                        opacity: 0.8
                    }
                    Item { Layout.fillWidth: true }
                    Item {
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
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

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // List
                Flickable {
                    Layout.preferredWidth: Math.min(260, panel.width * 0.42)
                    Layout.fillHeight: true
                    contentHeight: listColumn.height + 20
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    ColumnLayout {
                        id: listColumn
                        x: 14
                        y: 10
                        width: parent.width - 28
                        spacing: 4

                        Text {
                            Layout.fillWidth: true
                            visible: root.items.length === 0
                            wrapMode: Text.Wrap
                            text: "No snippets yet. Add one on the right — it will be  "
                                  + "typed into the active session."
                            font.family: Theme.typography.bodySmall.family
                            font.pixelSize: 11
                            color: Theme.skin.inkDim
                        }

                        Repeater {
                            model: root.items
                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 46
                                radius: Theme.skin.radiusControl
                                color: root.editingName === modelData.name
                                       ? Theme.skin.accentSoft
                                       : (itemMouse.containsMouse
                                          ? Theme.skin.surfaceWash : "transparent")

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 8
                                    spacing: 0
                                    Text {
                                        text: modelData.name
                                        font.family: Theme.typography.bodyMedium.family
                                        font.pixelSize: 12
                                        color: Theme.skin.ink
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: modelData.command
                                        font.family: "Cascadia Mono"
                                        font.pixelSize: 10
                                        color: Theme.skin.inkDim
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }
                                MouseArea {
                                    id: itemMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.edit(modelData)
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    color: Theme.skin.hairline
                }

                // Editor
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: 18
                    spacing: 12

                    Text {
                        text: root.editingName ? "Edit snippet" : "New snippet"
                        font.family: Theme.typography.titleSmall.family
                        font.pixelSize: 14
                        color: Theme.skin.ink
                    }

                    TextField {
                        id: nameField
                        Layout.fillWidth: true
                        label: "Name"
                        placeholderText: "Restart nginx"
                        text: root.nameText
                        type: "outlined"
                        labelBackgroundColor: Theme.skin.panel
                        onTextChanged: root.nameText = text
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 120
                        radius: Theme.skin.radiusOverlay
                        color: Theme.skin.surface
                        border.width: 1
                        border.color: Theme.skin.hairline

                        // Same clipped-TextEdit shape as the raw-block editor:
                        // nesting a TextEdit in a Flickable rendered nothing.
                        Item {
                            id: commandViewport
                            anchors.fill: parent
                            anchors.margins: 7
                            clip: true

                            property real scrollOffset: 0
                            property real contentHeight: commandArea.implicitHeight + 12
                            readonly property real maxOffset:
                                Math.max(0, contentHeight - height)

                            TextEdit {
                                id: commandArea
                                x: 6
                                y: 6 - commandViewport.scrollOffset
                                width: commandViewport.width - 12
                                text: root.commandText
                                wrapMode: TextEdit.Wrap
                                selectByMouse: true
                                font.family: "Cascadia Mono"
                                font.pixelSize: 12
                                color: Theme.skin.ink
                                selectionColor: Theme.skin.accent
                                selectedTextColor: Theme.skin.inkOnAccent
                                onTextChanged: root.commandText = text
                                onCursorPositionChanged: {
                                    var caret = cursorRectangle
                                    var top = commandViewport.scrollOffset
                                    var bottom = top + commandViewport.height
                                    if (caret.y < top)
                                        commandViewport.scrollOffset = Math.max(0, caret.y - 4)
                                    else if (caret.y + caret.height > bottom)
                                        commandViewport.scrollOffset =
                                            Math.min(commandViewport.maxOffset,
                                                     caret.y + caret.height
                                                     - commandViewport.height + 4)
                                }
                            }

                            Text {
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.leftMargin: 6
                                anchors.topMargin: 6
                                visible: commandArea.text.length === 0
                                text: "systemctl restart nginx"
                                font: commandArea.font
                                color: Theme.skin.inkDim
                                opacity: 0.55
                            }

                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.NoButton
                                onWheel: (e) => {
                                    commandViewport.scrollOffset = Math.max(0,
                                        Math.min(commandViewport.maxOffset,
                                                 commandViewport.scrollOffset - e.angleDelta.y / 3))
                                }
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Sent as typed input, so multi-line blocks and programs that read "
                              + "stdin work normally. It does not run before the shell is ready."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 10
                        color: Theme.skin.inkDim
                        opacity: 0.8
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.statusError !== ""
                        wrapMode: Text.Wrap
                        text: root.statusError
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: Theme.skin.danger
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.statusOk !== ""
                        wrapMode: Text.Wrap
                        text: root.statusOk
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: Theme.skin.accent
                    }

                    Item { Layout.fillHeight: true }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Button {
                            visible: root.editingName !== ""
                            text: "Delete"
                            type: "text"
                            onClicked: root.remove(root.editingName)
                        }
                        Button {
                            text: "Run now"
                            type: "text"
                            icon: "play_arrow"
                            enabled: root.commandText.trim().length > 0
                            onClicked: {
                                App.runSnippet(root.nameText, root.commandText)
                                root.close()
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Button {
                            text: "Save"
                            icon: "check"
                            enabled: root.nameText.trim().length > 0
                                    && root.commandText.trim().length > 0
                            onClicked: root.submit()
                        }
                    }
                }
            }
        }
    }
}
