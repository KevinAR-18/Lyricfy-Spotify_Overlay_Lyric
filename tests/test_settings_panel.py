from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest

from lyric_overlay.config import default_config, SPOTIFY_API_PLAYBACK_SOURCE
from lyric_overlay.overlay import OverlayWindow, create_application
from lyric_overlay.cinematic.preferences import normalize_options


@pytest.fixture
def overlay():
    app = create_application()
    window = OverlayWindow()
    window.load_config_values(default_config())
    window.show()
    yield window
    window.allow_exit()
    window.close()
    window.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("width,height", [(1920, 1040), (1080, 1880), (1280, 680), (720, 1253), (640, 480)])
def test_settings_fit_available_screen_and_footer_remains_visible(overlay, monkeypatch, width, height):
    area = QRect(0, 0, width, height)
    monkeypatch.setattr(overlay, "_settings_available_geometry", lambda: area)
    monkeypatch.setattr(overlay, "_horizontal_screen_geometry", lambda pos: area)
    overlay.move(width - 100, height - 100)
    overlay.toggle_settings()
    overlay._resize_animation.setCurrentTime(overlay._resize_animation.duration())
    QTest.qWait(30)
    for tab in range(5):
        overlay.settings_tabs.setCurrentIndex(tab)
        overlay.select_playback_source(SPOTIFY_API_PLAYBACK_SOURCE)
        overlay.font_size_input.setValue(48)
        QTest.qWait(20)
        assert area.contains(overlay.geometry())
        assert overlay.width() <= 860
        assert overlay.height() <= 720
        for button in (overlay.save_button, overlay.apply_button, overlay.close_settings_button):
            rect = QRect(button.mapTo(overlay, QPoint()), button.size())
            assert overlay.rect().contains(rect)
            assert button.isVisible()


def test_cancel_restores_preview_and_apply_establishes_new_baseline(overlay):
    saved = []
    overlay.save_requested.connect(lambda config: (saved.append(config), overlay.load_config_values(config)))
    assert not overlay.apply_button.isEnabled()
    overlay.toggle_settings()
    overlay.overlay_corner_radius_input.setValue(7)
    assert overlay._overlay_corner_radius == 7
    overlay.close_settings_panel()
    assert overlay._overlay_corner_radius == 30
    overlay.toggle_settings()
    overlay.overlay_corner_radius_input.setValue(9)
    assert overlay.apply_settings()
    overlay.overlay_corner_radius_input.setValue(15)
    overlay.close_settings_panel()
    assert overlay._overlay_corner_radius == 9
    assert saved[-1].overlay_corner_radius == 9


def test_tray_edits_merge_without_discarding_draft(overlay):
    overlay.toggle_settings()
    overlay.lyric_offset_input.setText("350")
    overlay.sync_external_preferences(autostart_enabled=True, cinematic_enabled=True)
    assert overlay.lyric_offset_input.text() == "350"
    assert overlay.autostart_checkbox.isChecked()
    assert overlay.presentation_buttons[True].isChecked()
    overlay.close_settings_panel()
    assert overlay.lyric_offset_input.text() == "0"
    assert overlay._saved_config.autostart_enabled
    assert overlay._saved_config.cinematic_enabled


def test_api_validation_and_draft_credentials(overlay):
    saved = []
    overlay.save_requested.connect(saved.append)
    overlay.toggle_settings()
    overlay.select_playback_source(SPOTIFY_API_PLAYBACK_SOURCE)
    assert not overlay.credentials_section.isHidden()
    assert not overlay.apply_settings()
    assert not saved
    overlay.client_id_input.setText("test-client")
    overlay.client_secret_input.setText("test-secret")
    overlay.save_requested.connect(overlay.load_config_values)
    assert overlay.apply_settings()
    assert saved[-1].playback_source == SPOTIFY_API_PLAYBACK_SOURCE


def test_reset_tab_preserves_other_draft_and_credentials(overlay):
    overlay.load_config_values(replace(default_config(), spotify_client_id="keep", spotify_client_secret="keep"))
    overlay.toggle_settings()
    overlay.lyric_offset_input.setText("350")
    overlay.settings_tabs.setCurrentIndex(1)
    overlay.poll_interval_input.setValue(5000)
    overlay.reset_settings_tab()
    assert overlay.poll_interval_input.value() == 1000
    assert overlay.client_id_input.text() == "keep"
    assert overlay.lyric_offset_input.text() == "350"


