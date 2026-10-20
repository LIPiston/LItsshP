import QtQuick
import md3.Core
Item {
    id: control
    
    // API
    property string text: ""
    property int timeout: 2500
    
    // Theme Helpers
    property var _colors: Theme.color
    property var _typography: Theme.typography
    property var _shape: Theme.shape
    
    // Layout
    // Centered in parent by default if not anchored externally
    x: parent ? (parent.width - width) / 2 : 0
    y: parent ? (parent.height - height) / 2 : 0
    z: 999
    
    implicitWidth: background.width
    implicitHeight: background.height
    
    visible: opacity > 0
    opacity: 0
    
    function open() {
        showAnim.restart()
        if (timeout > 0) {
            hideTimer.interval = timeout
            hideTimer.restart()
        }
    }
    
    function close() {
        hideTimer.stop()
        hideAnim.restart()
    }
    
    Timer {
        id: hideTimer
        onTriggered: control.close()
    }
    
    // Animations
    NumberAnimation {
        id: showAnim
        target: control
        property: "opacity"
        to: 1.0
        duration: 200
        easing.type: Easing.OutQuad
    }
    
    NumberAnimation {
        id: hideAnim
        target: control
        property: "opacity"
        to: 0.0
        duration: 150
        easing.type: Easing.InQuad
    }
    
    // Visuals
    Rectangle {
        id: background
        width: label.implicitWidth + 16
        height: label.implicitHeight + 6
        color: Theme.skin.panel
        radius: Theme.skin.radiusChip
        border.width: 1
        border.color: Theme.skin.hairline
        opacity: 1
        
        Text {
            id: label
            anchors.centerIn: parent
            text: control.text
            font.family: _typography.bodySmall.family
            font.pixelSize: 10
            font.weight: _typography.bodySmall.weight
            color: Theme.skin.inkDim
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            
            // Limit max width if needed, though MD3 plain tooltips are usually short
            // Let's set a max width relative to parent or fixed
            width: Math.min(implicitWidth, (control.parent ? control.parent.width : 300) - 32)
        }
    }
}
