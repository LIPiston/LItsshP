import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core
import QtQuick.Controls as Controls

// Centre dialog for appearance and behaviour. Flat rows, no cards.
Item {
    id: root
    property var window
    signal configPathRequested()

    readonly property var settings: App.settings
    readonly property var fonts: App.availableFonts()
    readonly property var fallbacks: App.fallbackFonts()
    // The first problem from the last theme reload; shown under the picker so
    // a broken YAML file is visible instead of silently ignored.
    property string themeError: ""
    function open() {
        scrim.visible = true
        panel.opacity = 1
    }

    function close() {
        scrim.visible = false
    }

    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Theme.skin.veil
        opacity: 1
        visible: false
        z: 1100
        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    Rectangle {
        id: panel
        z: 1101
        width: Math.min(560, root.width - 80)
        height: Math.min(600, root.height - 80)
        anchors.centerIn: parent
        radius: Theme.skin.radiusOverlay
        color: Theme.skin.panel
        border.width: 1
        border.color: Theme.skin.hairline
        visible: scrim.visible

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
                        text: "Settings"
                        font.family: Theme.typography.titleLarge.family
                        font.pixelSize: 18
                        color: Theme.skin.ink
                    }
                    Item { Layout.fillWidth: true }
                    Item {
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.skin.radiusControl
                            color: closeHover.containsMouse ? Theme.skin.hover : "transparent"
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

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentHeight: content.height + 40
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

                ColumnLayout {
                    id: content
                    x: 22
                    y: 18
                    width: parent.width - 44
                    spacing: 6

                    SectionLabel { text: "Appearance" }

                    Row {
                        Layout.fillWidth: true
                        spacing: 8
                        SegmentedButton {
                            anchors.verticalCenter: parent.verticalCenter
                            buttons: [
                                { text: "Dark", selected: root.settings.theme === "dark" },
                                { text: "Light", selected: root.settings.theme === "light" },
                                { text: "System", selected: root.settings.theme === "system" }
                            ]
                            onClicked: (index) => {
                                var modes = ["dark", "light", "system"]
                                App.setSetting("theme", modes[index])
                            }
                        }
                    }

                    Text {
                        Layout.topMargin: 12
                        text: "Theme"
                        font.family: Theme.typography.labelMedium.family
                        font.pixelSize: 12
                        color: Theme.skin.inkDim
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Each family has a dark and a light member; Dark/Light above picks which one you get. "
                              + "Themes are YAML files you can edit — open the folder, change a colour, then Reload."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 10
                        color: Theme.skin.inkFaint
                    }

                    // Swatch rows: each family's own shell/surface/accent, painted
                    // from the real palette so the preview cannot drift from what
                    // the theme actually looks like. The model comes from
                    // StyleManager.families, which resolves the same palettes the
                    // app applies.
                    Grid {
                        Layout.fillWidth: true
                        Layout.topMargin: 2
                        columns: 2
                        rowSpacing: 8
                        columnSpacing: 8

                        Repeater {
                            model: StyleManager.families
                            delegate: Item {
                                id: familySwatch
                                required property var modelData
                                property bool active: (root.settings.themeFamily || "catppuccin") === modelData.id

                                width: Math.floor((content.width - 8) / 2)
                                height: 52

                                Rectangle {
                                    anchors.fill: parent
                                    radius: Theme.skin.radiusControl
                                    color: familySwatch.modelData.shell
                                    border.width: familySwatch.active ? 2 : 1
                                    border.color: familySwatch.active
                                                  ? familySwatch.modelData.accent
                                                  : Theme.skin.hairline
                                }

                                // A miniature of the actual layout: shell strip,
                                // content plane, accent mark.
                                Rectangle {
                                    x: 8
                                    y: 8
                                    width: 26
                                    height: parent.height - 16
                                    radius: 2
                                    color: familySwatch.modelData.surface
                                }
                                Rectangle {
                                    x: 38
                                    y: 8
                                    width: parent.width - 46
                                    height: 10
                                    radius: 2
                                    color: familySwatch.modelData.accent
                                    opacity: 0.85
                                }
                                Rectangle {
                                    x: 38
                                    y: 22
                                    width: parent.width - 58
                                    height: 4
                                    radius: 2
                                    color: familySwatch.modelData.accent
                                    opacity: 0.45
                                }
                                Rectangle {
                                    x: 38
                                    y: 30
                                    width: parent.width - 68
                                    height: 4
                                    radius: 2
                                    color: familySwatch.modelData.accent
                                    opacity: 0.3
                                }

                                Text {
                                    anchors.left: parent.left
                                    anchors.bottom: parent.bottom
                                    anchors.leftMargin: 8
                                    anchors.bottomMargin: 1
                                    text: familySwatch.modelData.label
                                    font.family: Theme.typography.labelSmall.family
                                    font.pixelSize: 9
                                    color: familySwatch.modelData.accent
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: App.setSetting("themeFamily", familySwatch.modelData.id)
                                }
                            }
                        }
                    }

                    // The catalog is a directory of YAML files, so the picker
                    // needs an escape hatch: edit a file, then reload it without
                    // restarting the app.
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 2
                        spacing: 8

                        Text {
                            Layout.fillWidth: true
                            text: StyleManager.themeDir
                            elide: Text.ElideMiddle
                            font.family: Theme.typography.bodySmall.family
                            font.pixelSize: 10
                            color: Theme.skin.inkFaint
                        }
                        Button {
                            text: "Reload"
                            type: "text"
                            icon: "refresh"
                            onClicked: {
                                var problem = StyleManager.reloadThemes()
                                root.themeError = problem
                                if (!problem) App.toast("Themes reloaded")
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.themeError !== ""
                        wrapMode: Text.Wrap
                        text: root.themeError
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 10
                        color: Theme.skin.danger
                    }

                    Text {
                        Layout.topMargin: 8
                        text: "Accent override"
                        font.family: Theme.typography.labelMedium.family
                        font.pixelSize: 12
                        color: Theme.skin.inkDim
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Leave empty to use the theme's own accent."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 10
                        color: Theme.skin.inkFaint
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        TextField {
                            id: seedField
                            Layout.preferredWidth: 120
                            label: "Hex"
                            placeholderText: "#88c0d0"
                            text: root.settings.seedColor
                            type: "outlined"
                            labelBackgroundColor: Theme.skin.panel
                            onAccepted: {
                                if (text === "" || /^#[0-9a-fA-F]{6}$/.test(text))
                                    App.setSetting("seedColor", text)
                            }
                            onEditingFinished: {
                                if (text === "" || /^#[0-9a-fA-F]{6}$/.test(text))
                                    App.setSetting("seedColor", text)
                            }
                        }

                        Button {
                            text: "Use theme accent"
                            type: "text"
                            visible: (root.settings.seedColor || "") !== ""
                            onClicked: {
                                seedField.text = ""
                                App.setSetting("seedColor", "")
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }

                    Text {
                        Layout.topMargin: 12
                        text: "Terminal theme"
                        font.family: Theme.typography.labelMedium.family
                        font.pixelSize: 12
                        color: Theme.skin.inkDim
                    }
                    SegmentedButton {
                        buttons: [
                            { text: "Match app", selected: root.settings.terminalTheme !== "classic" },
                            { text: "Classic dark", selected: root.settings.terminalTheme === "classic" }
                        ]
                        onClicked: (index) => App.setSetting("terminalTheme", index === 0 ? "match" : "classic")
                    }

                    Text {
                        Layout.topMargin: 12
                        text: "Font"
                        font.family: Theme.typography.labelMedium.family
                        font.pixelSize: 12
                        color: Theme.skin.inkDim
                    }
                    Row {
                        Layout.fillWidth: true
                        spacing: 10

                        ComboBox {
                            id: fontCombo
                            width: parent.width - fontSizeStepper.width - 10
                            model: root.fonts
                            type: "outlined"
                            label: "Family"
                            labelBackgroundColor: Theme.skin.panel
                            currentIndex: Math.max(0, root.fonts.indexOf(root.settings.fontFamily))
                            onActivated: (index) => App.setSetting("fontFamily", model[index])
                        }

                        Item {
                            id: fontSizeStepper
                            width: 120
                            height: fontCombo.height

                            Rectangle {
                                anchors.fill: parent
                                radius: Theme.skin.radiusControl
                                color: "transparent"
                                border.width: 1
                                border.color: Theme.skin.icon
                            }
                            Row {
                                anchors.centerIn: parent
                                spacing: 4
                                StepperButton {
                                    symbol: "remove"
                                    onActivated: App.setSetting("fontSize", Math.max(9, root.settings.fontSize - 1))
                                }
                                Text {
                                    width: 34
                                    horizontalAlignment: Text.AlignHCenter
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: root.settings.fontSize
                                    font.family: Theme.typography.bodyLarge.family
                                    font.pixelSize: 14
                                    color: Theme.skin.ink
                                }
                                StepperButton {
                                    symbol: "add"
                                    onActivated: App.setSetting("fontSize", Math.min(28, root.settings.fontSize + 1))
                                }
                            }
                        }
                    }

                    // Fallback font. Only glyphs the primary family lacks come
                    // from here, which is what makes Chinese render at all in
                    // a terminal font that ships no CJK.
                    ComboBox {
                        Layout.fillWidth: true
                        model: ["None (system fallback)"].concat(root.fallbacks)
                        type: "outlined"
                        label: "Fallback for missing glyphs"
                        labelBackgroundColor: Theme.skin.panel
                        currentIndex: {
                            var chosen = root.settings.fontFallback || ""
                            var at = root.fallbacks.indexOf(chosen)
                            return at < 0 ? 0 : at + 1
                        }
                        onActivated: (index) => App.setSetting(
                            "fontFallback", index === 0 ? "" : model[index])
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Used only for characters the first font has no glyph for — "
                              + "Chinese, Japanese and other scripts. The cell size still "
                              + "comes from the primary font."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: Theme.skin.inkDim
                        opacity: 0.8
                    }

                    SectionLabel { text: "Behaviour" }
                    SettingSwitch {
                        label: "Confirm before closing a running session"
                        checked: root.settings.confirmClose !== false
                        onToggled: App.setSetting("confirmClose", checked)
                    }
                    SettingSwitch {
                        label: "Copy selection automatically"
                        checked: root.settings.copyOnSelect !== false
                        onToggled: App.setSetting("copyOnSelect", checked)
                    }
                    SettingSwitch {
                        label: "Show the command composer"
                        checked: root.settings.composerVisible !== false
                        onToggled: App.setSetting("composerVisible", checked)
                    }
                    SettingSwitch {
                        label: "Reconnect automatically when a connection drops"
                        checked: root.settings.autoReconnect !== false
                        onToggled: App.setSetting("autoReconnect", checked)
                    }
                    SettingSwitch {
                        label: "Write session output to a log file"
                        checked: root.settings.sessionLog === true
                        onToggled: App.setSetting("sessionLog", checked)
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: root.settings.sessionLog === true
                        spacing: 10
                        Text {
                            Layout.fillWidth: true
                            text: App.logsPath()
                            elide: Text.ElideMiddle
                            font.family: Theme.typography.bodySmall.family
                            font.pixelSize: 11
                            color: Theme.skin.inkDim
                        }
                        Button {
                            text: "Open folder"
                            type: "text"
                            icon: "folder_open"
                            onClicked: App.revealLogs()
                        }
                    }

                    Text {
                        Layout.topMargin: 10
                        text: "Keep-alive interval"
                        font.family: Theme.typography.labelMedium.family
                        font.pixelSize: 12
                        color: Theme.skin.inkDim
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Seconds between keep-alive probes. Sent as "
                              + "ServerAliveInterval only when the host does not set it."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: Theme.skin.inkDim
                        opacity: 0.85
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        SegmentedButton {
                            buttons: [
                                { text: "Off", selected: (root.settings.keepalive || 0) === 0 },
                                { text: "15 s", selected: root.settings.keepalive === 15 },
                                { text: "30 s", selected: (root.settings.keepalive || 30) === 30 || root.settings.keepalive === undefined },
                                { text: "60 s", selected: root.settings.keepalive === 60 }
                            ]
                            onClicked: (index) => {
                                var values = [0, 15, 30, 60]
                                App.setSetting("keepalive", values[index])
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }

                    SectionLabel { text: "Configuration" }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Text {
                            Layout.fillWidth: true
                            text: "SSH keys and trusted hosts in ~/.ssh"
                            font.family: Theme.typography.bodySmall.family
                            font.pixelSize: 12
                            color: Theme.skin.inkDim
                        }
                        Button {
                            text: "Manage keys"
                            type: "tonal"
                            icon: "key"
                            onClicked: {
                                root.close()
                                root.window.openKeys()
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Text {
                            Layout.fillWidth: true
                            text: App.configPath()
                            elide: Text.ElideMiddle
                            font.family: Theme.typography.bodySmall.family
                            font.pixelSize: 12
                            color: Theme.skin.inkDim
                        }
                        Button {
                            text: "Open folder"
                            type: "tonal"
                            icon: "folder_open"
                            onClicked: root.configPathRequested()
                        }
                        Button {
                            text: "Reload"
                            type: "text"
                            onClicked: {
                                App.refreshHosts()
                                App.toast("Hosts reloaded")
                            }
                        }
                    }

                    Text {
                        Layout.topMargin: 10
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "LItsshP only reads and writes ~/.ssh/config. Passwords and other tssh options are left in tssh's own format, so the tssh CLI keeps working with the same file."
                        font.family: Theme.typography.bodySmall.family
                        font.pixelSize: 11
                        color: Theme.skin.inkDim
                        opacity: 0.85
                    }

                    Item { Layout.preferredHeight: 16 }
                }
            }
        }
    }

    // ── Building blocks ────────────────────────────────────────────────
    component SectionLabel: Text {
        Layout.topMargin: 14
        Layout.bottomMargin: 4
        font.family: Theme.typography.labelLarge.family
        font.pixelSize: 12
        font.weight: Font.Medium
        color: Theme.skin.accent
    }

    component StepperButton: Item {
        id: sb
        property string symbol: ""
        signal activated()
        width: 26
        height: 26

        Rectangle {
            anchors.fill: parent
            radius: Theme.skin.radiusControl
            color: sbMouse.containsMouse ? Theme.skin.hover : "transparent"
        }
        Text {
            anchors.centerIn: parent
            text: sb.symbol
            font.family: Theme.iconFont.name
            font.pixelSize: 15
            color: Theme.skin.inkDim
        }
        MouseArea {
            id: sbMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: sb.activated()
        }
    }

    component SettingSwitch: Item {
        id: ss
        property string label: ""
        property bool checked: false
        signal toggled()
        Layout.fillWidth: true
        implicitHeight: 44

        RowLayout {
            anchors.fill: parent
            spacing: 12
            Text {
                Layout.fillWidth: true
                text: ss.label
                wrapMode: Text.Wrap
                font.family: Theme.typography.bodyMedium.family
                font.pixelSize: 13
                color: Theme.skin.ink
            }
            Switch {
                checked: ss.checked
                onClicked: {
                    ss.checked = checked
                    ss.toggled()
                }
            }
        }
    }
}
