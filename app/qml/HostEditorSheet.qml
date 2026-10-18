import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core
import QtQuick.Controls as Controls

// Flat right-hand sheet for creating/editing a host. Writes straight into
// ~/.ssh/config via App.saveHost, so tssh sees the change immediately.
Item {
    id: root
    property var window
    property string editingAlias: ""
    property string originalAlias: ""
    property string statusError: ""
    property string statusOk: ""
    property string mode: "form"    // form | raw

    readonly property bool isNew: originalAlias === ""

    function open(alias) {
        originalAlias = alias || ""
        editingAlias = alias || ""
        statusError = ""
        statusOk = ""
        mode = "form"
        loadForm()
        scrim.visible = true
        scrim.opacity = 0.4
        Qt.callLater(function() { fieldAlias.forceActiveFocus() })    }

    function close() {
        scrim.visible = false
    }

    function loadForm() {
        if (originalAlias === "") {
            fieldAlias.text = ""
            fieldHost.text = ""
            fieldPort.text = "22"
            fieldUser.text = ""
            fieldIdentity.text = ""
            fieldGroups.text = ""
            fieldJump.text = ""
            fieldCommand.text = ""
            fieldPassword.text = ""
            passwordHint = ""
            rawArea.text = ""
            return
        }
        var h = App.host(originalAlias)
        fieldAlias.text = h.alias || ""
        fieldHost.text = h.hostname || ""
        fieldPort.text = h.port || "22"
        fieldUser.text = h.user || ""
        fieldIdentity.text = h.identityFile || ""
        fieldGroups.text = (h.groups || []).join(" ")
        fieldJump.text = h.proxyJump || ""
        fieldCommand.text = h.proxyCommand || ""
        fieldPassword.text = App.hostPassword(originalAlias)
        passwordHint = h.hasPassword ? "Password stored (tssh encPassword)" : ""
        rawArea.text = App.hostRawBlock(originalAlias)
    }

    property string passwordHint: ""

    // ── Scrim ──────────────────────────────────────────────────────────
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: "#000000"
        opacity: 0
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
        width: Math.min(520, root.width - 60)
        height: root.height
        x: root.width - (scrim.visible ? sheet.width : 0)
        color: Theme.color.surfaceContainerLow
        border.width: 0

        Rectangle {
            anchors.left: parent.left
            width: 1
            height: parent.height
            color: Theme.color.outlineVariant
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 0
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
                            text: root.isNew ? "New host" : root.editingAlias
                            font.family: Theme.typography.titleLarge.family
                            font.pixelSize: 19
                            color: Theme.color.onSurfaceColor
                        }
                        Text {
                            text: root.isNew ? "Added to ~/.ssh/config" : "Editing in ~/.ssh/config"
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 11
                            color: Theme.color.onSurfaceVariantColor
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Item {
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: closeHover.containsMouse ? root.window.flatHover : "transparent"
                        }
                        Text {
                            anchors.centerIn: parent
                            text: "close"
                            font.family: Theme.iconFont.name
                            font.pixelSize: 17
                            color: Theme.color.onSurfaceVariantColor
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
                    color: Theme.color.outlineVariant
                }
            }

            // Mode switch + body
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                // ── Form ─────────────────────────────────────────────────
                Flickable {
                    id: formFlick
                    anchors.fill: parent
                    visible: root.mode === "form"
                    contentHeight: formColumn.height + 32
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

                    ColumnLayout {
                        id: formColumn
                        x: 24
                        y: 20
                        width: parent.width - 48
                        spacing: 14

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            TextField {
                                id: fieldAlias
                                Layout.fillWidth: true
                                Layout.preferredWidth: formColumn.width - 122
                                Layout.minimumWidth: 120
                                label: "Alias"
                                placeholderText: "prod-web"
                                type: "outlined"
                                labelBackgroundColor: Theme.color.surfaceContainerLow
                            }
                            TextField {
                                id: fieldPort
                                Layout.preferredWidth: 110
                                label: "Port"
                                placeholderText: "22"
                                type: "outlined"
                                labelBackgroundColor: Theme.color.surfaceContainerLow
                            }
                        }

                        TextField {
                            id: fieldHost
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            label: "Hostname"
                            placeholderText: "example.com or 10.0.0.5"
                            type: "outlined"
                            labelBackgroundColor: Theme.color.surfaceContainerLow
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            TextField {
                                id: fieldUser
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.alignment: Qt.AlignTop
                                label: "User"
                                placeholderText: "root"
                                type: "outlined"
                                labelBackgroundColor: Theme.color.surfaceContainerLow
                            }
                            TextField {
                                id: fieldGroups
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.alignment: Qt.AlignTop
                                label: "Groups"
                                placeholderText: "prod web"
                                supportingText: "tssh #!! GroupLabels"
                                type: "outlined"
                                labelBackgroundColor: Theme.color.surfaceContainerLow
                            }
                        }

                        TextField {
                            id: fieldIdentity
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            label: "Identity file"
                            placeholderText: "~/.ssh/id_ed25519"
                            leadingIcon: "key"
                            type: "outlined"
                            labelBackgroundColor: Theme.color.surfaceContainerLow
                        }

                        TextField {
                            id: fieldPassword
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            label: "Password"
                            placeholderText: "stored as tssh encPassword"
                            supportingText: root.passwordHint
                            leadingIcon: "password"
                            isPassword: true
                            type: "outlined"
                            labelBackgroundColor: Theme.color.surfaceContainerLow
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            radius: 8
                            color: Qt.rgba(Theme.color.tertiary.r, Theme.color.tertiary.g,
                                           Theme.color.tertiary.b, 0.10)
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 8
                                Text {
                                    text: "info"
                                    font.family: Theme.iconFont.name
                                    font.pixelSize: 16
                                    color: Theme.color.tertiary
                                }
                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    text: "Passwords use tssh's encoding. It is obfuscation, not encryption — keep the file private."
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 10
                                    color: Theme.color.onSurfaceVariantColor
                                }
                            }
                        }

                        // Advanced
                        Text {
                            Layout.topMargin: 6
                            text: "Advanced"
                            font.family: Theme.typography.labelLarge.family
                            font.pixelSize: 12
                            color: Theme.color.onSurfaceVariantColor
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            TextField {
                                id: fieldJump
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                label: "ProxyJump"
                                placeholderText: "bastion"
                                type: "outlined"
                                labelBackgroundColor: Theme.color.surfaceContainerLow
                            }
                            TextField {
                                id: fieldCommand
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                label: "ProxyCommand"
                                placeholderText: "ssh -W %h:%p proxy"
                                type: "outlined"
                                labelBackgroundColor: Theme.color.surfaceContainerLow
                            }
                        }

                        Button {
                            Layout.alignment: Qt.AlignLeft
                            Layout.topMargin: 4
                            text: "Edit raw block"
                            icon: "code"
                            type: "text"
                            visible: !root.isNew
                            onClicked: {
                                rawArea.text = App.hostRawBlock(root.originalAlias)
                                root.mode = "raw"
                            }
                        }

                        Item { Layout.fillWidth: true }
                        Item { Layout.preferredHeight: 8 }
                    }
                }

                // ── Raw block editor ──────────────────────────────────────
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    visible: root.mode === "raw"
                    spacing: 12

                    Text {
                        text: "Raw block"
                        font.family: Theme.typography.titleMedium.family
                        font.pixelSize: 15
                        color: Theme.color.onSurfaceColor
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Edit the exact lines written to ~/.ssh/config. Must start with a Host line."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: Theme.color.onSurfaceVariantColor
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 10
                        color: Theme.color.surfaceContainerLowest
                        border.width: 1
                        border.color: Theme.color.outlineVariant

                        // A plain TextEdit inside a clipping Item, with the
                        // scroll offset applied to `y` by hand. The Flickable
                        // version is the obvious layout, but it showed no text
                        // in the running app; a minimal Flickable + TextEdit
                        // case does render, so the trigger was never isolated.
                        // A clipped TextEdit renders reliably, so that is the
                        // shape kept here and in the command composer.
                        Item {
                            id: rawViewport
                            anchors.fill: parent
                            anchors.margins: 7
                            clip: true

                            property real scrollOffset: 0
                            property real contentHeight: rawArea.implicitHeight + 12
                            readonly property real maxOffset: Math.max(0, contentHeight - height)

                            function scrollBy(delta) {
                                var next = Math.max(0, Math.min(maxOffset, scrollOffset + delta))
                                scrollOffset = next
                            }

                            TextEdit {
                                id: rawArea
                                x: 6
                                y: 6 - rawViewport.scrollOffset
                                width: rawViewport.width - 12
                                font.family: "Cascadia Mono"
                                font.pixelSize: 12
                                color: Theme.color.onSurfaceColor
                                selectionColor: Theme.color.primary
                                selectedTextColor: Theme.color.onPrimaryColor
                                selectByMouse: true
                                wrapMode: TextEdit.NoWrap

                                onCursorPositionChanged: {
                                    var caret = cursorRectangle
                                    var top = rawViewport.scrollOffset
                                    var bottom = top + rawViewport.height
                                    if (caret.y < top)
                                        rawViewport.scrollOffset = Math.max(0, caret.y - 4)
                                    else if (caret.y + caret.height > bottom)
                                        rawViewport.scrollOffset =
                                            Math.min(rawViewport.maxOffset,
                                                     caret.y + caret.height - rawViewport.height + 4)
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.NoButton
                                onWheel: (e) => {
                                    rawViewport.scrollBy(-e.angleDelta.y / 3)
                                }
                            }

                            // Thin scroll indicator, sized from the ratio so it
                            // stays proportional without an attached ScrollBar.
                            Rectangle {
                                visible: rawViewport.maxOffset > 0
                                x: rawViewport.width - 4
                                width: 3
                                radius: 2
                                color: Theme.color.outline
                                opacity: 0.5
                                readonly property real ratio:
                                    rawViewport.height / Math.max(rawViewport.height,
                                                                  rawViewport.contentHeight)
                                height: Math.max(24, rawViewport.height * ratio)
                                y: (rawViewport.height - height)
                                   * (rawViewport.maxOffset > 0
                                      ? rawViewport.scrollOffset / rawViewport.maxOffset : 0)
                            }
                        }
                    }

                    Button {
                        Layout.alignment: Qt.AlignLeft
                        text: "Back to form"
                        type: "text"
                        icon: "arrow_back"
                        onClicked: {
                            root.mode = "form"
                            root.loadForm()
                        }
                    }
                }
            }

            // Error / success strip
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: (root.statusError || root.statusOk) ? 40 : 0
                visible: height > 0
                color: root.statusError ? Qt.rgba(Theme.color.error.r, Theme.color.error.g,
                                                   Theme.color.error.b, 0.12)
                                        : Qt.rgba(Theme.color.primary.r, Theme.color.primary.g,
                                                  Theme.color.primary.b, 0.10)
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 24
                    anchors.rightMargin: 24
                    spacing: 8
                    Text {
                        text: root.statusError ? "error" : "check_circle"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 16
                        color: root.statusError ? Theme.color.error : Theme.color.primary
                    }
                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: root.statusError || root.statusOk
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: root.statusError ? Theme.color.error : Theme.color.onSurfaceColor
                    }
                }
            }

            // Footer actions
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: "transparent"

                Rectangle {
                    anchors.top: parent.top
                    width: parent.width
                    height: 1
                    color: Theme.color.outlineVariant
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 24
                    anchors.rightMargin: 24
                    spacing: 8

                    Button {
                        visible: !root.isNew && root.mode === "form"
                        text: "Delete"
                        type: "text"
                        onClicked: deleteDialog.open()
                    }
                    Button {
                        visible: !root.isNew && root.mode === "form"
                        text: "Duplicate"
                        type: "text"
                        onClicked: {
                            var res = App.duplicateHost(root.originalAlias)
                            if (res.ok) {
                                root.statusOk = "Duplicated as " + res.alias
                                App.refreshHosts()
                            } else {
                                root.statusError = res.error
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Cancel"
                        type: "text"
                        onClicked: root.close()
                    }
                    Button {
                        text: root.isNew ? "Create" : "Save"
                        icon: "check"
                        onClicked: root.submit()
                    }
                }
            }
        }

        // Position comes from the `x` binding: a visible scrim keeps the sheet
        // on-screen, a hidden one parks it off the right edge.
    }

    function submit() {
        root.statusError = ""
        root.statusOk = ""

        if (root.mode === "raw") {
            var raw = App.saveRawBlock(root.originalAlias, rawArea.text)
            if (!raw.ok) {
                root.statusError = raw.error
                return
            }
            App.refreshHosts()
            root.statusOk = "Saved"
            closeTimer.restart()
            return
        }

        var fields = {
            "originalAlias": root.originalAlias,
            "alias": fieldAlias.text.trim(),
            "hostname": fieldHost.text.trim(),
            "port": fieldPort.text.trim(),
            "user": fieldUser.text.trim(),
            "identityFile": fieldIdentity.text.trim(),
            "groups": fieldGroups.text.trim(),
            "proxyJump": fieldJump.text.trim(),
            "proxyCommand": fieldCommand.text.trim()
        }
        if (root.isNew || fieldPassword.text !== App.hostPassword(root.originalAlias)) {
            fields.password = fieldPassword.text
        }
        if (!fields.alias) {
            root.statusError = "Alias is required"
            return
        }

        var result = App.saveHost(fields)
        if (!result.ok) {
            root.statusError = result.error
            return
        }

        App.refreshHosts()
        root.originalAlias = result.alias
        root.editingAlias = result.alias
        root.statusOk = root.isNew ? "Created " + result.alias : "Saved"
        closeTimer.restart()
    }

    Timer {
        id: closeTimer
        interval: 650
        onTriggered: root.close()
    }

    Dialog {
        id: deleteDialog
        title: "Delete host?"
        text: "This removes the \"" + root.originalAlias + "\" block from ~/.ssh/config."
        acceptText: "Delete"
        rejectText: "Cancel"
        icon: "delete"
        onAccepted: {
            var res = App.deleteHost(root.originalAlias)
            if (res.ok) {
                App.refreshHosts()
                root.close()
            } else {
                root.statusError = res.error
            }
        }
    }
}
