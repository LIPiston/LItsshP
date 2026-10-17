import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core
import QtQuick.Controls as Controls

// Left rail: brand, search, grouped host list, footer actions.
// Deliberately flat — a single panel colour, no cards, hairline separators.
Item {
    id: root
    property var window
    property string filter: ""
    property string selectedGroup: ""
    property string selectedAlias: ""

    signal hostActivated(string alias)
    signal hostEditRequested(string alias)
    signal transferRequested(string alias)
    signal deleteRequested(string alias)
    signal addRequested()
    signal settingsRequested()

    readonly property var c: Theme.color
    readonly property color hairline: c.outlineVariant
    readonly property color hoverColor: window ? window.flatHover : "#22ffffff"
    readonly property color selectedColor: window ? window.flatSelected : "#33ffffff"

    function focusSearch() {
        searchField.forceActiveFocus()
        searchField.selectAll()
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.color.surfaceContainerLow
    }

    // ── Brand + window controls ────────────────────────────────────────
    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 74

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26
                radius: 13
                color: Theme.color.primary
                Text {
                    anchors.centerIn: parent
                    text: "terminal"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: Theme.color.onPrimaryColor
                }
            }

            ColumnLayout {
                spacing: -1
                Text {
                    text: "LItsshP"
                    font.family: Theme.typography.titleSmall.family
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: Theme.color.onSurfaceColor
                }
                Text {
                    text: "tssh · ~/.ssh"
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 10
                    color: Theme.color.onSurfaceVariantColor
                }
                Text {
                    text: App.hosts.length === 1 ? "1 host"
                                                        : App.hosts.length + " hosts"
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 10
                    color: Theme.color.onSurfaceVariantColor
                    opacity: 0.75
                }
            }

            Item { Layout.fillWidth: true }

        }
    }

    Rectangle {
        anchors.top: header.bottom
        width: parent.width
        height: 1
        color: root.hairline
        opacity: 0.6
    }

    // ── Search ─────────────────────────────────────────────────────────
    Rectangle {
        id: searchBox
        anchors.top: header.bottom
        anchors.topMargin: 14
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        height: 36
        radius: window ? window.radiusMedium : 10
        color: searchMouse.containsMouse ? Theme.color.surfaceContainerHigh
                                         : Theme.color.surfaceContainer
        border.width: searchField.activeFocus ? 1 : 0
        border.color: Theme.color.primary

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 8
            spacing: 6

            Text {
                text: "search"
                font.family: Theme.iconFont.name
                font.pixelSize: 17
                color: Theme.color.onSurfaceVariantColor
            }

            TextInput {
                id: searchField
                Layout.fillWidth: true
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.color.onSurfaceColor
                selectionColor: Theme.color.primary
                selectedTextColor: Theme.color.onPrimaryColor
                font.family: Theme.typography.bodyMedium.family
                font.pixelSize: 13
                clip: true
                onTextChanged: root.filter = text

                Text {
                    anchors.fill: parent
                    verticalAlignment: Text.AlignVCenter
                    visible: !searchField.text && !searchField.activeFocus
                    text: "Search hosts"
                    font: searchField.font
                    color: Theme.color.onSurfaceVariantColor
                    opacity: 0.75
                }

                Keys.onEscapePressed: {
                    text = ""
                    root.filter = ""
                }
                Keys.onDownPressed: hostList.incrementCurrentIndex()
                Keys.onUpPressed: hostList.decrementCurrentIndex()
                Keys.onReturnPressed: {
                    if (hostList.currentItem && hostList.currentItem.alias)
                        root.hostActivated(hostList.currentItem.alias)
                }
            }

            Text {
                visible: searchField.text.length > 0
                text: "close"
                font.family: Theme.iconFont.name
                font.pixelSize: 15
                color: Theme.color.onSurfaceVariantColor
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        searchField.text = ""
                        root.filter = ""
                    }
                }
            }
        }

        MouseArea {
            id: searchMouse
            anchors.fill: parent
            acceptedButtons: Qt.NoButton
            hoverEnabled: true
            z: -1
        }
    }

    // ── Group chips ────────────────────────────────────────────────────
    Flickable {
        id: groupBar
        anchors.top: searchBox.bottom
        anchors.topMargin: 10
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        height: App.groups.length > 0 ? 30 : 0
        visible: height > 0
        contentWidth: groupRow.width
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.HorizontalFlick

        Row {
            id: groupRow
            spacing: 6
            GroupChip {
                label: "All"
                active: root.selectedGroup === ""
                onActivated: root.selectedGroup = ""
            }
            Repeater {
                model: App.groups
                GroupChip {
                    label: modelData
                    active: root.selectedGroup === modelData
                    onActivated: root.selectedGroup = (root.selectedGroup === modelData ? "" : modelData)
                }
            }
        }
    }

    // ── Host list ──────────────────────────────────────────────────────
    ListView {
        id: hostList
        anchors.top: groupBar.visible ? groupBar.bottom : searchBox.bottom
        anchors.topMargin: 12
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: footer.top
        anchors.bottomMargin: 8
        clip: true
        spacing: 2
        model: hostModel
        currentIndex: -1
        boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

        delegate: HostRow {
            width: hostList.width - 16
            x: 8
            alias: model.alias
            hostname: model.hostname
            port: model.port
            user: model.user
            groups: model.groups
            hasPassword: model.hasPassword
            active: root.selectedAlias === model.alias ||
                    (App.hasTabs && App.tabs[App.activeIndex].host === model.alias)
            query: root.filter

            onClicked: {
                root.selectedAlias = model.alias
                root.hostActivated(model.alias)
            }
            onEditRequested: root.hostEditRequested(model.alias)
            onContextRequested: (x, y) => hostMenu.show(model.alias, x, y)
            onHoveredChanged: if (hovered) hostList.currentIndex = index
        }
    }

    // ── Empty state ────────────────────────────────────────────────────
    ColumnLayout {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 20
        width: parent.width - 48
        spacing: 10
        visible: hostList.count === 0
        opacity: 0.85

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: root.filter.length > 0 ? "search_off" : "dns"
            font.family: Theme.iconFont.name
            font.pixelSize: 34
            color: Theme.color.onSurfaceVariantColor
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.filter.length > 0
                  ? "No host matches \u201c" + root.filter + "\u201d"
                  : "No hosts in ~/.ssh/config yet"
            font.family: Theme.typography.bodyMedium.family
            font.pixelSize: 13
            color: Theme.color.onSurfaceVariantColor
        }
        Button {
            Layout.alignment: Qt.AlignHCenter
            visible: root.filter.length === 0
            text: "Add host"
            icon: "add"
            type: "tonal"
            onClicked: root.addRequested()
        }
    }

    // ── Footer ─────────────────────────────────────────────────────────
    Rectangle {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 52
        color: "transparent"

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: root.hairline
            opacity: 0.6
        }

        Row {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 12
            spacing: 4

            FooterButton {
                icon: "add"
                label: "New host"
                onActivated: root.addRequested()
            }
            FooterButton {
                icon: "settings"
                label: "Settings"
                onActivated: root.settingsRequested()
            }
        }
    }

    // ── Filtered model ─────────────────────────────────────────────────
    ListModel { id: hostModel }

    function rebuild() {
        hostModel.clear()
        var needle = root.filter.trim().toLowerCase()
        var group = root.selectedGroup
        var hosts = App.hosts
        for (var i = 0; i < hosts.length; i++) {
            var h = hosts[i]
            if (group !== "" && h.groups.indexOf(group) < 0)
                continue
            if (needle !== "") {
                var label = h.groups.join(" ").toLowerCase()
                if (h.alias.toLowerCase().indexOf(needle) < 0 &&
                    h.hostname.toLowerCase().indexOf(needle) < 0 &&
                    h.user.toLowerCase().indexOf(needle) < 0 &&
                    label.indexOf(needle) < 0)
                    continue
            }
            hostModel.append(h)
        }
    }

    onFilterChanged: rebuild()
    onSelectedGroupChanged: rebuild()

    Connections {
        target: App
        function onHostsChanged() { root.rebuild() }
    }

    Component.onCompleted: rebuild()

    // ── Inline components ──────────────────────────────────────────────
    component FooterButton: Item {
        id: fb
        property string icon: ""
        property string label: ""
        signal activated()
        implicitWidth: fbRow.width + 20
        implicitHeight: 34
        width: implicitWidth
        height: implicitHeight

        Rectangle {
            anchors.fill: parent
            radius: 8
            color: fbMouse.containsMouse ? root.hoverColor : "transparent"
        }
        Row {
            id: fbRow
            anchors.centerIn: parent
            spacing: 6
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: fb.icon
                font.family: Theme.iconFont.name
                font.pixelSize: 17
                color: Theme.color.onSurfaceVariantColor
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: fb.label
                font.family: Theme.typography.labelMedium.family
                font.pixelSize: 12
                color: Theme.color.onSurfaceVariantColor
            }
        }
        MouseArea {
            id: fbMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: fb.activated()
        }
    }

    component GroupChip: Item {
        id: chip
        property string label: ""
        property bool active: false
        signal activated()
        width: chipText.implicitWidth + 20
        height: 26

        Rectangle {
            anchors.fill: parent
            radius: 13
            color: chip.active ? Theme.color.secondaryContainer : "transparent"
            border.width: 1
            border.color: chip.active ? "transparent" : root.hairline
        }
        Text {
            id: chipText
            anchors.centerIn: parent
            text: chip.label
            font.family: Theme.typography.labelMedium.family
            font.pixelSize: 11
            color: chip.active ? Theme.color.onSecondaryContainerColor
                               : Theme.color.onSurfaceVariantColor
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: chip.activated()
        }
    }

    component HostRow: Rectangle {
        id: row
        property string alias: ""
        property string hostname: ""
        property string port: "22"
        property string user: ""
        property var groups: []
        property bool hasPassword: false
        property bool active: false
        property string query: ""
        property bool hovered: rowMouse.containsMouse

        signal clicked()
        signal editRequested()
        signal transferRequested()
        signal deleteRequested()
        signal contextRequested(real x, real y)

        height: 54
        radius: window ? window.radiusMedium : 10
        color: active ? root.selectedColor : (rowMouse.containsMouse ? root.hoverColor : "transparent")

        Rectangle {
            // Accent bar marks the active session.
            visible: row.active
            width: 3
            height: 22
            radius: 2
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.color.primary
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 8
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                radius: 16
                color: row.active ? Theme.color.primaryContainer : Theme.color.surfaceContainerHigh
                Text {
                    anchors.centerIn: parent
                    text: "dns"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: row.active ? Theme.color.onPrimaryContainerColor
                                      : Theme.color.onSurfaceVariantColor
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                RowLayout {
                    spacing: 6
                    Layout.fillWidth: true
                    Text {
                        text: row.alias
                        font.family: Theme.typography.bodyMedium.family
                        font.pixelSize: 13
                        font.weight: Font.Medium
                        color: Theme.color.onSurfaceColor
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: row.hasPassword
                        text: "key"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 12
                        color: Theme.color.tertiary
                        opacity: 0.9
                    }
                }

                Text {
                    text: (row.user ? row.user + "@" : "") + row.hostname +
                          (row.port && row.port !== "22" ? ":" + row.port : "")
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 11
                    color: Theme.color.onSurfaceVariantColor
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }
            }

            Text {
                visible: rowMouse.containsMouse
                text: "more_vert"
                font.family: Theme.iconFont.name
                font.pixelSize: 17
                color: Theme.color.onSurfaceVariantColor
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -8
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var p = row.mapToItem(root, row.width - 24, row.height / 2)
                            row.contextRequested(p.x, p.y)
                        }
                    }
            }
        }

        MouseArea {
            id: rowMouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: Qt.PointingHandCursor
            onClicked: (mouse) => {
                if (mouse.button === Qt.RightButton) {
                    // Hand the click position to the sheet so the menu opens
                    // at the cursor rather than at the row's corner.
                    var p = row.mapToItem(root, mouse.x, mouse.y)
                    row.contextRequested(p.x, p.y)
                } else {
                    row.clicked()
                }
            }
        }
    }

    // ── Host context menu ──────────────────────────────────────────────
    Menu {
        id: hostMenu
        property string alias: ""
        property real anchorX: 0
        property real anchorY: 0

        model: [
            { text: "Edit", icon: "edit", action: function() {
                root.hostEditRequested(hostMenu.alias)
            } },
            { text: "Transfer files", icon: "swap_vert", action: function() {
                root.transferRequested(hostMenu.alias)
            } },
            { type: "separator" },
            { text: "Delete", icon: "delete", action: function() {
                root.deleteRequested(hostMenu.alias)
            } }
        ]

        function show(alias, x, y) {
            hostMenu.alias = alias
            // Anchor a zero-size item at the click point so the library's own
            // bounds handling still applies.
            menuAnchor.x = x
            menuAnchor.y = y
            hostMenu.open(menuAnchor, 0, 0)
        }
    }

    Item {
        id: menuAnchor
        width: 1
        height: 1
    }
}
