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
        objectName: "ambientLayer"
        anchors.fill: parent
        visible: (opts.ambient_effect || "none") !== "none"

        property real gust: 0.0
        property real pulse: 0.0
        property int lastIndex: -100
        property bool wasPlaying: false
        property real tempoScale: 1.0

        NumberAnimation {
            id: gustAnim
            target: ambientLayer
            property: "gust"
            from: 1.0
            to: 0.0
            duration: 750
            easing.type: Easing.OutCubic
        }

        NumberAnimation {
            id: pulseAnim
            target: ambientLayer
            property: "pulse"
            from: 1.0
            to: 0.0
            duration: 900
            easing.type: Easing.OutQuad
        }

        function onLyricTrigger() {
            gustAnim.restart()
            pulseAnim.restart()
        }

        function resetReaction() {
            gustAnim.stop()
            pulseAnim.stop()
            gust = 0
            pulse = 0
        }

        function updateTempo() {
            // Sample at line/track changes and resume, not on every playback tick.
            var rem = Number(root.state.remaining)
            if (root.state.playing && isFinite(rem) && rem > 0) {
                var factor = 3000.0 / Math.max(1500.0, Math.min(5000.0, rem))
                ambientLayer.tempoScale = Math.max(0.75, Math.min(1.35, factor))
            } else {
                ambientLayer.tempoScale = 1.0
            }
        }

        // Dedicated Loader: Only the active effect is kept in memory and rendered.
        Loader {
            id: effectLoader
            objectName: "ambientEffectLoader"
            anchors.fill: parent
            asynchronous: false
            sourceComponent: {
                var eff = opts.ambient_effect || "none"
                if (eff === "leaves") return leavesComp
                if (eff === "snowfall") return snowfallComp
                if (eff === "rain") return rainComp
                if (eff === "fireflies") return firefliesComp
                if (eff === "blobs") return blobsComp
                if (eff === "stardust") return stardustComp
                return null
            }
        }

        // 1. Leaves Effect (Drifting leaves/sakura with wind sway & tumble)
        Component {
            id: leavesComp
            Item {
                objectName: "leaves"
                anchors.fill: parent
                transform: Translate { x: ambientLayer.gust * 32 }

                Repeater {
                    model: 16
                    Item {
                        id: leafItem
                        readonly property real startX: (index * 47) % Math.max(100, ambientLayer.width)
                        readonly property real fallDuration: Math.max(1600, (4200 + (index * 430) % 2800) / ambientLayer.tempoScale)
                        readonly property real swayAmp: 22 + (index * 7) % 24
                        readonly property real swayDuration: Math.max(900, (1800 + (index * 320) % 1400) / ambientLayer.tempoScale)
                        readonly property real leafWidth: 16 + (index % 4) * 3
                        readonly property real leafHeight: 9 + (index % 3) * 2
                        readonly property var leafColors: [cinematic.albumColor, opts.glow_color, "#D4813B", "#C05646", "#E5A05D", "#D97D64", "#C66D42", "#E8B365"]
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
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                        }

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation {
                                to: leafItem.startX + leafItem.swayAmp
                                duration: leafItem.swayDuration
                                easing.type: Easing.InOutSine
                            }
                            NumberAnimation {
                                to: leafItem.startX - leafItem.swayAmp
                                duration: leafItem.swayDuration
                                easing.type: Easing.InOutSine
                            }
                        }

                        SequentialAnimation on rotation {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation { to: 35; duration: leafItem.swayDuration; easing.type: Easing.InOutSine }
                            NumberAnimation { to: -35; duration: leafItem.swayDuration; easing.type: Easing.InOutSine }
                        }

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
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
        }

        // 2. Winter Snowfall Effect (Soft floating flakes with gentle breeze)
        Component {
            id: snowfallComp
            Item {
                objectName: "snowfall"
                anchors.fill: parent
                transform: Translate { x: ambientLayer.gust * 24 }

                Repeater {
                    model: 16
                    Item {
                        id: snowItem
                        readonly property real startX: (index * 47) % Math.max(100, ambientLayer.width)
                        readonly property real fallDuration: Math.max(1800, (4600 + (index * 370) % 3000) / ambientLayer.tempoScale)
                        readonly property real swayAmp: 14 + (index * 5) % 18
                        readonly property real swayDuration: Math.max(1000, (2200 + (index * 290) % 1500) / ambientLayer.tempoScale)
                        readonly property real snowSize: 3.5 + (index % 4) * 1.4
                        readonly property real baseAlpha: 0.36 + (index % 4) * 0.15
                        readonly property color flakeColor: (index % 4 === 0) ? opts.glow_color : ((index % 4 === 1) ? opts.active_color : "#FFFFFF")

                        width: snowSize * 2.5
                        height: snowSize * 2.5

                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width
                            height: parent.height
                            radius: width / 2
                            color: Qt.alpha(snowItem.flakeColor, 0.22)
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            width: snowItem.snowSize
                            height: snowItem.snowSize
                            radius: width / 2
                            color: Qt.alpha("#FFFFFF", 0.92)
                        }

                        NumberAnimation on y {
                            from: -20
                            to: ambientLayer.height + 20
                            duration: snowItem.fallDuration
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                        }

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation {
                                to: snowItem.startX + snowItem.swayAmp
                                duration: snowItem.swayDuration
                                easing.type: Easing.InOutSine
                            }
                            NumberAnimation {
                                to: snowItem.startX - snowItem.swayAmp
                                duration: snowItem.swayDuration
                                easing.type: Easing.InOutSine
                            }
                        }

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation {
                                from: 0
                                to: snowItem.baseAlpha * ((opts.ambient_intensity || 50) / 100)
                                duration: snowItem.fallDuration * 0.15
                                easing.type: Easing.OutQuad
                            }
                            PauseAnimation {
                                duration: snowItem.fallDuration * 0.70
                            }
                            NumberAnimation {
                                to: 0
                                duration: snowItem.fallDuration * 0.15
                                easing.type: Easing.InQuad
                            }
                        }
                    }
                }
            }
        }

        // 3. Gentle Rain & Mist Effect (Delicate diagonal streaks with misty bottom)
        Component {
            id: rainComp
            Item {
                objectName: "rain"
                anchors.fill: parent
                transform: Translate { x: ambientLayer.gust * 20 }
                rotation: ambientLayer.gust * 6

                // Ground mist (pure geometry gradient, zero shader overhead)
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: Math.max(50, parent.height * 0.24)
                    opacity: (0.16 + ambientLayer.pulse * 0.14) * ((opts.ambient_intensity || 50) / 100)
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.7; color: Qt.alpha(cinematic.albumColor, 0.22) }
                        GradientStop { position: 1.0; color: Qt.alpha(opts.glow_color, 0.32) }
                    }
                }

                Repeater {
                    model: 18
                    Item {
                        id: rainItem
                        readonly property real startX: (index * 43) % Math.max(100, ambientLayer.width)
                        readonly property real fallDuration: Math.max(500, (850 + (index * 95) % 600) / ambientLayer.tempoScale)
                        readonly property real dropWidth: 1.5 + (index % 3) * 0.4
                        readonly property real dropHeight: 20 + (index % 4) * 6
                        readonly property real baseAlpha: 0.32 + (index % 3) * 0.14
                        readonly property color dropColor: (index % 3 === 0) ? Qt.alpha(opts.glow_color, 0.75) : ((index % 3 === 1) ? Qt.alpha(cinematic.albumColor, 0.75) : "#90BEE3FF")

                        x: rainItem.startX
                        width: dropWidth
                        height: dropHeight
                        rotation: 14

                        Rectangle {
                            anchors.fill: parent
                            radius: parent.width / 2
                            color: rainItem.dropColor
                        }

                        NumberAnimation on y {
                            from: -40
                            to: ambientLayer.height + 40
                            duration: rainItem.fallDuration
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                        }

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation {
                                from: 0
                                to: rainItem.baseAlpha * ((opts.ambient_intensity || 50) / 100)
                                duration: rainItem.fallDuration * 0.12
                            }
                            PauseAnimation {
                                duration: rainItem.fallDuration * 0.76
                            }
                            NumberAnimation {
                                to: 0
                                duration: rainItem.fallDuration * 0.12
                            }
                        }
                    }
                }
            }
        }

        // 4. Fireflies / Forest Embers Effect (Warm wandering bioluminescent motes)
        Component {
            id: firefliesComp
            Item {
                objectName: "fireflies"
                anchors.fill: parent
                transform: Translate { x: ambientLayer.gust * 15 }

                Repeater {
                    model: 14
                    Item {
                        id: fireflyItem
                        readonly property real startX: (index * 53) % Math.max(100, ambientLayer.width)
                        readonly property real floatDuration: Math.max(2500, (6200 + (index * 480) % 3200) / ambientLayer.tempoScale)
                        readonly property real wanderAmp: 22 + (index * 7) % 28
                        readonly property real wanderDuration: Math.max(1200, (2500 + (index * 380) % 1700) / ambientLayer.tempoScale)
                        readonly property real fireflySize: 4.0 + (index % 3) * 1.5
                        readonly property real baseAlpha: 0.48 + (index % 3) * 0.20
                        readonly property var fireflyColors: ["#FFE270", "#FFD152", "#98EE64", "#B8F97A", opts.glow_color, cinematic.albumColor]
                        readonly property color fireflyColor: fireflyColors[index % fireflyColors.length]

                        width: fireflySize * 3.0
                        height: fireflySize * 3.0

                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width
                            height: parent.height
                            radius: width / 2
                            color: Qt.alpha(fireflyItem.fireflyColor, 0.26)
                            scale: 1.0 + ambientLayer.pulse * 0.40
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            width: fireflyItem.fireflySize
                            height: fireflyItem.fireflySize
                            radius: width / 2
                            color: (index % 2 === 0) ? "#FFFFFF" : fireflyItem.fireflyColor
                        }

                        NumberAnimation on y {
                            from: ambientLayer.height + 25
                            to: -25
                            duration: fireflyItem.floatDuration
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                        }

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation {
                                to: fireflyItem.startX + fireflyItem.wanderAmp
                                duration: fireflyItem.wanderDuration
                                easing.type: Easing.InOutSine
                            }
                            NumberAnimation {
                                to: fireflyItem.startX - fireflyItem.wanderAmp
                                duration: fireflyItem.wanderDuration * 1.15
                                easing.type: Easing.InOutSine
                            }
                        }

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation {
                                from: 0
                                to: fireflyItem.baseAlpha * ((opts.ambient_intensity || 50) / 100)
                                duration: fireflyItem.floatDuration * 0.15
                                easing.type: Easing.OutQuad
                            }
                            SequentialAnimation {
                                loops: 2
                                NumberAnimation {
                                    to: Math.min(1.0, fireflyItem.baseAlpha * 1.5) * ((opts.ambient_intensity || 50) / 100)
                                    duration: fireflyItem.wanderDuration * 0.4
                                    easing.type: Easing.InOutSine
                                }
                                NumberAnimation {
                                    to: Math.max(0.12, fireflyItem.baseAlpha * 0.45) * ((opts.ambient_intensity || 50) / 100)
                                    duration: fireflyItem.wanderDuration * 0.4
                                    easing.type: Easing.InOutSine
                                }
                            }
                            PauseAnimation {
                                duration: Math.max(0, fireflyItem.floatDuration * 0.70 - fireflyItem.wanderDuration * 1.6)
                            }
                            NumberAnimation {
                                to: 0
                                duration: fireflyItem.floatDuration * 0.15
                                easing.type: Easing.InQuad
                            }
                        }
                    }
                }
            }
        }

        // 5. Fluid Lava / Color Blobs Effect (Single-pass shared blur for fluid blending)
        Component {
            id: blobsComp
            Item {
                objectName: "blobs"
                anchors.fill: parent

                Item {
                    anchors.fill: parent
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        blurEnabled: true
                        blur: 0.70
                        blurMax: 20
                    }

                    // Blob 1: Album color orb
                    Rectangle {
                        objectName: "albumOrb"
                        width: Math.max(180, parent.width * 0.45)
                        height: width
                        radius: width / 2
                        x: parent.width * 0.1
                        y: parent.height * 0.1
                        color: Qt.alpha(cinematic.albumColor, (0.28 + ambientLayer.pulse * 0.12) * ((opts.ambient_intensity || 50) / 100))
                        scale: 0.95 + ambientLayer.pulse * 0.14

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation { to: ambientLayer.width * 0.55; duration: 13000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                            NumberAnimation { to: ambientLayer.width * 0.05; duration: 13000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                        }
                        SequentialAnimation on y {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation { to: ambientLayer.height * 0.45; duration: 16000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                            NumberAnimation { to: ambientLayer.height * 0.10; duration: 16000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                        }
                    }

                    // Blob 2: Glow color orb
                    Rectangle {
                        width: Math.max(160, parent.width * 0.40)
                        height: width
                        radius: width / 2
                        x: parent.width * 0.5
                        y: parent.height * 0.4
                        color: Qt.alpha(opts.glow_color, (0.22 + ambientLayer.pulse * 0.10) * ((opts.ambient_intensity || 50) / 100))
                        scale: 0.92 + ambientLayer.pulse * 0.12

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation { to: ambientLayer.width * 0.15; duration: 15000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                            NumberAnimation { to: ambientLayer.width * 0.60; duration: 15000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                        }
                        SequentialAnimation on y {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation { to: ambientLayer.height * 0.10; duration: 14000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                            NumberAnimation { to: ambientLayer.height * 0.50; duration: 14000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                        }
                    }

                    // Blob 3: Active lyric tint orb
                    Rectangle {
                        width: Math.max(150, parent.width * 0.36)
                        height: width
                        radius: width / 2
                        x: parent.width * 0.3
                        y: parent.height * 0.6
                        color: Qt.alpha(opts.active_color, (0.16 + ambientLayer.pulse * 0.08) * ((opts.ambient_intensity || 50) / 100))
                        scale: 0.90 + ambientLayer.pulse * 0.10

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation { to: ambientLayer.width * 0.40; duration: 11000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                            NumberAnimation { to: ambientLayer.width * 0.20; duration: 11000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                        }
                        SequentialAnimation on y {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                            NumberAnimation { to: ambientLayer.height * 0.20; duration: 12000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                            NumberAnimation { to: ambientLayer.height * 0.65; duration: 12000 / ambientLayer.tempoScale; easing.type: Easing.InOutSine }
                        }
                    }
                }

                // Lyric Backing Glow (sibling, so it doesn't dirty or add to the FBO blur pass)
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: (parent.height / 2) - height / 2
                    width: Math.min(parent.width * 0.85, root.textWidth * 1.4)
                    height: Math.max(70, root.activeHeight * 2.0)
                    radius: height / 2
                    opacity: ambientLayer.pulse * ((opts.ambient_intensity || 50) / 100) * 0.36
                    scale: 0.94 + ambientLayer.pulse * 0.10
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5; color: Qt.alpha(cinematic.albumColor, 0.32) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
            }
        }

        // 6. Stardust Effect (Glowing embers & shimmering dust particles)
        Component {
            id: stardustComp
            Item {
                objectName: "stardust"
                anchors.fill: parent

                Repeater {
                    model: 16
                    Item {
                        id: starItem
                        readonly property real startX: (index * 59) % Math.max(100, ambientLayer.width)
                        readonly property real floatDuration: Math.max(1500, (4000 + (index * 350) % 3000) / ambientLayer.tempoScale)
                        readonly property real swayAmp: 14 + (index * 3) % 18
                        readonly property real swayDuration: Math.max(800, (1500 + (index * 260) % 1200) / ambientLayer.tempoScale)
                        readonly property real baseSize: 3 + (index % 4) * 1.2
                        readonly property real baseAlpha: 0.45 + (index % 3) * 0.18

                        width: baseSize * 3
                        height: baseSize * 3

                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.baseSize * 2.8
                            height: parent.baseSize * 2.8
                            radius: width / 2
                            color: Qt.alpha((index % 3 === 0) ? cinematic.albumColor : opts.glow_color, 0.3)
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.baseSize
                            height: parent.baseSize
                            radius: width / 2
                            color: (index % 4 === 0) ? cinematic.albumColor : ((index % 4 === 1) ? "#FFFFFF" : opts.active_color)
                        }

                        NumberAnimation on y {
                            from: ambientLayer.height + 20
                            to: -20
                            duration: starItem.floatDuration
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
                        }

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            running: root.Window.window && root.Window.window.visible && root.state.playing
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
                            running: root.Window.window && root.Window.window.visible && root.state.playing
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
        if (trackChanged || state.index !== ambientLayer.lastIndex
                || state.playing !== ambientLayer.wasPlaying) {
            ambientLayer.updateTempo()
            if (state.playing) {
                ambientLayer.onLyricTrigger()
            } else {
                ambientLayer.resetReaction()
            }
            ambientLayer.lastIndex = state.index
            ambientLayer.wasPlaying = state.playing
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