def test_cinematic_draft_rolls_back_and_saves_with_other_tabs(overlay):
    overlay.toggle_settings()
    overlay.cinematic_editor.controls["font_size"].setValue(48)
    assert overlay.current_form_config().cinematic_options["font_size"] == 48
    overlay.close_settings_panel()
    assert overlay.cinematic_editor.options == normalize_options(default_config().cinematic_options)


def test_classic_theme_and_live_lyrics_survive_settings_animation(overlay):
    config = replace(default_config(), overlay_bg_color="#80402010", overlay_text_color="#eeddbb", overlay_corner_radius=18)
    overlay.load_config_values(config)
    overlay._lyrics_available = True
    overlay.set_lines("First lyric", "Second lyric", transition_ms=0)
    overlay.toggle_settings()
    assert overlay._resize_animation.state() == QAbstractAnimation.State.Running
    assert overlay._compact_text_widget.isVisible()
    assert not overlay.settings_panel.styleSheet()
    assert overlay._overlay_background_qcolor() == QColor(config.overlay_bg_color)
    assert overlay._overlay_corner_radius == 18
    QTest.qWait(280)
    overlay.set_lines("Second lyric", "Third lyric", transition_ms=360)
    assert overlay._lyric_transition._animation.state() == QAbstractAnimation.State.Running
    assert overlay.compact_label.text() == "Second lyric"
    overlay.settings_tabs.setCurrentIndex(4)
    assert overlay._lyric_transition.isVisible()
    QTest.qWait(420)
    assert overlay._lyric_transition.isHidden()
    assert overlay.compact_label.isVisible()


def test_rapid_panel_reversal_restores_original_compact_position(overlay):
    overlay.move(90, 110)
    original = QPoint(overlay.pos())
    overlay.toggle_settings()
    QTest.qWait(60)
    intermediate = QRect(overlay.geometry())
    overlay.close_settings_panel()
    assert overlay._resize_animation.startValue() == intermediate
    QTest.qWait(40)
    overlay.toggle_settings()
    QTest.qWait(280)
    overlay.close_settings_panel()
    QTest.qWait(280)
    assert overlay.pos() == original
    assert overlay.settings_panel.isHidden()
    assert not overlay._panel_animating


def test_settings_coordinator_reconnects_only_for_playback_changes(overlay, monkeypatch):
    from lyric_overlay import main as module
    from lyric_overlay.app_controller import AppController
    from lyric_overlay.lyrics import LyricsRepository
    from lyric_overlay.cinematic.manager import CinematicManager

    controller = AppController(None, LyricsRepository(), overlay, default_config())
    manager = CinematicManager(overlay, controller)
    coordinator = module.SettingsCoordinator(overlay, controller, manager)
    persisted, reconnects = [], []
    monkeypatch.setattr(module, "save_config", persisted.append)
    monkeypatch.setattr(module, "set_windows_autostart", lambda *args: None)
    monkeypatch.setattr(coordinator, "reconnect", lambda: reconnects.append(True))
    overlay.toggle_settings()
    overlay.font_size_input.setValue(16)
    assert overlay.apply_settings()
    assert not reconnects
    overlay.poll_interval_input.setValue(2000)
    assert overlay.apply_settings()
    assert len(reconnects) == 1
    assert persisted[-1].poll_interval_ms == 2000
    manager.shutdown()


