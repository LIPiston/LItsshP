import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core
import QtQuick.Controls as Controls

// Key manager: identities in ~/.ssh, their public halves, and known_hosts.
// Everything writes through the OpenSSH tools, so the files stay exactly what
// ssh expects; the UI only decides what to show and what to confirm.
Item {
    id: root
    property var window

    readonly property var c: Theme.color

    property var keys: []
    property var hosts: []
    property string statusError: ""
    property string statusOk: ""
    property string query: ""
    property string mode: "keys"        // keys | known

    property bool generateVisible: false
    property string newName: "id_ed25519"
    property string newComment: ""
    property string newPassphrase: ""
    property string newType: "ed25519"
    property string generatedPublic: ""

    property bool pushVisible: false
    property string pushAlias: ""
    property string pushKeyText: ""

    property string forgetHost: ""
    property int forgetLine: 0

    property bool scanVisible: false
    property string scanHostName: ""
    property var scanResults: []
    property bool scanBusy: false

    function open() {
        scrim.visible = true
        statusError = ""
        statusOk = ""
        mode = "keys"
        reload()
    }

    function close() {
        scrim.visible = false
    }

    function reload() {
        keys = App.sshKeys()
        hosts = App.knownHosts()
    }

    function copy(text) {
        clipHelper.text = text
        clipHelper.selectAll()
        clipHelper.copy()
        statusOk = "Copied to the clipboard"
        statusError = ""
        Qt.callLater(function () { clipHelper.deselect() })
    }

    function beginGenerate() {
        newName = "id_ed25519"
        newComment = ""
        newPassphrase = ""
        newType = "ed25519"
        generatedPublic = ""
        statusError = ""
        statusOk = ""
        generateVisible = true
    }

    function submitGenerate() {
        statusError = ""
        var path = App.keyPathFor(newName)
        var result = App.generateKey(path, newComment, newPassphrase, newType, 0)
        if (!result.ok) {
            statusError = result.error
            return
        }
        generatedPublic = result.publicKey || ""
        statusOk = "Created " + newName + " — push it to a host below."
        reload()
    }

    function beginPush(keyText) {
        pushKeyText = keyText || ""
        pushAlias = ""
        pushVisible = true
    }

    function submitPush() {
        if (!pushAlias) {
            statusError = "Choose a host"
            return
        }
        var result = App.pushKey(pushAlias, pushKeyText)
        pushVisible = false
        if (result.ok) {
            statusOk = "Installing the key on " + pushAlias + " in its session…"
            statusError = ""
        } else {
            statusError = result.error
        }
    }

    function confirmForget(host, line) {
        forgetHost = host
        forgetLine = line || 0
        forgetDialog.open()
    }

    function beginScan() {
        scanHostName = ""
        scanResults = []
        scanBusy = false
        statusError = ""
        statusOk = ""
        scanVisible = true
    }

    function submitScan() {
        var target = scanHostName.trim()
        if (!target) {
            statusError = "Enter a host name or address"
            return
        }
        scanBusy = true
        statusError = ""
        scanResults = []
        // The scan runs in the background; onHostScanFinished fills the list.
        App.scanHost(target, 22)
    }

    Connections {
        target: App
        function onHostScanFinished(result) {
            root.scanBusy = false
            if (!root.scanVisible) return
            if (!result.ok) {
                root.statusError = result.error
                return
            }
            root.scanResults = result.entries || []
        }
    }

    function trustScanned() {
        var lines = []
        for (var i = 0; i < scanResults.length; i++) lines.push(scanResults[i].raw)
        var result = App.trustHost(lines)
        scanVisible = false
        if (result.ok) {
            statusOk = "Added " + result.added + " key(s)"
            statusError = ""
            reload()
        } else {
            statusError = result.error
        }
    }

    function filteredKeys() {
        var needle = query.trim().toLowerCase()
        if (needle === "") return keys
        var out = []
        for (var i = 0; i < keys.length; i++) {
            var k = keys[i]
            var hay = (k.name + " " + k.type + " " + k.fingerprint + " " + k.comment
                       + " " + (k.referencedBy || "")).toLowerCase()
            if (hay.indexOf(needle) >= 0) out.push(k)
        }
        return out
    }

    function filteredHosts() {
        var needle = query.trim().toLowerCase()
        if (needle === "") return hosts
        var out = []
        for (var i = 0; i < hosts.length; i++) {
            var h = hosts[i]
            var hay = (h.displayHost + " " + h.hosts + " " + h.type + " "
                       + h.fingerprint).toLowerCase()
            if (hay.indexOf(needle) >= 0) out.push(h)
        }
        return out
    }

    TextEdit { id: clipHelper; visible: false }

    // ── Scrim ──────────────────────────────────────────────────────────
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: "#000000"
        opacity: 0.42
        visible: false
        z: 1300
        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    // ── Dialog panel ───────────────────────────────────────────────────
    Rectangle {
        id: panel
        z: 1301
        visible: scrim.visible
        width: Math.min(720, root.width - 80)
        height: Math.min(620, root.height - 70)
        anchors.centerIn: parent
        radius: 14
        color: Theme.color.surfaceContainerLow
        border.width: 1
        border.color: Theme.color.outlineVariant

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // Header
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 58

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 22
                    anchors.rightMargin: 12
                    spacing: 10

                    Text {
                        text: "Keys"
                        font.family: Theme.typography.titleLarge.family
                        font.pixelSize: 18
                        color: Theme.color.onSurfaceColor
                    }

                    Rectangle {
                        Layout.preferredWidth: segRow.width + 8
                        Layout.preferredHeight: 30
                        radius: 15
                        color: Theme.color.surfaceContainerHigh
                        Row {
                            id: segRow
                            anchors.centerIn: parent
                            Repeater {
                                model: [{ t: "Identities", m: "keys" },
                                        { t: "Known hosts", m: "known" }]
                                delegate: Rectangle {
                                    required property var modelData
                                    width: tabLabel.implicitWidth + 24
                                    height: 26
                                    radius: 13
                                    color: root.mode === modelData.m ? Theme.color.primaryContainer
                                                                    : "transparent"
                                    Text {
                                        id: tabLabel
                                        anchors.centerIn: parent
                                        text: modelData.t
                                        font.family: Theme.typography.labelMedium.family
                                        font.pixelSize: 11
                                        color: root.mode === modelData.m
                                               ? Theme.color.onPrimaryContainerColor
                                               : Theme.color.onSurfaceVariantColor
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.mode = modelData.m
                                    }
                                }
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        visible: root.mode === "keys"
                        text: "New key"
                        icon: "add"
                        onClicked: root.beginGenerate()
                    }

                    Button {
                        visible: root.mode === "known"
                        text: "Trust a host"
                        icon: "travel_explore"
                        onClicked: root.beginScan()
                    }

                    Item {
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
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

            // Filter + status
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 46

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    spacing: 10

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        radius: 8
                        color: Theme.color.surfaceContainerHigh
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 9
                            anchors.rightMargin: 9
                            spacing: 7
                            Text {
                                text: "filter_alt"
                                font.family: Theme.iconFont.name
                                font.pixelSize: 15
                                color: Theme.color.onSurfaceVariantColor
                            }
                            TextInput {
                                Layout.fillWidth: true
                                verticalAlignment: TextInput.AlignVCenter
                                font.family: Theme.typography.bodyMedium.family
                                font.pixelSize: 12
                                color: Theme.color.onSurfaceColor
                                selectionColor: Theme.color.primary
                                selectedTextColor: Theme.color.onPrimaryColor
                                clip: true
                                onTextChanged: root.query = text
                                Text {
                                    anchors.fill: parent
                                    verticalAlignment: Text.AlignVCenter
                                    visible: !parent.text
                                    text: "Filter by name, fingerprint or comment"
                                    font: parent.font
                                    color: Theme.color.onSurfaceVariantColor
                                    opacity: 0.6
                                }
                            }
                        }
                    }
                    Button {
                        text: "Refresh"
                        type: "text"
                        icon: "refresh"
                        onClicked: root.reload()
                    }
                }
            }

            // Status line
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: (root.statusError || root.statusOk) ? 34 : 0
                visible: height > 0
                color: root.statusError
                       ? Qt.rgba(Theme.color.error.r, Theme.color.error.g, Theme.color.error.b, 0.12)
                       : Qt.rgba(Theme.color.primary.r, Theme.color.primary.g, Theme.color.primary.b, 0.10)
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    spacing: 8
                    Text {
                        text: root.statusError ? "error" : "check_circle"
                        font.family: Theme.iconFont.name
                        font.pixelSize: 15
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

            // ── Identities ─────────────────────────────────────────────
            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: root.mode === "keys"
                contentHeight: keyColumn.height + 24
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

                ColumnLayout {
                    id: keyColumn
                    x: 20
                    y: 8
                    width: panel.width - 40
                    spacing: 8

                    Text {
                        Layout.fillWidth: true
                        visible: root.filteredKeys().length === 0
                        wrapMode: Text.Wrap
                        text: root.keys.length === 0
                              ? "No keys in ~/.ssh yet. Create one, then install its public half on a host."
                              : "No key matches the filter."
                        font.family: Theme.typography.bodyMedium.family
                        font.pixelSize: 12
                        color: Theme.color.onSurfaceVariantColor
                    }

                    Repeater {
                        model: root.filteredKeys()

                        delegate: Rectangle {
                            id: keyCard
                            required property var modelData

                            Layout.fillWidth: true
                            Layout.preferredHeight: keyBody.height + 22
                            radius: 10
                            color: Theme.color.surfaceContainer

                            ColumnLayout {
                                id: keyBody
                                x: 14
                                y: 12
                                width: keyCard.width - 28
                                spacing: 5

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: "key"
                                        font.family: Theme.iconFont.name
                                        font.pixelSize: 16
                                        color: keyCard.modelData.private
                                               ? Theme.color.primary : Theme.color.error
                                    }
                                    Text {
                                        text: keyCard.modelData.name
                                        font.family: Theme.typography.titleSmall.family
                                        font.pixelSize: 13
                                        color: Theme.color.onSurfaceColor
                                    }
                                    Text {
                                        text: keyCard.modelData.type +
                                              (keyCard.modelData.bits > 0
                                               ? " " + keyCard.modelData.bits + "-bit" : "")
                                        font.family: Theme.typography.labelSmall.family
                                        font.pixelSize: 10
                                        color: Theme.color.onSurfaceVariantColor
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        visible: !!keyCard.modelData.referencedBy
                                        text: "used by " + (keyCard.modelData.referencedBy || "")
                                        font.family: Theme.typography.labelSmall.family
                                        font.pixelSize: 10
                                        color: Theme.color.onSurfaceVariantColor
                                        opacity: 0.8
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: keyCard.modelData.fingerprint || "no public half"
                                    elide: Text.ElideMiddle
                                    font.family: "Cascadia Mono"
                                    font.pixelSize: 10
                                    color: keyCard.modelData.fingerprint
                                           ? Theme.color.onSurfaceVariantColor : Theme.color.error
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 4

                                    Button {
                                        text: "Copy public"
                                        type: "text"
                                        enabled: !!keyCard.modelData.publicKey
                                        onClicked: root.copy(keyCard.modelData.publicKey)
                                    }
                                    Button {
                                        text: "Install on host"
                                        type: "text"
                                        enabled: !!keyCard.modelData.publicKey
                                        onClicked: root.beginPush(keyCard.modelData.publicKey)
                                    }
                                    Item { Layout.fillWidth: true }
                                    Button {
                                        text: "Delete"
                                        type: "text"
                                        onClicked: {
                                            var res = App.deleteKey(keyCard.modelData.path)
                                            if (res.ok) {
                                                root.statusOk = "Deleted " + keyCard.modelData.name
                                                root.statusError = ""
                                                root.reload()
                                            } else {
                                                root.statusError = res.error
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        wrapMode: Text.Wrap
                        text: "A key stored outside ~/.ssh is listed with the host that references it. "
                              + "Deleting removes both halves; ssh then falls back to the next identity."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: Theme.color.onSurfaceVariantColor
                        opacity: 0.8
                    }
                }
            }

            // ── Known hosts ────────────────────────────────────────────
            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: root.mode === "known"
                contentHeight: knownColumn.height + 24
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

                ColumnLayout {
                    id: knownColumn
                    x: 20
                    y: 8
                    width: panel.width - 40
                    spacing: 6

                    Text {
                        Layout.fillWidth: true
                        visible: root.filteredHosts().length === 0
                        wrapMode: Text.Wrap
                        text: "No trusted host keys yet. Use \"Trust a host\" to scan one, or "
                              + "connect once and accept its fingerprint."
                        font.family: Theme.typography.bodyMedium.family
                        font.pixelSize: 12
                        color: Theme.color.onSurfaceVariantColor
                    }

                    Repeater {
                        model: root.filteredHosts()

                        delegate: Rectangle {
                            id: hostRow
                            required property var modelData

                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            radius: 8
                            color: Theme.color.surfaceContainer

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 8
                                spacing: 10

                                Text {
                                    text: hostRow.modelData.displayHost
                                    Layout.preferredWidth: 180
                                    elide: Text.ElideMiddle
                                    font.family: Theme.typography.bodyMedium.family
                                    font.pixelSize: 12
                                    color: Theme.color.onSurfaceColor
                                }
                                Text {
                                    text: hostRow.modelData.type
                                    Layout.preferredWidth: 60
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 10
                                    color: Theme.color.onSurfaceVariantColor
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: hostRow.modelData.fingerprint
                                    elide: Text.ElideMiddle
                                    font.family: "Cascadia Mono"
                                    font.pixelSize: 10
                                    color: Theme.color.onSurfaceVariantColor
                                }
                                Button {
                                    text: "Forget"
                                    type: "text"
                                    onClicked: root.confirmForget(
                                        hostRow.modelData.hashed ? "" : hostRow.modelData.hosts,
                                        hostRow.modelData.hashed ? hostRow.modelData.line : 0)
                                }
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        wrapMode: Text.Wrap
                        text: "Forgetting a host makes the next connection ask again, which is how "
                              + "you recover after a server legitimately changes its key. A hashed "
                              + "entry keeps its own row per key, so there is nothing to show by name."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: Theme.color.onSurfaceVariantColor
                        opacity: 0.8
                    }
                }
            }
        }
    }

    // ── Generate key ───────────────────────────────────────────────────
    Rectangle {
        id: generateScrim
        anchors.fill: parent
        z: 1310
        visible: root.generateVisible
        color: "#000000"
        opacity: 0.35
        MouseArea {
            anchors.fill: parent
            onClicked: root.generateVisible = false
        }
    }

    Rectangle {
        id: generateCard
        z: 1311
        visible: root.generateVisible
        anchors.centerIn: parent
        width: Math.min(520, root.width - 100)
        height: generateColumn.height + 48
        radius: 16
        color: Theme.color.surfaceContainerHigh
        border.width: 1
        border.color: Theme.color.outlineVariant

        ColumnLayout {
            id: generateColumn
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.topMargin: 22
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            spacing: 12

            Text {
                text: "New key"
                font.family: Theme.typography.titleMedium.family
                font.pixelSize: 15
                color: Theme.color.onSurfaceColor
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                TextField {
                    Layout.fillWidth: true
                    label: "File name"
                    text: root.newName
                    type: "outlined"
                    labelBackgroundColor: Theme.color.surfaceContainerHigh
                    onTextChanged: root.newName = text
                }
                ComboBox {
                    Layout.preferredWidth: 130
                    model: ["ED25519", "RSA 4096"]
                    type: "outlined"
                    onActivated: (i) => root.newType = i === 1 ? "rsa" : "ed25519"
                }
            }

            TextField {
                Layout.fillWidth: true
                label: "Comment"
                placeholderText: "user@laptop (optional)"
                type: "outlined"
                labelBackgroundColor: Theme.color.surfaceContainerHigh
                onTextChanged: root.newComment = text
            }

            TextField {
                Layout.fillWidth: true
                label: "Passphrase"
                placeholderText: "leave empty for no passphrase"
                isPassword: true
                type: "outlined"
                labelBackgroundColor: Theme.color.surfaceContainerHigh
                onTextChanged: root.newPassphrase = text
            }

            Text {
                Layout.fillWidth: true
                visible: root.generatedPublic !== ""
                wrapMode: Text.WrapAnywhere
                text: root.generatedPublic
                font.family: "Cascadia Mono"
                font.pixelSize: 10
                color: Theme.color.onSurfaceVariantColor
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 2
                spacing: 8
                Item { Layout.fillWidth: true }
                Button {
                    text: "Close"
                    type: "text"
                    onClicked: root.generateVisible = false
                }
                Button {
                    text: "Create"
                    icon: "check"
                    onClicked: root.submitGenerate()
                }
            }
        }
    }

    // ── Install on host ────────────────────────────────────────────────
    Rectangle {
        id: pushScrim
        anchors.fill: parent
        z: 1312
        visible: root.pushVisible
        color: "#000000"
        opacity: 0.35
        MouseArea {
            anchors.fill: parent
            onClicked: root.pushVisible = false
        }
    }

    Rectangle {
        id: pushCard
        z: 1313
        visible: root.pushVisible
        anchors.centerIn: parent
        width: Math.min(500, root.width - 100)
        height: pushColumn.height + 48
        radius: 16
        color: Theme.color.surfaceContainerHigh
        border.width: 1
        border.color: Theme.color.outlineVariant

        ColumnLayout {
            id: pushColumn
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.topMargin: 22
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            spacing: 12

            Text {
                text: "Install the public key"
                font.family: Theme.typography.titleMedium.family
                font.pixelSize: 15
                color: Theme.color.onSurfaceColor
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: "The key is appended to ~/.ssh/authorized_keys in that host's own session, "
                      + "so password or touch prompts stay visible."
                font.family: Theme.typography.bodySmall.family
                font.pixelSize: 11
                color: Theme.color.onSurfaceVariantColor
            }

            ComboBox {
                Layout.fillWidth: true
                model: {
                    var names = []
                    for (var i = 0; i < App.hosts.length; i++) names.push(App.hosts[i].alias)
                    return names
                }
                type: "outlined"
                onActivated: (i) => root.pushAlias = App.hosts[i].alias
                Component.onCompleted: if (App.hosts.length > 0) root.pushAlias = App.hosts[0].alias
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WrapAnywhere
                maximumLineCount: 2
                elide: Text.ElideMiddle
                text: root.pushKeyText
                font.family: "Cascadia Mono"
                font.pixelSize: 9
                color: Theme.color.onSurfaceVariantColor
                opacity: 0.8
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Button {
                    text: "Cancel"
                    type: "text"
                    onClicked: root.pushVisible = false
                }
                Button {
                    text: "Install"
                    icon: "upload"
                    onClicked: root.submitPush()
                }
            }
        }
    }

    Dialog {
        id: forgetDialog
        title: "Forget host key?"
        text: (root.forgetLine > 0
               ? "This removes one key entry from ~/.ssh/known_hosts. Because the file hashes "
                 + "host names, the entry is deleted by position. ssh keeps a .old backup."
               : "The next connection to \"" + root.forgetHost + "\" will ask you to verify its "
                 + "fingerprint again. ssh keeps a .old backup of known_hosts.")
        acceptText: "Forget"
        rejectText: "Cancel"
        icon: "delete"
        onAccepted: {
            var res = App.forgetHost(root.forgetHost, root.forgetLine)
            if (res.ok) {
                root.statusOk = res.message || "Forgot the host key"
                root.statusError = ""
                root.reload()
            } else {
                root.statusError = res.error
            }
        }
    }

    // ── Trust a host ───────────────────────────────────────────────────
    Rectangle {
        id: scanScrim
        anchors.fill: parent
        z: 1314
        visible: root.scanVisible
        color: "#000000"
        opacity: 0.35
        MouseArea {
            anchors.fill: parent
            onClicked: root.scanVisible = false
        }
    }

    Rectangle {
        id: scanCard
        z: 1315
        visible: root.scanVisible
        anchors.centerIn: parent
        width: Math.min(560, root.width - 100)
        height: scanColumn.height + 48
        radius: 16
        color: Theme.color.surfaceContainerHigh
        border.width: 1
        border.color: Theme.color.outlineVariant

        ColumnLayout {
            id: scanColumn
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.topMargin: 22
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            spacing: 12

            Text {
                text: "Trust a host"
                font.family: Theme.typography.titleMedium.family
                font.pixelSize: 15
                color: Theme.color.onSurfaceColor
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: "The scan only reads what the server presents. Compare a fingerprint "
                      + "with one you trust before adding these keys."
                font.family: Theme.typography.bodySmall.family
                font.pixelSize: 11
                color: Theme.color.onSurfaceVariantColor
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    Layout.fillWidth: true
                    label: "Host or address"
                    placeholderText: "git.example.com"
                    type: "outlined"
                    labelBackgroundColor: Theme.color.surfaceContainerHigh
                    onTextChanged: root.scanHostName = text
                    Keys.onReturnPressed: root.submitScan()
                }
                Button {
                    text: "Scan"
                    enabled: !root.scanBusy
                    onClicked: root.submitScan()
                }
            }

            Repeater {
                model: root.scanResults

                delegate: Text {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.type + "  " + modelData.fingerprint
                    elide: Text.ElideMiddle
                    font.family: "Cascadia Mono"
                    font.pixelSize: 10
                    color: Theme.color.onSurfaceVariantColor
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Button {
                    text: "Cancel"
                    type: "text"
                    onClicked: root.scanVisible = false
                }
                Button {
                    text: "Trust"
                    icon: "verified_user"
                    enabled: root.scanResults.length > 0
                    onClicked: root.trustScanned()
                }
            }
        }
    }
}
