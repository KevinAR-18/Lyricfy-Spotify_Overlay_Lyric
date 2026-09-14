import pytest
from dotenv import dotenv_values
from PySide6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, QObject, QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from shiboken6 import isValid

from lyric_overlay import config as config_module
from lyric_overlay.app_controller import AppController, PlaybackSnapshot
from lyric_overlay.cinematic.bridge import CinematicBridge
from lyric_overlay.cinematic.preferences import DEFAULTS, decode_options, normalize_options
from lyric_overlay.cinematic.window import CinematicWindow
from lyric_overlay.cinematic.manager import CinematicManager
from lyric_overlay.cinematic import manager as manager_module
from lyric_overlay.config import default_config
from lyric_overlay.lyrics import LyricsRepository
from lyric_overlay.models import LyricLine, LyricsData, TrackInfo
from lyric_overlay.overlay import create_application


@pytest.fixture
def app():
    return create_application()


def frame(index=0, progress=0, track="song", text=None, playing=True):
    texts = text or ["First lyric", "Repeated lyric", "Repeated lyric", "Final lyric"]
    return {"track": track, "index": index, "progress": progress, "title": "Song",
            "artist": "Artist", "playing": playing, "remaining": 2000, "message": "",
            "rows": [{"index": i, "text": t} for i, t in enumerate(texts)
                     if index - 2 <= i <= index + 2]}


