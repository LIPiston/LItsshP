import QtQuick
import QtQuick.Layouts
import md3.Core
Item {
    id: control
    
    // API
    // Array of objects: { text: "Label", icon: "icon_name", selected: true/false, enabled: true, tooltip: "..." }
    property var buttons: [
        { text: "Day", icon: "menu", selected: false },
        { text: "Week", icon: "check", selected: true },
        { text: "Month", icon: "grid_view", selected: false },
        { text: "Year", icon: "calendar_today", selected: false }
    ] 
    property bool enabled: true
    property bool multiSelect: false
    
    signal clicked(int index)

    function _getDisabledColor(colorString, alpha) {
        let c = Qt.color(colorString)
        return Qt.rgba(c.r, c.g, c.b, alpha)
    }

    function _handleClicked(index) {
        var newButtons = []
        for (var i = 0; i < buttons.length; i++) {
            var item = buttons[i]
            // Shallow copy
            var newItem = {}
            for (var key in item) {
                newItem[key] = item[key]
            }
            
            if (multiSelect) {
                if (i === index) newItem.selected = !item.selected
            } else {
                newItem.selected = (i === index)
            }
            newButtons.push(newItem)
        }
        buttons = newButtons
        clicked(index)
    }

    implicitWidth: row.implicitWidth
    implicitHeight: 28

    // Content Clipping Container
    Rectangle {
        id: container
        anchors.fill: parent
        radius: Theme.skin.radiusControl
        color: "transparent"
        clip: true

        RowLayout {
            id: row
            anchors.fill: parent
            spacing: 4

            Repeater {
                model: control.buttons
                delegate: Rectangle {
                    id: segment
                    Layout.fillHeight: true
                    Layout.minimumWidth: 36
                    implicitWidth: Math.max(contentRow.implicitWidth + 20, 36)
                    
                    property bool isSelected: modelData.selected === true
                    property bool isSegmentEnabled: (modelData.enabled !== undefined ? modelData.enabled : true) && control.enabled
                    property bool isFirst: index === 0
                    property bool isLast: index === control.buttons.length - 1

                    // One rounded chip per segment rather than a fused pill:
                    // Pebrel never merges controls into a single capsule, and
                    // separate chips read as independent choices.
                    radius: Theme.skin.radiusControl

                    color: isSelected && isSegmentEnabled ? Theme.skin.accentSoft
                                                          : (segmentMouse.containsMouse
                                                             ? Theme.skin.hover : "transparent")

                    MouseArea {
                        id: segmentMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: segment.isSegmentEnabled
                    }

                    // Content
                    Row {
                        id: contentRow
                        anchors.centerIn: parent
                        spacing: 8
                        
                        // Icon (Checkmark if selected, or provided icon)
                        Text {
                            text: segment.isSelected ? "check" : (modelData.icon || "")
                            font.family: Theme.iconFont.name
                            font.pixelSize: 18
                            color: {
                                if (!segment.isSegmentEnabled) return control._getDisabledColor(Theme.color.onSurfaceColor, 0.38)
                                if (segment.isSelected) return Theme.skin.accent
                                return Theme.skin.icon
                            }
                            visible: text !== ""
                            verticalAlignment: Text.AlignVCenter
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: modelData.text || ""
                            font.family: Theme.typography.labelLarge.family
                            font.pixelSize: 11
                            font.weight: Theme.typography.labelLarge.weight
                            color: {
                                if (!segment.isSegmentEnabled) return control._getDisabledColor(Theme.color.onSurfaceColor, 0.38)
                                if (segment.isSelected) return Theme.skin.inkStrong
                                return Theme.skin.inkDim
                            }
                            visible: text !== ""
                            verticalAlignment: Text.AlignVCenter
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    // Ripple
                    Ripple {
                        anchors.fill: parent
                        rippleColor: Theme.color.onSurfaceColor
                        enabled: segment.isSegmentEnabled
                        onClicked: (mouse) => control._handleClicked(index)
                        
                        clipTopLeftRadius: Theme.skin.radiusControl
                        clipBottomLeftRadius: Theme.skin.radiusControl
                        clipTopRightRadius: Theme.skin.radiusControl
                        clipBottomRightRadius: Theme.skin.radiusControl
                    }
                }
            }
        }
    }

    // No outline around the group: the chips are the controls, and a capsule
    // border would fuse them back into one widget.
    Rectangle {
        id: borderOverlay
        visible: false
        anchors.fill: parent
        color: "transparent"
    }
}

