import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import md3.Core

// A compose-and-send strip that sits under the terminal.
//
// It coexists with normal typing: keys still go straight to the session unless
// this field has focus. The point is to prepare a command (or a short block of
// commands) while the session is busy, then hand it over in one go with
// Ctrl+Enter. Enter inserts a newline instead, so multi-line input stays
// editable.
Item {
    id: root

    property var model: null
    property bool enabled: model !== null
    property var history: []
    property int historyIndex: 0

    signal escapePressed()

    readonly property int maxEditorHeight: 92
    readonly property int editorHeight: Math.min(maxEditorHeight,
                                                 Math.max(22, input.contentHeight + 6))

    implicitHeight: editorHeight + 12

    function send() {
        if (!root.model || input.text.length === 0)
            return
        var payload = input.text
        var hist = root.history.slice()
        if (hist.length === 0 || hist[hist.length - 1].text !== payload) {
            hist.push({ text: payload })
            if (hist.length > 50) hist.shift()
            root.history = hist
        }
        root.historyIndex = root.history.length
        root.model.runCommand(payload, false)
        input.text = ""
    }

    function recall(delta) {
        if (root.history.length === 0) return
        var idx = Math.max(0, Math.min(root.history.length, root.historyIndex + delta))
        root.historyIndex = idx
        input.text = idx >= root.history.length ? "" : root.history[idx].text
        input.cursorPosition = input.text.length
    }

    function focusInput() { input.forceActiveFocus() }

    Rectangle {
        anchors.fill: parent
        color: Theme.color.surfaceContainerLow

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: Theme.color.outlineVariant
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 10
        anchors.topMargin: 4
        anchors.bottomMargin: 6
        spacing: 8

        // Prompt glyph: makes it obvious this is not the terminal itself.
        Text {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 4
            text: "keyboard_return"
            font.family: Theme.iconFont.name
            font.pixelSize: 16
            color: Theme.color.primary
            opacity: 0.85
        }

        // A bare TextEdit, not a TextEdit inside a Flickable. The Flickable
        // layout is the obvious one, but it showed no text in the running app;
        // a minimal Flickable + TextEdit case does render, so the exact
        // trigger was never isolated. This shape works and is used on purpose.
        // The field grows with its content up to maxEditorHeight and scrolls
        // internally beyond that; the composer's height follows editorHeight.
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextEdit {
                id: input
                width: parent.width
                height: root.editorHeight
                anchors.top: parent.top
                leftPadding: 5
                rightPadding: 5
                topPadding: 3
                bottomPadding: 3
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                selectionColor: Theme.color.primary
                selectedTextColor: Theme.color.onPrimaryColor
                color: Theme.color.onSurfaceColor
                font.family: Theme.typography.bodyMedium.family
                font.pixelSize: 13
                enabled: root.enabled

                // The field scrolls internally once it hits maxEditorHeight;
                // keep the caret visible by nudging the text origin.
                property real scrollOffset: 0
                y: -scrollOffset
                clip: false

                Text {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.leftMargin: 5
                    anchors.topMargin: 3
                    visible: input.text.length === 0
                    text: "Type a command to send when you're ready…"
                    font: input.font
                    color: Theme.color.onSurfaceVariantColor
                    opacity: 0.65
                }

                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        if (event.modifiers & Qt.ControlModifier) {
                            root.send()
                        } else {
                            input.insert(input.cursorPosition, "\n")
                        }
                        event.accepted = true
                        return
                    }
                    if (event.key === Qt.Key_Escape) {
                        root.escapePressed()
                        event.accepted = true
                        return
                    }
                    if (event.key === Qt.Key_Up && (event.modifiers & Qt.ControlModifier)) {
                        root.recall(-1)
                        event.accepted = true
                        return
                    }
                    if (event.key === Qt.Key_Down && (event.modifiers & Qt.ControlModifier)) {
                        root.recall(1)
                        event.accepted = true
                        return
                    }
                }

                onCursorPositionChanged: {
                    var caret = input.cursorRectangle
                    var visibleTop = input.scrollOffset
                    var visibleBottom = visibleTop + input.height
                    if (caret.y < visibleTop)
                        input.scrollOffset = Math.max(0, caret.y - 4)
                    else if (caret.y + caret.height > visibleBottom)
                        input.scrollOffset = caret.y + caret.height - input.height + 4
                }
            }
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            visible: root.enabled && input.text.length > 0
            text: "Ctrl+Enter"
            font.family: Theme.typography.labelSmall.family
            font.pixelSize: 10
            color: Theme.color.onSurfaceVariantColor
            opacity: 0.7
        }

        Button {
            Layout.alignment: Qt.AlignVCenter
            text: "Send"
            icon: "send"
            enabled: root.enabled && input.text.length > 0
            onClicked: root.send()
        }
    }
}