def test_preferences_roundtrip_handles_font_quotes_and_interpolation(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setattr(config_module, "ENV_FILE", path)
    config = default_config()
    config.cinematic_enabled = True
    config.cinematic_options.update(font_family="Kevin's ${FONT} \\ serif", active_color="#80ffaa33")
    config_module.save_config(config)
    values = dotenv_values(path)
    assert values["CINEMATIC_ENABLED"] == "true"
    assert decode_options(values["CINEMATIC_OPTIONS"]) == normalize_options(config.cinematic_options)


def test_preferences_validate_corrupt_values():
    options = normalize_options({"font_size": 99999, "text_width": -3, "duration": "broken",
                                 "active_color": "not a color", "background": "invalid",
                                 "ambient_effect": "magic", "ambient_intensity": 500})
    assert options["font_size"] == 100
    assert options["text_width"] == 200
    assert options["duration"] == 400
    assert options["active_color"] == DEFAULTS["active_color"]
    assert options["ambient_effect"] == DEFAULTS["ambient_effect"]
    assert options["ambient_intensity"] == 100
    assert decode_options("malformed") == DEFAULTS
    # Verify aurora fallback to none
    assert normalize_options({"ambient_effect": "aurora"})["ambient_effect"] == "none"


def test_repeated_lyrics_use_index_and_seek_resets_transition(app):
    bridge = CinematicBridge(DEFAULTS)
    events = []
    bridge.frameChanged.connect(lambda: events.append(bridge.frame))
    bridge.set_frame(frame(1, 1000))
    bridge.set_frame(frame(1, 1050))
    assert len(events) == 1
    bridge.set_frame(frame(2, 1100))
    assert bridge.frame["sequential"] is True
    bridge.set_frame(frame(1, 100))
    assert bridge.frame["sequential"] is False
    bridge.set_frame(frame(2, 8000))
    assert bridge.frame["sequential"] is False
    bridge.set_frame(frame(0, 0, track="new song"))
    assert bridge.frame["sequential"] is False


def test_controller_publishes_repeated_lines_and_paused_state(app):
    class Overlay:
        def set_lines(self, *lines, **kwargs):
            pass

    controller = AppController(None, LyricsRepository(), Overlay(), default_config())
    track = TrackInfo("song", "Title", "Artist", "Album", 5000, 1000, False)
    lyrics = LyricsData("local", [LyricLine(0, "Repeat"), LyricLine(1000, "Repeat"), LyricLine(2000, "End")])
    controller.snapshot = PlaybackSnapshot(track, lyrics)
    controller.sync_engine.set_lyrics(lyrics)
    frames = []
    controller.cinematic_frame.connect(frames.append)
    controller._render_current_state()
    assert frames[-1]["index"] == 1
    assert frames[-1]["playing"] is False
    track.progress_ms = 0
    controller._render_current_state()
    assert frames[-1]["index"] == 0
    assert frames[-1]["rows"][0]["text"] == "Repeat"
    controller.config.cinematic_enabled = True
    controller.config.cinematic_options["background"] = "album"
    assert controller._needs_cover() is True
    assert controller.config.show_album_cover is False


def _blocks(window):
    return window.rootObject().property("blocks").toVariant()


def test_qml_wraps_reuses_blocks_and_keeps_active_text_visible(app, tmp_path):
    window = CinematicWindow(dict(DEFAULTS, text_width=320, background="gradient", glow_strength=15))
    try:
        window.resize(620, 760)
        window.show()
        long_line = "Aku ingin berjalan bersamamu sampai akhir waktu dan melihat dunia"
        window.bridge.set_frame(frame(0, 0, text=["Previous", long_line, "Next"]))
        QTest.qWait(250)
        blocks = _blocks(window)
        next_block = next(b for b in blocks if b.property("lineIndex") == 1)
        assert next_block.property("lineCount") > 1
        assert next_block.width() <= 320
        start_y = next_block.y()
        window.bridge.set_frame(frame(1, 100, text=["Previous", long_line, "Next"]))
        QTest.qWait(50)
        assert next(b for b in _blocks(window) if b.property("lineIndex") == 1) is next_block
        assert next_block.y() < start_y
        QTest.qWait(500)
        assert next_block.property("role") == 0
        assert next_block.opacity() == pytest.approx(1)
        assert next_block.scale() == pytest.approx(1)
        previous = next(b for b in _blocks(window) if b.property("lineIndex") == 0)
        following = next(b for b in _blocks(window) if b.property("lineIndex") == 2)
        assert previous.y() + previous.height() <= next_block.y()
        assert next_block.y() + next_block.height() <= following.y()
        window.resize(320, 300)
        window.bridge.set_frame(frame(1, 200, text=["Previous", long_line * 8, "Next"]))
        QTest.qWait(300)
        stage = window.rootObject().findChild(QObject, "lyricStage")
        # A very tall block becomes scrollable instead of being elided or scaled down.
        assert window.rootObject().property("activeHeight") > 300
        assert stage.property("contentHeight") > stage.property("height")
        assert next_block.property("font").pixelSize() == DEFAULTS["font_size"]
        assert previous.opacity() == 0
        window.resize(760, 700)
        window.bridge.set_frame(frame(1, 250, text=["Previous", long_line, "Next"]))
        QTest.qWait(400)
        image = window.grabWindow()
        assert not image.isNull()
        image.save(str(tmp_path / "cinematic-preview.png"))
        assert window.status() == window.Status.Ready
    finally:
        window.hide()
        window.deleteLater()
        app.processEvents()


def test_mode_switch_style_cancel_and_save_preserve_playback_config(app, monkeypatch):
    from lyric_overlay.overlay import OverlayWindow

    saved = []
    monkeypatch.setattr(manager_module, "save_config", saved.append)
    overlay = OverlayWindow()
    config = default_config()
    config.lyric_offset_ms = 350
    overlay.load_config_values(config)
    controller = AppController(None, LyricsRepository(), overlay, config)
    manager = CinematicManager(overlay, controller)
    overlay.overlay_hidden.connect(manager.pause_if_hidden)
    try:
        overlay.show()
        manager.set_enabled(True)
        assert manager.window.isVisible()
        assert not overlay.isVisible()
        assert saved[-1].cinematic_enabled is True
        manager.open_settings()
        assert overlay._expanded
        assert overlay.settings_tabs.currentIndex() == 3
        overlay.cinematic_editor.controls["font_size"].setValue(48)
        assert manager.window.bridge.options["font_size"] == 48
        overlay.close_settings_panel()
        assert manager.window.bridge.options["font_size"] == DEFAULTS["font_size"]
        manager.open_settings()
        from lyric_overlay.main import SettingsCoordinator
        from lyric_overlay import main as main_module
        monkeypatch.setattr(main_module, "save_config", saved.append)
        monkeypatch.setattr(main_module, "set_windows_autostart", lambda *args: None)
        coordinator = SettingsCoordinator(overlay, controller, manager)
        overlay.cinematic_editor.controls["font_size"].setValue(42)
        overlay.save_and_close_settings()
        assert saved[-1].cinematic_options["font_size"] == 42
        assert saved[-1].lyric_offset_ms == 350
        manager.set_enabled(False)
        assert overlay.isVisible()
        assert not manager.window.isVisible()
        assert saved[-1].cinematic_enabled is False
        assert saved[-1].cinematic_options["font_size"] == 42
        manager.set_enabled(True)
        hidden = []
        manager.window.hidden.connect(lambda: hidden.append(True))
        controller._render_timer.start()
        assert controller._render_timer.isActive()
        assert manager.window.close() is False  # Close is ignored in favor of hiding to tray.
        assert hidden == [True]
        assert not manager.window.isVisible()
        assert not controller._render_timer.isActive()
        manager.show()
        assert manager.window.isVisible()
        manager.hide()
        assert not manager.window.isVisible()
        assert not overlay.isVisible()
        assert not controller._render_timer.isActive()
    finally:
        manager.shutdown()
        controller.stop()
        overlay.hide()
        if manager.window:
            manager.window.deleteLater()
        overlay.deleteLater()
        app.processEvents()


def test_ambient_effects_render_and_react_to_lyrics(app):
    from lyric_overlay.cinematic.settings import CinematicSettings

    effects = ("leaves", "snowfall", "rain", "fireflies", "blobs", "stardust")
    for effect in effects:
        opts = dict(DEFAULTS, background="transparent", ambient_effect=effect, ambient_intensity=75)
        window = CinematicWindow(opts)
        try:
            window.resize(500, 400)
            window.show()
            window.bridge.set_frame(frame(0, 0, text=["Line 1", "Line 2", "Line 3"]))
            QTest.qWait(150)
            # Advance lyric to trigger gust and pulse and tempo scaling
            window.bridge.set_frame(dict(frame(1, 500, text=["Line 1", "Line 2", "Line 3"]), remaining=1500))
            QTest.qWait(150)
            image = window.grabWindow()
            assert not image.isNull()
            assert window.status() == window.Status.Ready
        finally:
            window.hide()
            window.deleteLater()
            app.processEvents()

    # Verify settings dialog updates ambient_effect and ambient_intensity
    settings = CinematicSettings(DEFAULTS)
    settings.update_option("ambient_effect", "snowfall")
    assert settings.options["ambient_effect"] == "snowfall"
    settings.update_option("ambient_intensity", 80)
    assert settings.options["ambient_intensity"] == 80
    settings.deleteLater()
    app.processEvents()


def _artwork(color):
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


@pytest.mark.parametrize("effect, expected", [
    ("none", False), ("snowfall", False), ("leaves", True), ("rain", True),
    ("fireflies", True), ("blobs", True), ("stardust", True),
])
def test_ambient_artwork_required_without_visible_cover(app, effect, expected):
    config = default_config()
    config.show_album_cover = False
    config.cinematic_enabled = True
    config.cinematic_options = dict(DEFAULTS, ambient_effect=effect)
    controller = AppController(None, LyricsRepository(), None, config)
    assert controller._needs_cover() is expected
    config.cinematic_enabled = False
    assert controller._needs_cover() is False


def test_ambient_artwork_preview_cancel_save_and_late_response(app, monkeypatch):
    from lyric_overlay.overlay import OverlayWindow

    monkeypatch.setattr(manager_module, "save_config", lambda config: None)
    overlay = OverlayWindow()
    config = default_config()
    config.show_album_cover = False
    config.cinematic_options = dict(DEFAULTS)
    overlay.load_config_values(config)
    controller = AppController(None, LyricsRepository(), overlay, config)
    controller.snapshot = PlaybackSnapshot(TrackInfo("song", "Song", "Artist", "Album", 5000, 0, True))
    requests = []
    monkeypatch.setattr(controller.cover_worker, "fetch", lambda track, request_id: requests.append(request_id))
    manager = CinematicManager(overlay, controller)
    from lyric_overlay.main import SettingsCoordinator
    from lyric_overlay import main as main_module
    monkeypatch.setattr(main_module, "save_config", lambda config: None)
    monkeypatch.setattr(main_module, "set_windows_autostart", lambda *args: None)
    coordinator = SettingsCoordinator(overlay, controller, manager)
    try:
        manager.set_enabled(True)
        manager.set_frame(frame())
        assert not requests
        manager.open_settings()
        overlay.cinematic_editor.update_option("ambient_effect", "blobs")
        assert len(requests) == 1
        cancelled_request = requests[-1]
        overlay.close_settings_panel()
        assert not controller._needs_cover()
        controller._apply_fetched_cover("song", _artwork("red"), cancelled_request)
        assert manager.window.bridge.artwork == ""

        manager.open_settings()
        overlay.cinematic_editor.update_option("ambient_effect", "blobs")
        assert len(requests) == 2
        # Responses from an older request must not replace the current preview.
        controller._apply_fetched_cover("song", _artwork("red"), cancelled_request)
        assert manager.window.bridge.artwork == ""
        controller._apply_fetched_cover("song", _artwork("red"), requests[-1])
        app.processEvents()
        assert manager.window.bridge.artwork
        assert QColor(manager.window.bridge.albumColor).red() > QColor(manager.window.bridge.albumColor).blue()
        loader = manager.window.rootObject().findChild(QObject, "ambientEffectLoader")
        effect_item = loader.property("item")
        orb = effect_item.findChild(QObject, "albumOrb")
        assert orb is not None
        assert orb.property("color").red() > orb.property("color").blue()
        overlay.save_and_close_settings()
        assert controller.config.cinematic_options["ambient_effect"] == "blobs"
        assert controller._needs_cover()
        assert len(requests) == 3
        controller._apply_fetched_cover("song", _artwork("blue"), requests[-1])
        app.processEvents()
        effect_item = loader.property("item")
        orb = effect_item.findChild(QObject, "albumOrb")
        assert orb.property("color").blue() > orb.property("color").red()
    finally:
        manager.shutdown()
        controller.stop()
        if manager.window:
            manager.window.deleteLater()
        overlay.hide()
        overlay.deleteLater()
        app.processEvents()


def test_ambient_tempo_tracks_song_changes_pause_and_resume(app):
    window = CinematicWindow(dict(DEFAULTS, ambient_effect="leaves"))
    try:
        window.show()
        ambient = window.rootObject().findChild(QObject, "ambientLayer")
        window.bridge.set_frame(dict(frame(), remaining=5000))
        assert ambient.property("tempoScale") == pytest.approx(0.75)
        window.bridge.set_frame(dict(frame(track="new"), remaining=1500))
        assert ambient.property("tempoScale") == pytest.approx(1.35)
        window.bridge.set_frame(dict(frame(1, 500, track="new"), remaining=3000))
        assert ambient.property("tempoScale") == pytest.approx(1)
        window.bridge.set_frame(dict(frame(1, 550, track="new", playing=False), remaining=3000))
        assert ambient.property("gust") == 0
        assert ambient.property("pulse") == 0
        window.bridge.set_frame(dict(frame(2, 600, track="new", playing=False), remaining=5000))
        window.bridge.set_frame(dict(frame(2, 650, track="new"), remaining=5000))
        assert ambient.property("tempoScale") == pytest.approx(0.75)
        assert ambient.property("gust") > 0
        # Remaining changes alone must not churn the tempo on each playback tick.
        window.bridge.set_frame(dict(frame(2, 700, track="new"), remaining=1500))
        assert ambient.property("tempoScale") == pytest.approx(0.75)
        for index, remaining in enumerate((0, -100, float("inf"), float("nan")), 3):
            window.bridge.set_frame(dict(frame(index, 750, track="new"), remaining=remaining))
            assert ambient.property("tempoScale") == pytest.approx(1)
    finally:
        window.hide()
        window.deleteLater()
        app.processEvents()


@pytest.mark.parametrize("effect", ["leaves", "snowfall", "rain", "fireflies", "blobs", "stardust"])
def test_effect_loader_renders_replaces_and_unloads_effect(app, effect):
    options = dict(DEFAULTS, ambient_effect=effect, show_info=False, show_cover=False,
                   glow_strength=0, ambient_intensity=100)
    window = CinematicWindow(options)
    try:
        window.resize(500, 400)
        window.show()
        QTest.qWait(100)
        window.bridge.set_frame(dict(frame(), rows=[], message=""))
        root = window.rootObject()
        ambient = root.findChild(QObject, "ambientLayer")
        loader = root.findChild(QObject, "ambientEffectLoader")
        item = loader.property("item")
        assert item.objectName() == effect
        if effect in ("leaves", "snowfall", "rain", "fireflies"):
            # Map rendered coordinates, including transforms (rather than just reading x).
            assert item.mapToItem(loader, QPointF(0, 0)).x() > 0
            window.resize(620, 460)
            QTest.qWait(50)
            assert item.width() == loader.width()
            assert item.mapToItem(loader, QPointF(0, 0)).x() > 0
        QTest.qWait(2500)
        assert ambient.property("gust") == pytest.approx(0)
        assert item.mapToItem(loader, QPointF(0, 0)).x() == pytest.approx(0)
        image = window.grabWindow()
        assert not image.isNull()
        # Exclude hover controls at the window edges; only ambient content occupies this area.
        assert any(image.pixelColor(x, y).alpha() > 0
                   for y in range(100, image.height() - 70, 2) for x in range(0, image.width(), 2))
        replacement = "rain" if effect == "blobs" else "blobs"
        window.bridge.set_options(dict(options, ambient_effect=replacement))
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(item)
        new_item = loader.property("item")
        assert new_item.objectName() == replacement
        window.bridge.set_options(dict(options, ambient_effect="none"))
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(new_item)
        assert loader.property("item") is None
        QTest.qWait(100)
        empty = window.grabWindow()
        assert not empty.isNull()
        assert all(empty.pixelColor(x, y).alpha() == 0
                   for y in range(100, empty.height() - 70, 2) for x in range(0, empty.width(), 2))
    finally:
        window.hide()
        window.deleteLater()
        app.processEvents()

