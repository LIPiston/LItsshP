import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core
import QtQuick.Controls as Controls

// Left rail: brand, search, grouped host list, footer actions.
// Part of the window shell, not a panel: no fill of its own (the window clears
// to the shell colour), hover rows are an ink wash, and the selected row is an
// accent wash with a 2px accent bar — Pebrel's single selection voice.
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
    signal keysRequested()

    readonly property var skin: Theme.skin
    readonly property color hairline: skin.hairline
    readonly property color hoverColor: skin.hover
    readonly property color selectedColor: skin.accentSoft

    function focusSearch() {
        searchField.forceActiveFocus()
        searchField.selectAll()
    }

    // ── Brand + window controls ────────────────────────────────────────
    // Doubles as the title bar: the window is frameless, so dragging here
    // moves it (startSystemMove keeps the OS-native snap behaviour).
    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 56

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            onPressed: (mouse) => {
                if (root.window) root.window.beginWindowDrag(mouse)
            }
            onDoubleClicked: if (root.window) root.window.toggleMaximized()
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 9

            // Brand mark: a neutral icon tile, not an accent-filled circle —
            // the accent is reserved for selection and primary actions.
            Rectangle {
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26
                radius: root.skin.radiusControl
                color: root.skin.surfaceWash
                border.width: root.skin.isLight ? 1 : 0
                border.color: root.hairline
                Text {
                    anchors.centerIn: parent
                    text: "terminal"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: root.skin.ink
                }
            }

            ColumnLayout {
                spacing: 0
                Text {
                    text: "LItsshP"
                    font.family: Theme.typography.titleSmall.family
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: root.skin.inkStrong
                }
                Text {
                    text: "tssh · ~/.ssh · "
                          + (App.hosts.length === 1 ? "1 host" : App.hosts.length + " hosts")
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 10
                    color: root.skin.inkFaint
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
    // A filled inset field: on dark themes it is the terminal surface showing
    // through the shell; on light themes it is white on the dimmed shell. Radius
    // and height come from the control ladder (6px / 32px), not a pill.
    Rectangle {
        id: searchBox
        anchors.top: header.bottom
        anchors.topMargin: 10
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        height: root.skin.controlHeight
        radius: root.skin.radiusControl
        color: root.skin.isLight ? "#ffffff" : root.skin.surface
        border.width: 1
        border.color: searchField.activeFocus ? root.skin.accent : root.hairline

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 8
            spacing: 7

            Text {
                text: "search"
                font.family: Theme.iconFont.name
                font.pixelSize: 16
                color: root.skin.inkFaint
            }

            TextInput {
                id: searchField
                Layout.fillWidth: true
                verticalAlignment: TextInput.AlignVCenter
                color: root.skin.ink
                selectionColor: root.skin.accent
                selectedTextColor: root.skin.inkOnAccent
                font.family: Theme.typography.bodyMedium.family
                font.pixelSize: 12
                clip: true
                onTextChanged: root.filter = text

                Text {
                    anchors.fill: parent
                    verticalAlignment: Text.AlignVCenter
                    visible: !searchField.text && !searchField.activeFocus
                    text: "Search hosts"
                    font: searchField.font
                    color: root.skin.inkFaint
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
                font.pixelSize: 14
                color: root.skin.inkFaint
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
    }

    // ── Group chips ────────────────────────────────────────────────────
    // Section captions, not pills: Pebrel keeps the sidebar free of rounded
    // containers, so "All" and each group are small labels separated by a dot.
    Flickable {
        id: groupBar
        anchors.top: searchBox.bottom
        anchors.topMargin: 8
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        height: App.groups.length > 0 ? 22 : 0
        visible: height > 0
        contentWidth: groupRow.width
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.HorizontalFlick

        Row {
            id: groupRow
            spacing: 14
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
        anchors.topMargin: 8
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: footer.top
        anchors.bottomMargin: 6
        clip: true
        spacing: 2
        model: hostModel
        currentIndex: -1
        boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

        delegate: HostRow {
            width: hostList.width - 12
            x: 6
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
        spacing: 8
        visible: hostList.count === 0

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: root.filter.length > 0 ? "search_off" : "dns"
            font.family: Theme.iconFont.name
            font.pixelSize: 30
            color: root.skin.inkFaint
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.filter.length > 0
                  ? "No host matches \u201c" + root.filter + "\u201d"
                  : "No hosts in ~/.ssh/config yet"
            font.family: Theme.typography.bodySmall.family
            font.pixelSize: 11
            color: root.skin.inkDim
        }
        Button {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 4
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
        height: 44
        color: "transparent"

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: root.hairline
        }

        Row {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 2

            FooterButton {
                icon: "add"
                label: "New host"
                onActivated: root.addRequested()
            }
            FooterButton {
                icon: "key"
                label: "Keys"
                onActivated: root.keysRequested()
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
        implicitWidth: fbRow.width + 16
        implicitHeight: 30
        width: implicitWidth
        height: implicitHeight

        Rectangle {
            anchors.fill: parent
            radius: root.skin.radiusControl
            color: fbMouse.containsMouse ? root.hoverColor : "transparent"
        }
        Row {
            id: fbRow
            anchors.centerIn: parent
            spacing: 5
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: fb.icon
                font.family: Theme.iconFont.name
                font.pixelSize: 16
                color: fbMouse.containsMouse ? root.skin.iconHover : root.skin.icon
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: fb.label
                font.family: Theme.typography.labelMedium.family
                font.pixelSize: 11
                color: fbMouse.containsMouse ? root.skin.ink : root.skin.inkDim
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

    // Section caption. Pebrel's sidebar has no chip containers: the active
    // item is simply the brightest ink in the row.
    component GroupChip: Item {
        id: chip
        property string label: ""
        property bool active: false
        signal activated()
        width: chipText.implicitWidth
        height: 22

        Text {
            id: chipText
            anchors.centerIn: parent
            text: chip.label
            font.family: Theme.typography.labelSmall.family
            font.pixelSize: 10
            font.weight: chip.active ? Font.DemiBold : Font.Medium
            font.letterSpacing: 0.4
            color: chip.active ? root.skin.ink
                               : (chipMouse.containsMouse ? root.skin.inkDim : root.skin.inkFaint)
        }
        MouseArea {
            id: chipMouse
            anchors.fill: parent
            anchors.margins: -4
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: chip.activated()
        }
    }

    component HostRow: Item {
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

        height: 46

        // Active row: accent wash plus a 2px accent bar on the left edge.
        // Hover is a neutral ink wash — the two states never look alike.
        Rectangle {
            anchors.fill: parent
            radius: root.skin.radiusControl
            color: row.active ? root.selectedColor
                              : (row.hovered ? root.hoverColor : "transparent")
        }

        Rectangle {
            visible: row.active
            width: 2
            height: 20
            radius: 1
            anchors.left: parent.left
            anchors.leftMargin: 3
            anchors.verticalCenter: parent.verticalCenter
            color: root.skin.accent
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 10
            spacing: 9

            // Glyph tile instead of a colored avatar: neutral by default,
            // accent-tinted only while the session is the selected one.
            Item {
                Layout.preferredWidth: 20
                Layout.preferredHeight: 20
                Text {
                    anchors.centerIn: parent
                    text: "dns"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: row.active ? root.skin.accent
                                      : (row.hovered ? root.skin.iconHover : root.skin.icon)
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                RowLayout {
                    spacing: 5
                    Layout.fillWidth: true
                    Text {
                        text: row.alias
                        font.family: Theme.typography.bodyMedium.family
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        color: row.active ? root.skin.inkStrong : root.skin.ink
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: row.hasPassword
                        text: "key"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 11
                        color: root.skin.inkFaint
                    }
                }

                Text {
                    text: (row.user ? row.user + "@" : "") + row.hostname +
                          (row.port && row.port !== "22" ? ":" + row.port : "")
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 10
                    color: root.skin.inkFaint
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }
            }

            Text {
                visible: row.hovered
                text: "more_vert"
                font.family: Theme.iconFont.name
                font.pixelSize: 16
                color: root.skin.icon
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
