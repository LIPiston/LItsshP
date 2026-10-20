import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import md3.Core

Item {
    id: control
    
    property string text: ""
    property string actionText: ""
    property int timeout: 4000
    
    signal actionClicked()
    signal closed()
    
    visible: false
    opacity: 0
    
    // Default positioning
    anchors.bottom: parent ? parent.bottom : undefined
    anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
    anchors.bottomMargin: 24
    
    // Width constraints
    width: Math.min(600, (parent ? parent.width : 300) - 32)
    height: background.height
    
    function open() {
        visible = true
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
        onFinished: {
            control.visible = false
            control.closed()
        }
    }
    
    Rectangle {
        id: background
        width: control.width
        height: layout.implicitHeight + 20
        color: Theme.skin.panel
        radius: Theme.skin.radiusOverlay
        border.width: 1
        border.color: Theme.skin.hairline
        
        RowLayout {
            id: layout
            anchors.fill: parent
            anchors.margins: 10
            anchors.leftMargin: 14
            spacing: 6
            
            Text {
                text: control.text
                color: Theme.skin.ink
                font.family: Theme.typography.bodyMedium.family
                font.pixelSize: 12
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                verticalAlignment: Text.AlignVCenter
            }
            
            // Action Button
            Button {
                visible: control.actionText !== ""
                type: "text"
                Layout.preferredHeight: 28
                
                contentItem: Text {
                    text: control.actionText
                    color: Theme.skin.accent
                    font.family: Theme.typography.labelLarge.family
                    font.pixelSize: 11
                    font.weight: Theme.typography.labelLarge.weight
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }
                
                onClicked: {
                    control.actionClicked()
                    control.close()
                }
            }
            
            // Close Icon
            Item {
                visible: control.actionText === ""
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26
                
                Ripple {
                    anchors.fill: parent
                    clipRadius: 13
                    rippleColor: Theme.skin.ink
                    onClicked: control.close()
                }
                
                Text {
                    anchors.centerIn: parent
                    text: "close"
                    font.family: Theme.iconFont.name
                    font.pixelSize: 16
                    color: Theme.skin.inkDim
                }
            }
        }
    }
}