def test_tray_structure_and_startup_draft_merge(overlay, monkeypatch):
    from lyric_overlay import main as module
    from lyric_overlay.app_controller import AppController
    from lyric_overlay.lyrics import LyricsRepository
    from lyric_overlay.cinematic.manager import CinematicManager
    from lyric_overlay.cinematic import manager as manager_module

    controller = AppController(None, LyricsRepository(), overlay, default_config())
    manager = CinematicManager(overlay, controller)
    monkeypatch.setattr(module, "save_config", lambda config: None)
    monkeypatch.setattr(module, "set_windows_autostart", lambda *args: None)
    monkeypatch.setattr(manager_module, "save_config", lambda config: None)
    menu = module.create_tray_menu(overlay, controller, manager, lambda: None)
    assert [a.text() for a in menu.actions() if not a.isSeparator()] == [
        "Show Overlay", "Hide Overlay", "Reset Position", "Presentation", "Startup", "Settings…",
        f"Lyricfy v{__import__('lyric_overlay').__version__}", "Exit Lyricfy",
    ]
    presentation = next(a.menu() for a in menu.actions() if a.text() == "Presentation")
    assert [a.text() for a in presentation.actions()] == ["Classic", "Cinematic"]
    startup = next(a.menu() for a in menu.actions() if a.text() == "Startup")
    overlay.toggle_settings()
    overlay.lyric_offset_input.setText("700")
    startup.actions()[0].trigger()
    assert controller.config.autostart_enabled
    assert overlay.autostart_checkbox.isChecked()
    assert overlay.lyric_offset_input.text() == "700"
    presentation.actions()[1].trigger()
    assert controller.config.cinematic_enabled
    assert manager.window.isVisible()
    assert overlay._expanded and overlay.isVisible()
    assert overlay.lyric_offset_input.text() == "700"
    presentation.actions()[0].trigger()
    assert not controller.config.cinematic_enabled
    assert not manager.window.isVisible()
    assert overlay._expanded
    menu.deleteLater()
    manager.shutdown()
    manager.window.deleteLater()


def test_failed_persistence_keeps_draft_and_does_not_close(overlay, monkeypatch):
    from lyric_overlay import main as module
    from lyric_overlay.app_controller import AppController
    from lyric_overlay.lyrics import LyricsRepository
    from lyric_overlay.cinematic.manager import CinematicManager

    controller = AppController(None, LyricsRepository(), overlay, default_config())
    manager = CinematicManager(overlay, controller)
    coordinator = module.SettingsCoordinator(overlay, controller, manager)
    def fail(config):
        raise OSError("test write failure")
    monkeypatch.setattr(module, "save_config", fail)
    overlay.toggle_settings()
    overlay.lyric_offset_input.setText("500")
    overlay.save_and_close_settings()
    assert overlay._expanded
    assert controller.config.lyric_offset_ms == 0
    assert overlay.lyric_offset_input.text() == "500"
    assert "Could not save" in overlay.settings_feedback.text()
    manager.shutdown()


def test_reconnect_failure_keeps_saved_source_and_explains_status(overlay, monkeypatch):
    from lyric_overlay import main as module
    from lyric_overlay.app_controller import AppController
    from lyric_overlay.lyrics import LyricsRepository
    from lyric_overlay.cinematic.manager import CinematicManager

    controller = AppController(None, LyricsRepository(), overlay, default_config())
    manager = CinematicManager(overlay, controller)
    coordinator = module.SettingsCoordinator(overlay, controller, manager)
    monkeypatch.setattr(module, "save_config", lambda config: None)
    monkeypatch.setattr(module, "set_windows_autostart", lambda *args: None)
    monkeypatch.setattr(module, "build_playback_client", lambda config: (None, "Test connection failed"))
    overlay.toggle_settings()
    overlay.select_playback_source(SPOTIFY_API_PLAYBACK_SOURCE)
    overlay.client_id_input.setText("test-id")
    overlay.client_secret_input.setText("test-secret")
    assert overlay.apply_settings()
    assert controller.config.playback_source == SPOTIFY_API_PLAYBACK_SOURCE
    assert "Test connection failed" in overlay.playback_status.text()
    assert overlay._expanded
    assert not overlay.apply_button.isEnabled()
    manager.shutdown()


def test_font_combobox_popup_width_matches_control(overlay):
    overlay.toggle_settings()
    overlay._resize_animation.setCurrentTime(overlay._resize_animation.duration())
    QTest.qWait(30)

    # Classic font combo in Appearance tab
    overlay.settings_tabs.setCurrentIndex(2)
    font_combo = overlay.font_family_input
    font_combo.showPopup()
    popup = font_combo.view().window()
    assert popup.width() == font_combo.width()
    assert font_combo.view().width() == font_combo.width()
    font_combo.hidePopup()

    # Cinematic font combo in Cinematic tab
    overlay.settings_tabs.setCurrentIndex(3)
    cinematic_font_combo = overlay.cinematic_editor.controls["font_family"]
    cinematic_font_combo.showPopup()
    cinematic_popup = cinematic_font_combo.view().window()
    assert cinematic_popup.width() == cinematic_font_combo.width()
    assert cinematic_font_combo.view().width() == cinematic_font_combo.width()
    cinematic_font_combo.hidePopup()
