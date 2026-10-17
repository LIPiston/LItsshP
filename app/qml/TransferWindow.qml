import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import md3.Core
import QtQuick.Controls as Controls

// Dual-pane SFTP file manager, opened from a host's context menu.
// Local pane on the left, remote pane on the right, transfers in the middle.
Window {
    id: transferWindow

    property string alias: ""
    property var sftp: null

    readonly property var c: Theme.color
    property string localPath: ""
    property string remotePath: ""
    property var localEntries: []
    property var remoteEntries: []
    property var localSelection: []
    property var remoteSelection: []
    property string statusText: ""
    property bool busy: false
    property real progress: -1

    width: 1080
    height: 660
    minimumWidth: 760
    minimumHeight: 460
    title: alias ? "Transfer files · " + alias : "Transfer files"
    color: Theme.color.surface
    visible: false

    // ── Selection helpers ──────────────────────────────────────────────
    function selectedLocalPaths() {
        var out = []
        for (var i = 0; i < localSelection.length; i++) {
            if (localSelection[i])
                out.push(localPath + (localPath.endsWith("/") ? "" : "\\") + localEntries[i].name)
        }
        return out
    }

    function selectedLocalSizes() {
        var out = []
        for (var i = 0; i < localSelection.length; i++) {
            if (localSelection[i])
                out.push(localEntries[i].isDir ? -1 : localEntries[i].size)
        }
        return out
    }

    function selectedRemotePaths() {
        var out = []
        for (var i = 0; i < remoteSelection.length; i++) {
            if (remoteSelection[i])
                out.push(joinRemote(remotePath, remoteEntries[i].name))
        }
        return out
    }

    function selectedRemoteSizes() {
        var out = []
        for (var i = 0; i < remoteSelection.length; i++) {
            if (remoteSelection[i])
                out.push(remoteEntries[i].isDir ? -1 : remoteEntries[i].size)
        }
        return out
    }

    function joinRemote(base, name) {
        if (!base || base === "/")
            return "/" + name
        return base.replace(/\/+$/, "") + "/" + name
    }

    function parentRemote(path) {
        if (!path || path === "/")
            return "/"
        var trimmed = path.replace(/\/+$/, "")
        var idx = trimmed.lastIndexOf("/")
        return idx <= 0 ? "/" : trimmed.substring(0, idx)
    }

    function refreshLocal() {
        localEntries = App.listLocal(localPath)
        localSelection = []
    }

    function refreshRemote() {
        if (!sftp) return
        busy = true
        sftp.listDir(remotePath)
    }

    function open(host) {
        alias = host
        localPath = App.localHome()
        remotePath = ""
        localEntries = App.listLocal(localPath)
        remoteEntries = []
        localSelection = []
        remoteSelection = []
        statusText = "Connecting…"
        busy = true
        if (sftp) {
            sftp.deleteLater()
            sftp = null
        }
        sftp = App.createSftpClient(host)
        sftp.listingReady.connect(onListing)
        sftp.operationDone.connect(onOperation)
        sftp.failed.connect(onFailure)
        sftp.progressChanged.connect(onProgress)
        sftp.start()
        show()
        raise()
        requestActivate()
    }

    function routeFor(what) {
        if (what === "Download") return alias + " → this PC"
        if (what === "Upload") return "this PC → " + alias
        return what
    }

    function onProgress(label, fraction, detail) {
        progress = fraction
        statusText = routeFor(label) + " · " + Math.round(fraction * 100) + "%"
                   + (detail ? " · " + detail : "")
    }

    function onListing(path, entries) {
        busy = false
        remotePath = path
        remoteEntries = entries
        remoteSelection = []
        statusText = entries.length + (entries.length === 1 ? " item" : " items")
    }

    function onOperation(what, ok, message) {
        busy = false
        progress = -1
        statusText = routeFor(what) + (ok ? " done" : " failed")
        if (!ok && message)
            statusText += " · " + message.split("\n")[0]
        refreshRemote()
        refreshLocal()
    }

    function onFailure(message) {
        busy = false
        statusText = message.split("\n")[0]
    }

    function toggleLocal(index) {
        var sel = localSelection.slice()
        sel[index] = !sel[index]
        localSelection = sel
    }

    function toggleRemote(index) {
        var sel = remoteSelection.slice()
        sel[index] = !sel[index]
        remoteSelection = sel
    }

    function upload() {
        var paths = selectedLocalPaths()
        if (!paths.length) {
            statusText = "Select files on the left to upload"
            return
        }
        busy = true
        statusText = "Uploading…"
        sftp.upload(paths, remotePath, selectedLocalSizes())
    }

    function download() {
        var paths = selectedRemotePaths()
        if (!paths.length) {
            statusText = "Select files on the right to download"
            return
        }
        busy = true
        statusText = "Downloading…"
        sftp.download(paths, localPath, selectedRemoteSizes())
    }

    onClosing: {
        if (sftp) sftp.cancel()
    }

    // ── Header ─────────────────────────────────────────────────────────
    Rectangle {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 56
        color: Theme.color.surface

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 12
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
                radius: 15
                color: Theme.color.primaryContainer
                Text {
                    anchors.centerIn: parent
                    text: "swap_vert"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: Theme.color.onPrimaryContainerColor
                }
            }

            ColumnLayout {
                spacing: -1
                Text {
                    text: "Transfer files"
                    font.family: Theme.typography.titleMedium.family
                    font.pixelSize: 15
                    color: Theme.color.onSurfaceColor
                }
                Text {
                    text: alias + " · SFTP"
                    font.family: Theme.typography.labelSmall.family
                    font.pixelSize: 10
                    color: Theme.color.onSurfaceVariantColor
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: transferWindow.statusText
                elide: Text.ElideRight
                Layout.maximumWidth: 420
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 11
                color: Theme.color.onSurfaceVariantColor
            }

            Item {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
                Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: closeHover.containsMouse ? Qt.rgba(Theme.color.onSurfaceColor.r,
                                                              Theme.color.onSurfaceColor.g,
                                                              Theme.color.onSurfaceColor.b, 0.06)
                                                    : "transparent"
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
                    onClicked: transferWindow.close()
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

    // ── Two panes ──────────────────────────────────────────────────────
    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: footer.top
        anchors.margins: 0
        spacing: 0

        FilePane {
            id: localPane
            title: "Local"
            path: transferWindow.localPath
            entries: transferWindow.localEntries
            selection: transferWindow.localSelection
            onNavigate: (p) => { transferWindow.localPath = p; transferWindow.refreshLocal() }
            onParentRequested: {
                transferWindow.localPath = App.parentPath(transferWindow.localPath)
                transferWindow.refreshLocal()
            }
            onToggle: (i) => transferWindow.toggleLocal(i)
            onActivated: (i) => {
                if (transferWindow.localEntries[i].isDir) {
                    transferWindow.localPath = transferWindow.localEntries[i].path
                    transferWindow.refreshLocal()
                }
            }
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            color: Theme.color.outlineVariant
        }

        FilePane {
            id: remotePane
            title: "Remote"
            path: transferWindow.remotePath
            entries: transferWindow.remoteEntries
            selection: transferWindow.remoteSelection
            remotePane: true
            onNavigate: (p) => { transferWindow.remotePath = p; transferWindow.refreshRemote() }
            onParentRequested: {
                transferWindow.remotePath = transferWindow.parentRemote(transferWindow.remotePath)
                transferWindow.refreshRemote()
            }
            onToggle: (i) => transferWindow.toggleRemote(i)
            onActivated: (i) => {
                if (transferWindow.remoteEntries[i].isDir) {
                    transferWindow.remotePath = transferWindow.joinRemote(
                                transferWindow.remotePath, transferWindow.remoteEntries[i].name)
                    transferWindow.refreshRemote()
                }
            }
        }
    }

    // ── Footer actions ─────────────────────────────────────────────────
    Rectangle {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 62
        color: Theme.color.surface

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: Theme.color.outlineVariant
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 8

            // Determinate bar for the transfer in flight. A plain Rectangle
            // because md3's LinearProgress animates its value, and this
            // machine's render loop does not advance QML animations.
            Item {
                Layout.preferredWidth: 160
                Layout.preferredHeight: 3
                visible: transferWindow.progress >= 0
                Rectangle {
                    anchors.fill: parent
                    radius: 2
                    color: Theme.color.surfaceContainerHighest
                }
                Rectangle {
                    width: parent.width * Math.max(0, Math.min(1, transferWindow.progress))
                    height: parent.height
                    radius: 2
                    color: Theme.color.primary
                }
            }

            Text {
                text: transferWindow.statusText
                Layout.fillWidth: true
                elide: Text.ElideRight
                font.family: Theme.typography.labelSmall.family
                font.pixelSize: 11
                color: Theme.color.onSurfaceVariantColor
            }

            Button {
                text: "Upload ↑"
                icon: "upload"
                enabled: !transferWindow.busy
                onClicked: transferWindow.upload()
            }
            Button {
                text: "Download ↓"
                icon: "download"
                type: "tonal"
                enabled: !transferWindow.busy
                onClicked: transferWindow.download()
            }
            Button {
                text: "Refresh"
                icon: "refresh"
                type: "text"
                enabled: !transferWindow.busy
                onClicked: {
                    transferWindow.refreshLocal()
                    transferWindow.refreshRemote()
                }
            }
        }
    }

    // ── One pane ───────────────────────────────────────────────────────
    component FilePane: Rectangle {
        id: pane
        property string title: ""
        property string path: ""
        property var entries: []
        property var selection: []
        property bool remotePane: false

        signal navigate(string path)
        signal parentRequested()
        signal toggle(int index)
        signal activated(int index)

        Layout.fillWidth: true
        Layout.fillHeight: true
        color: "transparent"

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // Pane header: title + current path
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 44

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 12
                    spacing: 8

                    Text {
                        text: pane.title
                        font.family: Theme.typography.labelLarge.family
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        color: Theme.color.onSurfaceVariantColor
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        radius: 6
                        color: Theme.color.surfaceContainerHigh

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 6
                            spacing: 6

                            Text {
                                Layout.fillWidth: true
                                text: pane.path || (pane.remotePane ? "…" : "")
                                elide: Text.ElideMiddle
                                font.family: Theme.typography.labelSmall.family
                                font.pixelSize: 11
                                color: Theme.color.onSurfaceVariantColor
                            }

                            Text {
                                visible: pane.remotePane && transferWindow.busy
                                text: "progress_activity"
                                font.family: Theme.iconFont.name
                                font.pixelSize: 14
                                color: Theme.color.primary
                            }
                        }
                    }

                    // Up one level
                    Item {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: upHover.containsMouse ? Qt.rgba(Theme.color.onSurfaceColor.r,
                                                                   Theme.color.onSurfaceColor.g,
                                                                   Theme.color.onSurfaceColor.b, 0.06)
                                                         : "transparent"
                        }
                        Text {
                            anchors.centerIn: parent
                            text: "arrow_upward"
                            font.family: Theme.iconFont.name
                            font.pixelSize: 15
                            color: Theme.color.onSurfaceVariantColor
                        }
                        MouseArea {
                            id: upHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: pane.parentRequested()
                        }
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.color.outlineVariant
                    opacity: 0.6
                }
            }

            ListView {
                id: paneList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: pane.entries
                boundsBehavior: Flickable.StopAtBounds
                spacing: 1
                Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

                delegate: Rectangle {
                    id: entryRow
                    required property var modelData
                    required property int index
                    property bool selected: pane.selection[index] === true

                    width: paneList.width
                    height: 38
                    color: selected ? Qt.rgba(Theme.color.primary.r, Theme.color.primary.g,
                                              Theme.color.primary.b, 0.16)
                                    : (entryMouse.containsMouse
                                       ? Qt.rgba(Theme.color.onSurfaceColor.r,
                                                 Theme.color.onSurfaceColor.g,
                                                 Theme.color.onSurfaceColor.b, 0.05)
                                       : "transparent")

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 10

                        // Checkbox for multi-select transfer
                        Rectangle {
                            Layout.preferredWidth: 16
                            Layout.preferredHeight: 16
                            radius: 3
                            color: entryRow.selected ? Theme.color.primary : "transparent"
                            border.width: 1
                            border.color: entryRow.selected ? Theme.color.primary
                                                            : Theme.color.outline
                            Text {
                                anchors.centerIn: parent
                                visible: entryRow.selected
                                text: "check"
                                font.family: Theme.iconFont.name
                                font.pixelSize: 11
                                color: Theme.color.onPrimaryColor
                            }
                        }

                        Text {
                            text: modelData.isDir ? "folder" : "description"
                            font.family: Theme.iconFont.name
                            font.pixelSize: 17
                            color: modelData.isDir ? Theme.color.tertiary
                                                   : Theme.color.onSurfaceVariantColor
                        }

                        Text {
                            Layout.fillWidth: true
                            text: modelData.name
                            elide: Text.ElideMiddle
                            font.family: Theme.typography.bodyMedium.family
                            font.pixelSize: 12
                            color: Theme.color.onSurfaceColor
                        }

                        Text {
                            visible: !modelData.isDir
                            text: formatSize(modelData.size)
                            font.family: Theme.typography.labelSmall.family
                            font.pixelSize: 10
                            color: Theme.color.onSurfaceVariantColor
                        }
                    }

                    MouseArea {
                        id: entryMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: pane.toggle(entryRow.index)
                        onDoubleClicked: pane.activated(entryRow.index)
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: pane.entries.length === 0
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: pane.remotePane ? "Empty folder" : "Empty folder"
                font.family: Theme.typography.bodySmall.family
                font.pixelSize: 11
                color: Theme.color.onSurfaceVariantColor
                opacity: 0.7
            }
        }

        function formatSize(bytes) {
            if (bytes < 1024) return bytes + " B"
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
            if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB"
            return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB"
        }
    }
}
