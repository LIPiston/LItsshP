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
            fieldStartup.text = ""
            passwordSource = ""
            passwordHint = ""
            rawArea.text = ""
            ownForwards = []
            inheritedForwards = []
            forwardsDisabled = false
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
        fieldStartup.text = h.startupCommand || ""
        passwordSource = h.passwordSource || ""
        passwordHint = passwordHintFor(h)
        rawArea.text = App.hostRawBlock(originalAlias)

        var forwards = App.hostForwards(originalAlias)
        ownForwards = (forwards.own || []).map(function (r) {
            return { kind: r.kind, spec: r.spec }
        })
        inheritedForwards = forwards.inherited || []
        forwardsDisabled = forwards.disabled === true
    }

    property string passwordHint: ""
    // How the stored password is written (encrypted | plain | command | "").
    // Saving keeps the same form: converting on every save would rewrite the
    // file, and a PasswordCommand has no plain value to round-trip.
    property string passwordSource: ""

    function passwordHintFor(h) {
        if (!h || !h.hasPassword) return ""
        if (h.passwordSource === "plain") return "Stored as plain #!! Password"
        if (h.passwordSource === "command") return "Password comes from #!! PasswordCommand"
        return "Password stored (tssh encPassword)"
    }

    // Forwarding rules, split by where they came from: `own` is what this
    // form writes back, `inherited` is shown read-only because it belongs to
    // a Host * or Include block shared with other hosts.
    property var ownForwards: []
    property var inheritedForwards: []
    property bool forwardsDisabled: false

    function addForward() {
        var list = ownForwards.slice()
        list.push({ kind: "L", spec: "" })
        ownForwards = list
    }

    function removeForward(index) {
        var list = ownForwards.slice()
        list.splice(index, 1)
        ownForwards = list
    }

    function setForwardKind(index, kind) {
        var list = ownForwards.slice()
        list[index] = { kind: kind, spec: list[index].spec }
        ownForwards = list
    }

    // Mutated in place on purpose: reassigning the array would rebuild the
    // Repeater and yank the caret out of the field being typed into. `submit`
    // reads the array, so the in-place edit is what gets saved.
    function setForwardSpec(index, spec) {
        if (index < 0 || index >= ownForwards.length)
            return
        ownForwards[index].spec = spec
    }

    function forwardHint(kind, spec) {
        if (!String(spec || "").trim())
            return ""
        var parsed = App.forwardPreview(kind, spec)
        return parsed.valid ? parsed.label : parsed.error
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
        width: Math.min(520, root.width - 60)
        height: root.height
        x: root.width - (scrim.visible ? sheet.width : 0)
        color: Theme.skin.panel
        border.width: 0

        Rectangle {
            anchors.left: parent.left
            width: 1
            height: parent.height
            color: Theme.skin.hairline
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
                            color: Theme.skin.ink
                        }
                        Text {
                            text: root.isNew ? "Added to ~/.ssh/config" : "Editing in ~/.ssh/config"
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 11
                            color: Theme.skin.inkDim
                        }
                    }

                    Item { Layout.fillWidth: true }

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
                                labelBackgroundColor: Theme.skin.panel
                            }
                            TextField {
                                id: fieldPort
                                Layout.preferredWidth: 110
                                label: "Port"
                                placeholderText: "22"
                                type: "outlined"
                                labelBackgroundColor: Theme.skin.panel
                            }
                        }

                        TextField {
                            id: fieldHost
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            label: "Hostname"
                            placeholderText: "example.com or 10.0.0.5"
                            type: "outlined"
                            labelBackgroundColor: Theme.skin.panel
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
                                labelBackgroundColor: Theme.skin.panel
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
                                labelBackgroundColor: Theme.skin.panel
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
                            labelBackgroundColor: Theme.skin.panel
                        }

                        TextField {
                            id: fieldPassword
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            label: "Password"
                            placeholderText: root.passwordSource === "plain"
                                             ? "stored as plain #!! Password"
                                             : "stored as tssh encPassword"
                            supportingText: root.passwordHint
                            leadingIcon: "password"
                            isPassword: true
                            readOnly: root.passwordSource === "command"
                            type: "outlined"
                            labelBackgroundColor: Theme.skin.panel
                        }

                        TextField {
                            id: fieldStartup
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            label: "Startup command"
                            placeholderText: "optional, run after login"
                            supportingText: "LItsshP #!! StartupCommand — typed once the shell is ready"
                            leadingIcon: "play_arrow"
                            type: "outlined"
                            labelBackgroundColor: Theme.skin.panel
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            radius: Theme.skin.radiusOverlay
                            color: Qt.rgba(Theme.skin.info.r, Theme.skin.info.g,
                                           Theme.skin.info.b, 0.10)
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 8
                                Text {
                                    text: "info"
                                    font.family: Theme.iconFont.name
                                    font.pixelSize: 16
                                    color: Theme.skin.info
                                }
                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    text: "Passwords use tssh's encoding. It is obfuscation, not encryption — keep the file private."
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 10
                                    color: Theme.skin.inkDim
                                }
                            }
                        }

                        // Advanced
                        Text {
                            Layout.topMargin: 6
                            text: "Advanced"
                            font.family: Theme.typography.labelLarge.family
                            font.pixelSize: 12
                            color: Theme.skin.inkDim
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
                                labelBackgroundColor: Theme.skin.panel
                            }
                            TextField {
                                id: fieldCommand
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                label: "ProxyCommand"
                                placeholderText: "ssh -W %h:%p proxy"
                                type: "outlined"
                                labelBackgroundColor: Theme.skin.panel
                            }
                        }

                        // Port forwarding
                        Text {
                            Layout.topMargin: 6
                            text: "Port forwarding"
                            font.family: Theme.typography.labelLarge.family
                            font.pixelSize: 12
                            color: Theme.skin.inkDim
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: root.ownForwards.length === 0
                            wrapMode: Text.Wrap
                            text: "No rules of this host's own. Forwarding is only active while a session is open."
                            font.family: Theme.typography.bodySmall.family
                            font.pixelSize: 11
                            color: Theme.skin.inkDim
                            opacity: 0.8
                        }

                        Repeater {
                            model: root.ownForwards

                            delegate: ColumnLayout {
                                id: forwardRow

                                required property var modelData
                                required property int index

                                // Local copy so typing does not depend on the
                                // model object being re-bound per keystroke.
                                property string specText: modelData.spec

                                Layout.fillWidth: true
                                spacing: 2

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    ComboBox {
                                        Layout.preferredWidth: 104
                                        model: ["Local", "Remote", "Dynamic"]
                                        currentIndex: forwardRow.modelData.kind === "R" ? 1
                                                      : (forwardRow.modelData.kind === "D" ? 2 : 0)
                                        type: "outlined"
                                        onActivated: (i) => {
                                            root.setForwardKind(forwardRow.index,
                                                i === 1 ? "R" : (i === 2 ? "D" : "L"))
                                        }
                                    }

                                    TextField {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: forwardRow.specText
                                        type: "outlined"
                                        labelBackgroundColor: Theme.skin.panel
                                        placeholderText: forwardRow.modelData.kind === "D"
                                                         ? "1080" : "8080:localhost:80"
                                        onTextChanged: {
                                            forwardRow.specText = text
                                            root.setForwardSpec(forwardRow.index, text)
                                        }
                                    }

                                    Item {
                                        Layout.preferredWidth: 28
                                        Layout.preferredHeight: 28
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: Theme.skin.radiusControl
                                            color: removeHover.containsMouse
                                                   ? Qt.rgba(Theme.skin.danger.r,
                                                             Theme.skin.danger.g,
                                                             Theme.skin.danger.b, 0.12)
                                                   : "transparent"
                                        }
                                        Text {
                                            anchors.centerIn: parent
                                            text: "close"
                                            font.family: Theme.iconFont.name
                                            font.pixelSize: 15
                                            color: Theme.skin.danger
                                        }
                                        MouseArea {
                                            id: removeHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.removeForward(forwardRow.index)
                                        }
                                    }
                                }

                                Text {
                                    Layout.leftMargin: 112
                                    Layout.fillWidth: true
                                    visible: forwardRow.specText !== ""
                                    wrapMode: Text.Wrap
                                    text: root.forwardHint(forwardRow.modelData.kind,
                                                           forwardRow.specText)
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 10
                                    color: App.forwardPreview(forwardRow.modelData.kind,
                                                              forwardRow.specText).valid
                                           ? Theme.skin.inkDim
                                           : Theme.skin.danger
                                }
                            }
                        }

                        Button {
                            Layout.alignment: Qt.AlignLeft
                            text: "Add rule"
                            icon: "add"
                            type: "text"
                            onClicked: root.addForward()
                        }

                        // Inherited rules: visible, not editable from here.
                        Repeater {
                            model: root.inheritedForwards

                            delegate: RowLayout {
                                required property var modelData

                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: modelData.kind === "R" ? "Remote"
                                          : (modelData.kind === "D" ? "Dynamic" : "Local")
                                    Layout.preferredWidth: 104
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 10
                                    color: Theme.skin.inkDim
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.spec
                                    elide: Text.ElideMiddle
                                    font.family: Theme.typography.bodySmall.family
                                    font.pixelSize: 11
                                    color: Theme.skin.inkDim
                                }
                                Text {
                                    text: modelData.source || ""
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 9
                                    color: Theme.skin.inkDim
                                    opacity: 0.7
                                }
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: root.forwardsDisabled
                            wrapMode: Text.Wrap
                            text: "ClearAllForwardings is set for this host, so none of these rules is applied."
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 10
                            color: Theme.skin.info
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: root.originalAlias !== "" && root.ownForwards.length > 0
                            wrapMode: Text.WrapAnywhere
                            text: App.tunnelCommand(root.originalAlias)
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 9
                            color: Theme.skin.inkDim
                            opacity: 0.6
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
                        color: Theme.skin.ink
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Edit the exact lines written to ~/.ssh/config. Must start with a Host line."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: Theme.skin.inkDim
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: Theme.skin.radiusOverlay
                        color: Theme.skin.surface
                        border.width: 1
                        border.color: Theme.skin.hairline

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
                                color: Theme.skin.ink
                                selectionColor: Theme.skin.accent
                                selectedTextColor: Theme.skin.inkOnAccent
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
                                color: Theme.skin.hairline
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
                color: root.statusError ? Qt.rgba(Theme.skin.danger.r, Theme.skin.danger.g,
                                                   Theme.skin.danger.b, 0.12)
                                        : Qt.rgba(Theme.skin.accent.r, Theme.skin.accent.g,
                                                  Theme.skin.accent.b, 0.10)
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 24
                    anchors.rightMargin: 24
                    spacing: 8
                    Text {
                        text: root.statusError ? "error" : "check_circle"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 16
                        color: root.statusError ? Theme.skin.danger : Theme.skin.accent
                    }
                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: root.statusError || root.statusOk
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: root.statusError ? Theme.skin.danger : Theme.skin.ink
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
                    color: Theme.skin.hairline
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
            "proxyCommand": fieldCommand.text.trim(),
            // Always sent so clearing the field removes the option.
            "startup_command": fieldStartup.text.trim(),
            "forwards": root.ownForwards.filter(function (r) {
                return String(r.spec || "").trim() !== ""
            })
        }
        if (root.isNew || fieldPassword.text !== App.hostPassword(root.originalAlias)) {
            fields.password = fieldPassword.text
            fields.password_source = root.passwordSource
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
