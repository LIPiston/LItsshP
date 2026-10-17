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

    CommandPalette {
        id: commandPalette
        anchors.fill: parent
        window: appWindow
        onHostChosen: (alias) => App.openHost(alias)
        onActionChosen: (action) => {
            if (action === "new-host") appWindow.openHostEditor("")
            else if (action === "settings") appWindow.openSettings()
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
    Shortcut {
        sequences: ["Ctrl+B"]
        onActivated: App.setSetting("sidebarVisible", !(App.settings.sidebarVisible !== false))
    }
    Shortcut { sequences: ["Ctrl+R"]; onActivated: App.reconnectActive() }
    Shortcut { sequences: ["Ctrl+Shift+R"]; onActivated: App.refreshHosts() }
    // Ctrl+Shift+C / Ctrl+Shift+V are handled inside TerminalPane rather than
    // here: a window-level Shortcut would steal them from the composer and
    // from any focused text field, and would double-fire the paste.
    Shortcut {
        sequences: ["Ctrl+Shift+E"]
        onActivated: workspace.focusComposer()
    }

}
