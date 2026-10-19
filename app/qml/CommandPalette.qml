import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core

// Ctrl+Shift+P palette: fuzzy-jump to a host or run an app action.
Item {
    id: root
    property var window
    property string query: ""
    property int currentIndex: 0

    signal hostChosen(string alias)
    signal actionChosen(string action)
    signal snippetChosen(string name, string command)

    readonly property var actions: [
        { kind: "action", id: "new-host", title: "New host", icon: "add" },
        { kind: "action", id: "settings", title: "Open settings", icon: "settings" },
        { kind: "action", id: "snippets", title: "Manage snippets", icon: "code" },
        { kind: "action", id: "split", title: "Split the terminal", icon: "vertical_split" },
        { kind: "action", id: "restore", title: "Reopen the last session", icon: "history" },
        { kind: "action", id: "tunnels", title: "Port forwarding", icon: "swap_horiz" },
        { kind: "action", id: "keys", title: "SSH keys and known hosts", icon: "key" },
        { kind: "action", id: "toggle-sidebar", title: "Toggle sidebar", icon: "left_panel_close" },
        { kind: "action", id: "refresh", title: "Reload ~/.ssh/config", icon: "refresh" }
    ]

    function open() {
        query = ""
        currentIndex = 0
        scrim.visible = true
        rebuild()
        Qt.callLater(function() { searchInput.forceActiveFocus() })
    }

    function close() {
        scrim.visible = false
    }

    function rebuild() {
        model.clear()
        var needle = query.trim().toLowerCase()
        var hosts = App.hosts
        for (var i = 0; i < hosts.length; i++) {
            var h = hosts[i]
            var hay = (h.alias + " " + h.hostname + " " + h.user + " " + (h.groups || []).join(" ")).toLowerCase()
            if (needle === "" || hay.indexOf(needle) >= 0) {
                model.append({
                    kind: "host",
                    id: h.alias,
                    title: h.alias,
                    subtitle: (h.user ? h.user + "@" : "") + h.hostname +
                              (h.port && h.port !== "22" ? ":" + h.port : ""),
                    icon: "dns"
                })
            }
        }
        for (var a = 0; a < actions.length; a++) {
            var act = actions[a]
            if (needle === "" || act.title.toLowerCase().indexOf(needle) >= 0) {
                model.append({
                    kind: "action",
                    id: act.id,
                    title: act.title,
                    subtitle: "Action",
                    icon: act.icon
                })
            }
        }
        // Snippets are listed as their own kind: choosing one types it into
        // the active session rather than opening a surface.
        var snippets = App.snippets
        for (var s = 0; s < snippets.length; s++) {
            var snip = snippets[s]
            var haystack = (snip.name + " " + snip.command).toLowerCase()
            if (needle === "" || haystack.indexOf(needle) >= 0) {
                model.append({
                    kind: "snippet",
                    id: snip.name,
                    title: snip.name,
                    subtitle: snip.command,
                    icon: "keyboard_return"
                })
            }
        }
        currentIndex = model.count > 0 ? 0 : -1
    }

    function activate(index) {
        if (index < 0 || index >= model.count) return
        var item = model.get(index)
        close()
        if (item.kind === "host") root.hostChosen(item.id)
        else if (item.kind === "snippet") root.snippetChosen(item.id, item.subtitle)
        else root.actionChosen(item.id)
    }

    Rectangle {
        id: scrim
        anchors.fill: parent
        color: "#000000"
        opacity: 0.42
        visible: false
        z: 1200
        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    Rectangle {
        id: box
        z: 1201
        visible: scrim.visible
        width: Math.min(620, root.width - 100)
        height: Math.min(430, 90 + model.count * 44 + 16)
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.max(60, root.height * 0.16)
        radius: 14
        color: Theme.color.surfaceContainerHigh
        border.width: 1
        border.color: Theme.color.outline

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // Search row
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 54

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 10

                    Text {
                        text: "search"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 19
                        color: Theme.color.onSurfaceVariantColor
                    }

                    TextInput {
                        id: searchInput
                        Layout.fillWidth: true
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: Theme.typography.bodyLarge.family
                        font.pixelSize: 15
                        color: Theme.color.onSurfaceColor
                        selectionColor: Theme.color.primary
                        selectedTextColor: Theme.color.onPrimaryColor
                        clip: true
                        onTextChanged: {
                            root.query = text
                            root.rebuild()
                        }

                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            visible: !parent.text
                            text: "Search hosts and actions…"
                            font: parent.font
                            color: Theme.color.onSurfaceVariantColor
                            opacity: 0.6
                        }

                        Keys.onDownPressed: {
                            if (root.model.count > 0)
                                root.currentIndex = Math.min(root.model.count - 1, root.currentIndex + 1)
                            resultList.positionViewAtIndex(root.currentIndex, ListView.Contain)
                        }
                        Keys.onUpPressed: {
                            if (root.model.count > 0)
                                root.currentIndex = Math.max(0, root.currentIndex - 1)
                            resultList.positionViewAtIndex(root.currentIndex, ListView.Contain)
                        }
                        Keys.onReturnPressed: root.activate(root.currentIndex)
                        Keys.onEscapePressed: root.close()
                    }

                    Text {
                        text: "esc"
                        font.family: Theme.typography.labelSmall.family
                        font.pixelSize: 10
                        color: Theme.color.onSurfaceVariantColor
                        opacity: 0.6
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.color.outlineVariant
                    opacity: 0.7
                }
            }

            ListView {
                id: resultList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: 6
                Layout.bottomMargin: 8
                model: model
                currentIndex: root.currentIndex
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                delegate: Item {
                    id: rowItem
                    required property var modelData
                    required property int index
                    width: resultList.width
                    height: 42

                    Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        radius: 8
                        color: index === root.currentIndex ? Theme.color.primaryContainer : "transparent"
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 18
                        anchors.rightMargin: 18
                        spacing: 12

                        Text {
                            text: modelData.icon
                            font.family: Theme.iconFont.name
                            font.pixelSize: 17
                            color: index === root.currentIndex
                                   ? Theme.color.onPrimaryContainerColor
                                   : Theme.color.onSurfaceVariantColor
                        }
                        Text {
                            text: modelData.title
                            font.family: Theme.typography.bodyMedium.family
                            font.pixelSize: 13
                            color: Theme.color.onSurfaceColor
                        }
                        Text {
                            Layout.fillWidth: true
                            text: modelData.subtitle
                            elide: Text.ElideMiddle
                            horizontalAlignment: Text.AlignRight
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 10
                            color: Theme.color.onSurfaceVariantColor
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: root.currentIndex = index
                        onClicked: root.activate(index)
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: model.count === 0 ? 40 : 0
                Text {
                    anchors.centerIn: parent
                    text: "No matches"
                    font.family: Theme.typography.bodySmall.family
                    font.pixelSize: 12
                    color: Theme.color.onSurfaceVariantColor
                }
            }
        }
    }

    ListModel { id: model }
}
