import pytest
from dotenv import dotenv_values
from PySide6.QtCore import QObject
from PySide6.QtTest import QTest

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
                                 "active_color": "not a color", "background": "invalid"})
    assert options["font_size"] == 100
    assert options["text_width"] == 200
    assert options["duration"] == 400
    assert options["active_color"] == DEFAULTS["active_color"]
    assert decode_options("malformed") == DEFAULTS


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
        def set_lines(self, *lines):
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
        manager.dialog.update_option("font_size", 48)
        assert manager.window.bridge.options["font_size"] == 48
        manager.dialog.reject()
        assert manager.window.bridge.options["font_size"] == DEFAULTS["font_size"]
        manager.open_settings()
        manager.dialog.update_option("font_size", 42)
        manager.dialog.save()
        assert saved[-1].cinematic_options["font_size"] == 42
        assert saved[-1].lyric_offset_ms == 350
        manager.set_enabled(False)
        assert overlay.isVisible()
        assert not manager.window.isVisible()
        assert saved[-1].cinematic_enabled is False
        assert saved[-1].cinematic_options["font_size"] == 42
        manager.set_enabled(True)
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
