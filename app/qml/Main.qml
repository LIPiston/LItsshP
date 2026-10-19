import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import md3.Core

Window {
    id: appWindow

    width: 1280
    height: 820
    minimumWidth: 900
    minimumHeight: 540
    visible: true
    title: "LItsshP"
    color: Theme.color.surface

    // ── Flat design tokens ─────────────────────────────────────────────
    // Termius-like flatness: no elevation, hairline separators, one accent.
    readonly property var settings: App.settings
    readonly property string themeMode: settings.theme || "dark"

    readonly property color flatSurface: Theme.color.surface
    readonly property color flatPanel: Theme.color.surfaceContainerLow
    readonly property color flatPanelHigh: Theme.color.surfaceContainer
    readonly property color flatHover: Qt.rgba(Theme.color.onSurfaceColor.r,
                                               Theme.color.onSurfaceColor.g,
                                               Theme.color.onSurfaceColor.b, 0.06)
    readonly property color flatSelected: Qt.rgba(Theme.color.primary.r,
                                                  Theme.color.primary.g,
                                                  Theme.color.primary.b, 0.16)
    readonly property color hairline: Theme.color.outlineVariant
    readonly property color textPrimary: Theme.color.onSurfaceColor
    readonly property color textSecondary: Theme.color.onSurfaceVariantColor
    readonly property int radiusSmall: 6
    readonly property int radiusMedium: 10

    function applyTheme() {
        var dark = themeMode === "dark"
        if (themeMode === "system")
            dark = Qt.application.styleHints.colorScheme === Qt.ColorScheme.Dark
        StyleManager.seedColor = settings.seedColor || "#6750a4"
        StyleManager.isDarkTheme = dark
    }

    Component.onCompleted: applyTheme()

    Connections {
        target: App
        function onSettingsChanged() { appWindow.applyTheme() }
        function onTerminalColorsChanged() { appWindow.applyTheme() }
    }

    // ── Window glue exposed to the QML pages ───────────────────────────
    // Closing a live session asks first (Settings > confirmClose); a tab whose
    // process already exited closes straight away.
    function requestCloseTab(index) {
        if (!App.hasTabs || index < 0 || index >= App.tabs.length) return
        var t = App.tabs[index]
        var running = t.state === "connecting" || t.state === "connected"
        if (running && App.settings.confirmClose !== false) {
            closeDialog.pending = index
            closeDialog.open()
        } else {
            App.closeTab(index)
        }
    }

    function openHostEditor(alias) { hostEditor.open(alias) }
    function openPalette() { commandPalette.open() }
    function openSettings() { settingsSheet.open() }
    function focusSearch() { sidebar.focusSearch() }
    function openTransfer(alias) { transferWindow.open(alias) }
    function openTunnels() { tunnelSheet.open() }
    function openKeys() { keySheet.open() }
    function openSnippets() { snippetSheet.open() }

    // Choosing a tab to show beside the current one. The picker lists open
    // tabs and hosts: a split is usually "the same command on another server".
    function openSplitPicker() {
        splitPicker.open()
    }

    // Frameless window: the brand block in the sidebar header doubles as the
    // drag handle, so the title area has to forward press/drag to the window.
    function beginWindowDrag(mouse) {
        if (mouse.button !== Qt.LeftButton) return
        appWindow.startSystemMove()
    }
    function toggleMaximized() {
        if (appWindow.visibility === Window.Maximized) appWindow.showNormal()
        else appWindow.showMaximized()
    }

    // Deleting a host rewrites ~/.ssh/config, so it always asks first.
    function confirmDeleteHost(alias) {
        deleteDialog.hostAlias = alias
        deleteDialog.open()
    }

    // ── Sidebar | workspace ────────────────────────────────────────────
    RowLayout {
        anchors.fill: parent
        spacing: 0

        HostSidebar {
            id: sidebar
            Layout.preferredWidth: settings.sidebarWidth || 268
            Layout.fillHeight: true
            visible: settings.sidebarVisible !== false
            window: appWindow
            onHostActivated: (alias) => App.openHost(alias)
            onHostEditRequested: (alias) => appWindow.openHostEditor(alias)
            onTransferRequested: (alias) => transferWindow.open(alias)
            onDeleteRequested: (alias) => appWindow.confirmDeleteHost(alias)
            onAddRequested: appWindow.openHostEditor("")
            onSettingsRequested: appWindow.openSettings()
            onKeysRequested: appWindow.openKeys()
        }

        Rectangle {
            visible: sidebar.visible
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            color: appWindow.hairline
        }

        Workspace {
            id: workspace
            Layout.fillWidth: true
            Layout.fillHeight: true
            window: appWindow
        }
    }

    // ── Overlays ───────────────────────────────────────────────────────
    Snackbar {
        id: snackbar
        z: 90000
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 34
        text: ""
    }

    Connections {
        target: App
        function onToast(message) {
            snackbar.text = message
            snackbar.open()
        }
    }

    Dialog {
        id: deleteDialog
        property string hostAlias: ""
        title: "Delete host?"
        text: "This removes the \"" + hostAlias + "\" block from ~/.ssh/config. "
              + "Other hosts and their stored passwords are left untouched."
        acceptText: "Delete"
        rejectText: "Cancel"
        icon: "delete"
        onAccepted: {
            var res = App.deleteHost(hostAlias)
            if (res.ok) App.toast("Deleted " + hostAlias)
            else App.toast(res.error || "Could not delete the host")
        }
    }

    Dialog {
        id: closeDialog
        property int pending: -1
        title: "Close session?"
        text: App.hasTabs && pending >= 0 && pending < App.tabs.length
              ? "\"" + App.tabs[pending].title + "\" is still running. Closing the tab stops it."
              : ""
        acceptText: "Close"
        rejectText: "Cancel"
        icon: "power_settings_new"
        onAccepted: {
            if (pending >= 0) App.closeTab(pending)
            pending = -1
        }
        onRejected: pending = -1
    }

    HostEditorSheet {
        id: hostEditor
        anchors.fill: parent
        window: appWindow
    }

    SettingsSheet {
        id: settingsSheet
        anchors.fill: parent
        window: appWindow
        onConfigPathRequested: App.revealConfig()
    }

    TunnelSheet {
        id: tunnelSheet
        anchors.fill: parent
        window: appWindow
    }

    KeyManagerSheet {
        id: keySheet
        anchors.fill: parent
        window: appWindow
    }

    SnippetSheet {
        id: snippetSheet
        anchors.fill: parent
        window: appWindow
    }

    // Small chooser for the split's other pane. Opening a host here creates a
    // tab and splits it, so the list can mix open sessions and idle hosts.
    Item {
        id: splitPicker
        anchors.fill: parent
        visible: false
        z: 1400

        function open() {
            splitQuery = ""
            splitFilter.text = ""
            rebuildSplit()
            visible = true
            Qt.callLater(function () { splitFilter.forceActiveFocus() })
        }

        property string splitQuery: ""

        function rebuildSplit() {
            splitModel.clear()
            var needle = splitQuery.trim().toLowerCase()
            for (var i = 0; i < App.tabs.length; i++) {
                if (i === App.activeIndex) continue
                var tabLabel = App.tabs[i].host
                if (needle !== "" && tabLabel.toLowerCase().indexOf(needle) < 0) continue
                splitModel.append({ kind: "tab", id: String(i),
                                    title: tabLabel, subtitle: "open tab" })
            }
            for (var h = 0; h < App.hosts.length; h++) {
                var host = App.hosts[h]
                var hay = (host.alias + " " + host.hostname + " " + (host.user || "")).toLowerCase()
                if (needle !== "" && hay.indexOf(needle) < 0) continue
                splitModel.append({ kind: "host", id: host.alias,
                                    title: host.alias, subtitle: host.hostname })
            }
            splitList.currentIndex = splitModel.count > 0 ? 0 : -1
        }

        function choose(index) {
            if (index < 0 || index >= splitModel.count) return
            var item = splitModel.get(index)
            splitPicker.visible = false
            if (item.kind === "tab") App.splitWith(parseInt(item.id))
            else App.splitHost(item.id)
        }

        Rectangle {
            anchors.fill: parent
            color: "#000000"
            opacity: 0.4
            MouseArea { anchors.fill: parent; onClicked: splitPicker.visible = false }
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(460, splitPicker.width - 100)
            height: Math.min(420, 90 + splitModel.count * 40)
            radius: 14
            color: Theme.color.surfaceContainerHigh
            border.width: 1
            border.color: Theme.color.outline

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 8
                        Text {
                            text: "vertical_split"
                            font.family: Theme.iconFont.name
                            font.pixelSize: 17
                            color: Theme.color.onSurfaceVariantColor
                        }
                        TextInput {
                            id: splitFilter
                            Layout.fillWidth: true
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: Theme.typography.bodyMedium.family
                            font.pixelSize: 13
                            color: Theme.color.onSurfaceColor
                            selectionColor: Theme.color.primary
                            selectedTextColor: Theme.color.onPrimaryColor
                            clip: true
                            onTextChanged: {
                                splitPicker.splitQuery = text
                                splitPicker.rebuildSplit()
                            }
                            Keys.onReturnPressed: splitPicker.choose(splitList.currentIndex)
                            Keys.onEscapePressed: splitPicker.visible = false
                            Text {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                visible: !parent.text
                                text: "Split with a tab or host…"
                                font: parent.font
                                color: Theme.color.onSurfaceVariantColor
                                opacity: 0.6
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

                ListView {
                    id: splitList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: splitModel
                    clip: true
                    currentIndex: 0
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: splitList.width
                        height: 40
                        color: index === splitList.currentIndex
                               ? Theme.color.primaryContainer : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            spacing: 10
                            Text {
                                text: modelData.kind === "tab" ? "tab" : "dns"
                                font.family: Theme.iconFont.name
                                font.pixelSize: 15
                                color: Theme.color.onSurfaceVariantColor
                            }
                            Text {
                                text: modelData.title
                                font.family: Theme.typography.bodyMedium.family
                                font.pixelSize: 12
                                color: Theme.color.onSurfaceColor
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: modelData.subtitle
                                elide: Text.ElideMiddle
                                font.family: Theme.typography.labelSmall.family
                                font.pixelSize: 10
                                color: Theme.color.onSurfaceVariantColor
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered: splitList.currentIndex = index
                            onClicked: splitPicker.choose(index)
                        }
                    }
                }
            }
        }

        ListModel { id: splitModel }
    }

    CommandPalette {
        id: commandPalette
        anchors.fill: parent
        window: appWindow
        onHostChosen: (alias) => App.openHost(alias)
        onSnippetChosen: (name, command) => App.runSnippet(name, command)
        onActionChosen: (action) => {
            if (action === "new-host") appWindow.openHostEditor("")
            else if (action === "settings") appWindow.openSettings()
            else if (action === "snippets") appWindow.openSnippets()
            else if (action === "tunnels") appWindow.openTunnels()
            else if (action === "split") appWindow.openSplitPicker()
            else if (action === "restore") {
                var res = App.restoreLayout()
                if (!res.ok) App.toast(res.error || "Nothing to restore")
            }
            else if (action === "keys") appWindow.openKeys()
            else if (action === "toggle-sidebar") App.setSetting("sidebarVisible", !(App.settings.sidebarVisible !== false))
            else if (action === "refresh") App.refreshHosts()
        }
    }

    // Separate top-level window: transfers keep running while the main window
    // is used for terminal work.
    TransferWindow {
        id: transferWindow
    }

    // ── Global shortcuts ───────────────────────────────────────────────
    Shortcut { sequences: ["Ctrl+T"]; onActivated: appWindow.focusSearch() }
    Shortcut { sequences: ["Ctrl+N"]; onActivated: appWindow.openHostEditor("") }
    Shortcut { sequences: ["Ctrl+W"]; onActivated: appWindow.requestCloseTab(App.activeIndex) }
    Shortcut {
        sequences: ["Ctrl+Tab"]
        onActivated: if (App.hasTabs) App.setActiveIndex((App.activeIndex + 1) % App.tabs.length)
    }
    Shortcut {
        sequences: ["Ctrl+Shift+Tab"]
        onActivated: if (App.hasTabs) App.setActiveIndex((App.activeIndex - 1 + App.tabs.length) % App.tabs.length)
    }
    Shortcut { sequences: ["Ctrl+,"]; onActivated: appWindow.openSettings() }
    Shortcut { sequences: ["Ctrl+Shift+P"]; onActivated: appWindow.openPalette() }
    Shortcut { sequences: ["Ctrl+Shift+T"]; onActivated: appWindow.openTunnels() }
    Shortcut {
        sequences: ["Ctrl+B"]
        onActivated: App.setSetting("sidebarVisible", !(App.settings.sidebarVisible !== false))
    }
    Shortcut { sequences: ["Ctrl+R"]; onActivated: App.reconnectActive() }
    Shortcut { sequences: ["Ctrl+Shift+R"]; onActivated: App.refreshHosts() }
    // Ctrl+F is a window shortcut rather than a pane key handler so it works
    // whether focus is in the terminal, the composer or the sidebar.
    Shortcut { sequences: ["Ctrl+F"]; onActivated: workspace.openSearch() }
    Shortcut { sequences: ["Ctrl+Shift+D"]; onActivated: appWindow.openSplitPicker() }
    Shortcut {
        sequences: ["Ctrl+Shift+O"]
        onActivated: {
            var res = App.restoreLayout()
            if (!res.ok) App.toast(res.error || "Nothing to restore")
        }
    }
    // Ctrl+Shift+C / Ctrl+Shift+V are handled inside TerminalPane rather than
    // here: a window-level Shortcut would steal them from the composer and
    // from any focused text field, and would double-fire the paste.
    Shortcut {
        sequences: ["Ctrl+Shift+E"]
        onActivated: workspace.focusComposer()
    }

}
