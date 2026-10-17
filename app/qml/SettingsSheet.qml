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

    function open() {
        scrim.visible = true
        panel.opacity = 1
        Qt.callLater(function() { seedField.forceActiveFocus() })
    }

    function close() {
        scrim.visible = false
    }

    Rectangle {
        id: scrim
        anchors.fill: parent
        color: "#000000"
        opacity: 0.45
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
        radius: 14
        color: Theme.color.surfaceContainerLow
        border.width: 1
        border.color: Theme.color.outlineVariant
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
                        color: Theme.color.onSurfaceColor
                    }
                    Item { Layout.fillWidth: true }
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
                        Layout.topMargin: 10
                        text: "Accent colour"
                        font.family: Theme.typography.labelMedium.family
                        font.pixelSize: 12
                        color: Theme.color.onSurfaceVariantColor
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Repeater {
                            model: ["#6750a4", "#006a6a", "#7d5260", "#3f6212", "#8b5000", "#0061a4", "#984061"]
                            delegate: Rectangle {
                                required property string modelData
                                Layout.preferredWidth: 30
                                Layout.preferredHeight: 30
                                radius: 15
                                color: modelData
                                border.width: root.settings.seedColor === modelData ? 3 : 1
                                border.color: root.settings.seedColor === modelData
                                              ? Theme.color.onSurfaceColor : Theme.color.outlineVariant
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: App.setSetting("seedColor", modelData)
                                }
                            }
                        }

                        TextField {
                            id: seedField
                            Layout.preferredWidth: 130
                            label: "Hex"
                            text: root.settings.seedColor
                            type: "outlined"
                            labelBackgroundColor: Theme.color.surfaceContainerLow
                            onAccepted: {
                                if (/^#[0-9a-fA-F]{6}$/.test(text))
                                    App.setSetting("seedColor", text)
                            }
                            onEditingFinished: {
                                if (/^#[0-9a-fA-F]{6}$/.test(text))
                                    App.setSetting("seedColor", text)
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }

                    Text {
                        Layout.topMargin: 12
                        text: "Terminal theme"
                        font.family: Theme.typography.labelMedium.family
                        font.pixelSize: 12
                        color: Theme.color.onSurfaceVariantColor
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
                        color: Theme.color.onSurfaceVariantColor
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
                            labelBackgroundColor: Theme.color.surfaceContainerLow
                            currentIndex: Math.max(0, root.fonts.indexOf(root.settings.fontFamily))
                            onActivated: (index) => App.setSetting("fontFamily", model[index])
                        }

                        Item {
                            id: fontSizeStepper
                            width: 120
                            height: fontCombo.height

                            Rectangle {
                                anchors.fill: parent
                                radius: 6
                                color: "transparent"
                                border.width: 1
                                border.color: Theme.color.outline
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
                                    color: Theme.color.onSurfaceColor
                                }
                                StepperButton {
                                    symbol: "add"
                                    onActivated: App.setSetting("fontSize", Math.min(28, root.settings.fontSize + 1))
                                }
                            }
                        }
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

                    SectionLabel { text: "Configuration" }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Text {
                            Layout.fillWidth: true
                            text: App.configPath()
                            elide: Text.ElideMiddle
                            font.family: Theme.typography.bodySmall.family
                            font.pixelSize: 12
                            color: Theme.color.onSurfaceVariantColor
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
                        color: Theme.color.onSurfaceVariantColor
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
        color: Theme.color.primary
    }

    component StepperButton: Item {
        id: sb
        property string symbol: ""
        signal activated()
        width: 26
        height: 26

        Rectangle {
            anchors.fill: parent
            radius: 6
            color: sbMouse.containsMouse ? root.window.flatHover : "transparent"
        }
        Text {
            anchors.centerIn: parent
            text: sb.symbol
            font.family: Theme.iconFont.name
            font.pixelSize: 15
            color: Theme.color.onSurfaceVariantColor
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
                color: Theme.color.onSurfaceColor
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
