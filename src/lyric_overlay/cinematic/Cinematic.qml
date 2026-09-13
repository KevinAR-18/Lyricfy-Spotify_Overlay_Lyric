import QtQuick
import QtQuick.Window
import QtQuick.Effects

Item {
    id: root
    property var opts: cinematic.options
    property var state: cinematic.frame
    property int transitionDuration: 400
    property bool animateLayout: false
    property string trackIdentity: ""
    property var blocks: []
    property real activeHeight: opts.font_size * 1.3
    property bool fullscreen: root.Window.window && root.Window.window.visibility === Window.FullScreen
    readonly property real textWidth: Math.max(80, Math.min(opts.text_width, width - opts.padding * 2))
    readonly property bool hasBackground: opts.background !== "transparent"

    Rectangle {
        anchors.fill: parent
        visible: root.hasBackground
        color: opts.background_color
        radius: root.fullscreen ? 0 : 20
        clip: true
        Rectangle {
            id: atmosphere
            width: parent.width * 1.5
            height: parent.height * 1.5
            x: -parent.width * 0.25
            y: -parent.height * 0.25
            visible: opts.background === "gradient" || opts.background === "album"
            rotation: -12
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: opts.background === "album" ? cinematic.albumColor : opts.gradient_color
                    Behavior on color { ColorAnimation { duration: 900 } }
                }
                GradientStop { position: 1; color: opts.background_color }
            }
            SequentialAnimation on rotation {
                running: root.Window.window && root.Window.window.visible && opts.background_motion && atmosphere.visible && root.state.playing
                loops: Animation.Infinite
                NumberAnimation { to: 12; duration: 14000; easing.type: Easing.InOutSine }
                NumberAnimation { to: -12; duration: 14000; easing.type: Easing.InOutSine }
            }
        }
        Rectangle {
            anchors.fill: parent
            opacity: opts.vignette / 100
            gradient: Gradient {
                GradientStop { position: 0; color: "#CC000000" }
                GradientStop { position: 0.4; color: "transparent" }
                GradientStop { position: 0.6; color: "transparent" }
                GradientStop { position: 1; color: "#CC000000" }
            }
        }
    }

    // Ambient Effects Layer (active on transparent AND other backgrounds when ambient_effect !== "none")
    Item {
        id: ambientLayer
        anchors.fill: parent
        visible: (opts.ambient_effect || "none") !== "none"

        property real gust: 0.0
        property real pulse: 0.0
        property int lastIndex: -100

        NumberAnimation {
            id: gustAnim
            target: ambientLayer
            property: "gust"
            from: 1.0
            to: 0.0
            duration: 850
            easing.type: Easing.OutCubic
        }

        NumberAnimation {
            id: pulseAnim
            target: ambientLayer
            property: "pulse"
            from: 1.0
            to: 0.0
            duration: 1000
            easing.type: Easing.OutQuad
        }

        function onLyricTrigger() {
            gustAnim.restart()
            pulseAnim.restart()
        }

        // 1. Leaves Effect (Drifting leaves/sakura with wind sway & tumble)
        Item {
            id: leavesLayer
            anchors.fill: parent
            visible: opts.ambient_effect === "leaves"

            Repeater {
                model: 16
                Item {
                    id: leafItem
                    readonly property real startX: (index * 47) % Math.max(100, ambientLayer.width)
                    readonly property real fallDuration: 4200 + (index * 430) % 2800
                    readonly property real swayAmp: 22 + (index * 7) % 24
                    readonly property real swayDuration: 1800 + (index * 320) % 1400
                    readonly property real leafWidth: 16 + (index % 4) * 3
                    readonly property real leafHeight: 9 + (index % 3) * 2
                    readonly property var leafColors: ["#D4813B", "#C05646", "#E5A05D", "#D97D64", "#C66D42", "#E8B365"]
                    readonly property color leafColor: leafColors[index % leafColors.length]
                    readonly property real baseAlpha: 0.45 + (index % 4) * 0.12

                    width: leafWidth
                    height: leafHeight

                    Rectangle {
                        anchors.fill: parent
                        color: leafItem.leafColor
                        topLeftRadius: parent.width * 0.75
                        bottomRightRadius: parent.width * 0.75
                        topRightRadius: 2
                        bottomLeftRadius: 2
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width * 0.7
                            height: 1
                            color: "#50FFFFFF"
                            rotation: 12
                        }
                    }

                    NumberAnimation on y {
                        from: -30
                        to: ambientLayer.height + 30
                        duration: leafItem.fallDuration
                        loops: Animation.Infinite
                        running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "leaves") && root.state.playing
                    }

                    SequentialAnimation on x {
                        loops: Animation.Infinite
                        running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "leaves") && root.state.playing
                        NumberAnimation {
                            to: leafItem.startX + leafItem.swayAmp + ambientLayer.gust * 40
                            duration: leafItem.swayDuration
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            to: leafItem.startX - leafItem.swayAmp + ambientLayer.gust * 20
                            duration: leafItem.swayDuration
                            easing.type: Easing.InOutSine
                        }
                    }

                    SequentialAnimation on rotation {
                        loops: Animation.Infinite
                        running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "leaves") && root.state.playing
                        NumberAnimation { to: 35; duration: leafItem.swayDuration; easing.type: Easing.InOutSine }
                        NumberAnimation { to: -35; duration: leafItem.swayDuration; easing.type: Easing.InOutSine }
                    }

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "leaves") && root.state.playing
                        NumberAnimation {
                            from: 0
                            to: leafItem.baseAlpha * ((opts.ambient_intensity || 50) / 100)
                            duration: leafItem.fallDuration * 0.18
                            easing.type: Easing.OutQuad
                        }
                        PauseAnimation {
                            duration: leafItem.fallDuration * 0.64
                        }
                        NumberAnimation {
                            to: 0
                            duration: leafItem.fallDuration * 0.18
                            easing.type: Easing.InQuad
                        }
                    }
                }
            }
        }

        // 2. Aurora Waves Effect (Ethereal flowing luminous ribbons)
        Item {
            id: auroraLayer
            anchors.fill: parent
            visible: opts.ambient_effect === "aurora"

            Rectangle {
                id: auroraWave1
                width: parent.width * 1.4
                height: Math.max(140, parent.height * 0.5)
                x: -parent.width * 0.2
                y: parent.height * 0.15
                radius: height * 0.5
                rotation: -6
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.35; color: Qt.alpha(cinematic.albumColor, (0.24 + ambientLayer.pulse * 0.14) * ((opts.ambient_intensity || 50) / 100)) }
                    GradientStop { position: 0.70; color: Qt.alpha(opts.glow_color, (0.20 + ambientLayer.pulse * 0.10) * ((opts.ambient_intensity || 50) / 100)) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                layer.enabled: true
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blur: 1.0
                    blurMax: 48
                }
                SequentialAnimation on x {
                    loops: Animation.Infinite
                    running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "aurora") && root.state.playing
                    NumberAnimation { to: -auroraLayer.width * 0.10; duration: 11000; easing.type: Easing.InOutSine }
                    NumberAnimation { to: -auroraLayer.width * 0.25; duration: 11000; easing.type: Easing.InOutSine }
                }
                SequentialAnimation on rotation {
                    loops: Animation.Infinite
                    running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "aurora") && root.state.playing
                    NumberAnimation { to: 4; duration: 13000; easing.type: Easing.InOutSine }
                    NumberAnimation { to: -6; duration: 13000; easing.type: Easing.InOutSine }
                }
            }

            Rectangle {
                id: auroraWave2
                width: parent.width * 1.3
                height: Math.max(120, parent.height * 0.42)
                x: -parent.width * 0.15
                y: parent.height * 0.42
                radius: height * 0.5
                rotation: 5
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.30; color: Qt.alpha(opts.active_color, (0.14 + ambientLayer.pulse * 0.08) * ((opts.ambient_intensity || 50) / 100)) }
                    GradientStop { position: 0.65; color: Qt.alpha(cinematic.albumColor, (0.22 + ambientLayer.pulse * 0.12) * ((opts.ambient_intensity || 50) / 100)) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                layer.enabled: true
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blur: 1.0
                    blurMax: 48
                }
                SequentialAnimation on x {
                    loops: Animation.Infinite
                    running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "aurora") && root.state.playing
                    NumberAnimation { to: -auroraLayer.width * 0.22; duration: 9000; easing.type: Easing.InOutSine }
                    NumberAnimation { to: -auroraLayer.width * 0.10; duration: 9000; easing.type: Easing.InOutSine }
                }
                SequentialAnimation on rotation {
                    loops: Animation.Infinite
                    running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "aurora") && root.state.playing
                    NumberAnimation { to: -3; duration: 10000; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 5; duration: 10000; easing.type: Easing.InOutSine }
                }
            }

            Rectangle {
                id: lyricGlowPulse
                anchors.horizontalCenter: parent.horizontalCenter
                y: (parent.height / 2) - height / 2
                width: Math.min(parent.width * 0.85, root.textWidth * 1.4)
                height: Math.max(70, root.activeHeight * 2.0)
                radius: height / 2
                opacity: ambientLayer.pulse * ((opts.ambient_intensity || 50) / 100) * 0.40
                scale: 0.92 + ambientLayer.pulse * 0.12
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.alpha(cinematic.albumColor, 0.35) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                layer.enabled: true
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blur: 0.9
                    blurMax: 36
                }
            }
        }

        // 3. Stardust Effect (Glowing embers & shimmering dust particles)
        Item {
            id: stardustLayer
            anchors.fill: parent
            visible: opts.ambient_effect === "stardust"

            Repeater {
                model: 20
                Item {
                    id: starItem
                    readonly property real startX: (index * 59) % Math.max(100, ambientLayer.width)
                    readonly property real floatDuration: 4000 + (index * 350) % 3000
                    readonly property real swayAmp: 14 + (index * 3) % 18
                    readonly property real swayDuration: 1500 + (index * 260) % 1200
                    readonly property real baseSize: 3 + (index % 4) * 1.2
                    readonly property real baseAlpha: 0.45 + (index % 3) * 0.18

                    width: baseSize * 3
                    height: baseSize * 3

                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.baseSize * 2.8
                        height: parent.baseSize * 2.8
                        radius: width / 2
                        color: Qt.alpha(opts.glow_color, 0.3)
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.baseSize
                        height: parent.baseSize
                        radius: width / 2
                        color: (index % 3 === 0) ? "#FFFFFF" : opts.active_color
                    }

                    NumberAnimation on y {
                        from: ambientLayer.height + 20
                        to: -20
                        duration: starItem.floatDuration
                        loops: Animation.Infinite
                        running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "stardust") && root.state.playing
                    }

                    SequentialAnimation on x {
                        loops: Animation.Infinite
                        running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "stardust") && root.state.playing
                        NumberAnimation {
                            to: starItem.startX + starItem.swayAmp
                            duration: starItem.swayDuration
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            to: starItem.startX - starItem.swayAmp
                            duration: starItem.swayDuration
                            easing.type: Easing.InOutSine
                        }
                    }

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: root.Window.window && root.Window.window.visible && (opts.ambient_effect === "stardust") && root.state.playing
                        NumberAnimation {
                            from: 0
                            to: starItem.baseAlpha * ((opts.ambient_intensity || 50) / 100)
                            duration: starItem.floatDuration * 0.16
                            easing.type: Easing.OutQuad
                        }
                        SequentialAnimation {
                            loops: 2
                            NumberAnimation {
                                to: Math.min(1.0, starItem.baseAlpha * 1.4) * ((opts.ambient_intensity || 50) / 100)
                                duration: starItem.swayDuration * 0.5
                                easing.type: Easing.InOutSine
                            }
                            NumberAnimation {
                                to: Math.max(0.15, starItem.baseAlpha * 0.6) * ((opts.ambient_intensity || 50) / 100)
                                duration: starItem.swayDuration * 0.5
                                easing.type: Easing.InOutSine
                            }
                        }
                        PauseAnimation {
                            duration: Math.max(0, starItem.floatDuration * 0.68 - starItem.swayDuration * 2)
                        }
                        NumberAnimation {
                            to: 0
                            duration: starItem.floatDuration * 0.16
                            easing.type: Easing.InQuad
                        }
                    }
                }
            }
        }
    }

    // Native dragging keeps positioning correct across monitors and DPI scales.
    MouseArea {
        anchors.fill: parent
        onPressed: root.Window.window.startSystemMove()
        onDoubleClicked: cinematic.command("fullscreen")
    }
    HoverHandler { id: hover }

    Item {
        id: metadata
        anchors.top: parent.top
        anchors.topMargin: 56
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.textWidth
        height: visible ? Math.max(cover.visible ? 52 : 0, info.implicitHeight) : 0
        visible: opts.show_info || opts.show_cover
        Image {
            id: cover
            width: 52; height: 52
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            source: cinematic.artwork
            fillMode: Image.PreserveAspectCrop
            visible: opts.show_cover && source.toString().length > 0
            asynchronous: true
        }
        Text {
            id: info
            anchors.left: cover.visible ? cover.right : parent.left
            anchors.leftMargin: cover.visible ? 16 : 0
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: opts.show_info
            text: root.state.title + "\n" + root.state.artist
            textFormat: Text.PlainText
            font.family: opts.font_family
            font.pixelSize: Math.max(13, Math.min(22, opts.font_size * 0.45))
            color: opts.active_color
            opacity: 0.75
            horizontalAlignment: opts.alignment === "left" ? Text.AlignLeft : opts.alignment === "right" ? Text.AlignRight : Text.AlignHCenter
            wrapMode: Text.Wrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }
    }

    Flickable {
        id: stage
        objectName: "lyricStage"
        anchors.top: metadata.visible ? metadata.bottom : parent.top
        anchors.topMargin: metadata.visible ? 20 : 54
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 40
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true
        contentWidth: width
        contentHeight: Math.max(height, root.activeHeight + opts.padding * 2)
        interactive: contentHeight > height
        boundsBehavior: Flickable.StopAtBounds

        Item {
            id: lyricCanvas
            width: stage.width
            height: stage.contentHeight
            Text {
                anchors.centerIn: parent
                width: root.textWidth
                text: root.state.message
                visible: text.length > 0
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                font.family: opts.font_family
                font.pixelSize: opts.font_size
                color: opts.active_color
                opacity: 0.8
            }
        }
    }

    Component {
        id: blockComponent
        Text {
            id: block
            property int lineIndex: -100
            property int role: 5
            property bool ready: false
            objectName: "lyricBlock"
            width: root.textWidth
            x: (lyricCanvas.width - width) / 2
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: opts.font_family
            font.pixelSize: opts.font_size
            font.bold: opts.bold
            horizontalAlignment: opts.alignment === "left" ? Text.AlignLeft : opts.alignment === "right" ? Text.AlignRight : Text.AlignHCenter
            transformOrigin: opts.alignment === "left" ? Item.Left : opts.alignment === "right" ? Item.Right : Item.Center
            color: role === 0 ? opts.active_color : role < 0 ? opts.previous_color : opts.next_color
            opacity: 0
            scale: 0.82
            layer.enabled: opts.glow_strength > 0 && Math.abs(role) <= 1
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: opts.glow_color
                shadowOpacity: opts.glow_strength / 100
                shadowBlur: 0.6
                shadowHorizontalOffset: 0
                shadowVerticalOffset: 0
                blurMax: 16
            }
            Behavior on y { enabled: block.ready && root.animateLayout; NumberAnimation { duration: root.transitionDuration; easing.type: Easing.OutCubic } }
            Behavior on scale { enabled: block.ready && root.animateLayout; NumberAnimation { duration: root.transitionDuration; easing.type: Easing.OutCubic } }
            Behavior on opacity { enabled: block.ready; NumberAnimation { duration: root.transitionDuration; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: root.transitionDuration } }
            onImplicitHeightChanged: root.queueLayout()
        }
    }

    function queueLayout() { Qt.callLater(layoutBlocks) }

    function layoutBlocks() {
        let active = null
        for (let b of blocks) {
            if (b.lineIndex === state.index) active = b
        }
        activeHeight = active ? active.implicitHeight : opts.font_size * 1.3
        const middle = Math.max(stage.height, activeHeight + opts.padding * 2) / 2
        const contextScale = 1 - 0.18 * opts.motion / 100
        let before = middle - activeHeight / 2 - opts.gap
        let after = middle + activeHeight / 2 + opts.gap
        const ordered = blocks.slice().sort(function(a, b) { return a.lineIndex - b.lineIndex })
        for (let b of ordered) {
            const role = b.lineIndex - state.index
            b.role = role
            b.scale = role === 0 ? 1 : contextScale
            if (role === 0) b.y = middle - b.implicitHeight / 2
            else if (role > 0) {
                b.y = after - b.implicitHeight * (1 - contextScale) / 2
                after += b.implicitHeight * contextScale + opts.gap
            }
            // Hide context when the active block needs the available height.
            const room = stage.height >= activeHeight + opts.gap * 2 + b.implicitHeight * contextScale * 2
            b.opacity = role === 0 ? 1 : Math.abs(role) === 1 && room ? opts.context_opacity / 100 : 0
        }
        for (let i = ordered.length - 1; i >= 0; --i) {
            let b = ordered[i]
            if (b.role < 0) {
                b.y = before - b.implicitHeight * contextScale - b.implicitHeight * (1 - contextScale) / 2
                before -= b.implicitHeight * contextScale + opts.gap
            }
            b.ready = true
        }
    }

    function updateFrame() {
        if (!lyricCanvas) return
        const trackChanged = trackIdentity !== state.track
        trackIdentity = state.track
        animateLayout = state.sequential && !trackChanged && opts.motion > 0
        transitionDuration = state.sequential ? state.duration : Math.min(180, opts.duration)
        if (ambientLayer && state.index !== ambientLayer.lastIndex) {
            ambientLayer.lastIndex = state.index
            if (state.playing) {
                ambientLayer.onLyricTrigger()
            }
        }
        if (trackChanged) {
            for (let b of blocks) b.destroy()
            blocks = []
        }
        let retained = []
        for (let row of state.rows) {
            let found = null
            for (let b of blocks) if (b.lineIndex === row.index) found = b
            if (!found) {
                found = blockComponent.createObject(lyricCanvas, {
                    lineIndex: row.index, text: row.text,
                    y: lyricCanvas.height + 100, opacity: 0
                })
            } else found.text = row.text
            retained.push(found)
        }
        for (let b of blocks) if (retained.indexOf(b) < 0) b.destroy()
        blocks = retained
        stage.contentY = 0
        queueLayout()
    }

    Connections {
        target: cinematic
        function onFrameChanged() { root.updateFrame() }
        function onOptionsChanged() { root.animateLayout = false; root.queueLayout() }
    }
    onWidthChanged: { animateLayout = false; queueLayout() }
    onHeightChanged: { animateLayout = false; queueLayout() }
    Component.onCompleted: updateFrame()

    Row {
        anchors.top: parent.top
        anchors.topMargin: 10
        anchors.right: parent.right
        anchors.rightMargin: 16
        spacing: 6
        opacity: hover.hovered ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        Repeater {
            model: [ {label: "Style", action: "settings"}, {label: "Classic", action: "classic"},
                     {label: root.fullscreen ? "Window" : "Fullscreen", action: "fullscreen"}, {label: "Hide", action: "hide"} ]
            Rectangle {
                required property var modelData
                width: buttonText.implicitWidth + 22; height: 30; radius: 8
                color: buttonMouse.containsMouse ? "#CC48404F" : "#BB211E28"
                Text { id: buttonText; anchors.centerIn: parent; text: modelData.label; color: "#FFF6E8"; font.pixelSize: 12 }
                MouseArea { id: buttonMouse; anchors.fill: parent; hoverEnabled: true; onClicked: cinematic.command(modelData.action) }
            }
        }
    }
    Text {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        anchors.horizontalCenter: parent.horizontalCenter
        text: stage.interactive ? "Scroll to read • Shift+S: style • F11: fullscreen" : "Drag to move • Shift+S: style • F11: fullscreen"
        font.pixelSize: 11
        color: opts.active_color
        opacity: hover.hovered ? 0.65 : 0
    }
    Rectangle {
        anchors.right: parent.right; anchors.bottom: parent.bottom
        width: 24; height: 24; radius: 6
        color: "#8848404F"
        visible: hover.hovered && !root.fullscreen
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.SizeFDiagCursor
            onPressed: root.Window.window.startSystemResize(Qt.RightEdge | Qt.BottomEdge)
        }
    }
}
