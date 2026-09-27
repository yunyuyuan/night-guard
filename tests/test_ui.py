from datetime import datetime
from PySide6.QtCore import Qt
import pytest

from nightguard.app import Controller
from nightguard.core import PHRASES, Phase
from nightguard.storage import Config, Store
from nightguard.ui import ReminderDialog, SettingsWindow


@pytest.mark.parametrize("language", ["zh", "en"])
def test_placeholder_and_exact_matching(qtbot, language):
    dialog = ReminderDialog(language, preview=True)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.phrase_input.placeholderText() == PHRASES[language]
    assert not dialog.bypass_button.isEnabled()
    dialog.phrase_input.setText(PHRASES[language] + " ")
    assert not dialog.bypass_button.isEnabled()
    dialog.phrase_input.setText(PHRASES[language])
    assert dialog.bypass_button.isEnabled()
    with qtbot.waitSignal(dialog.bypass_requested) as signal:
        qtbot.mouseClick(dialog.bypass_button, Qt.MouseButton.LeftButton)
    assert signal.args == [PHRASES[language]]


def test_live_reminder_cannot_close_via_escape(qtbot):
    dialog = ReminderDialog("en")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.isVisible()
    dialog.close()
    assert dialog.isVisible()
    dialog.allow_close = True
    dialog.close()


def test_switch_language_updates_settings_and_preserves_edits(qtbot):
    window = SettingsWindow(Config(language="zh"), demo=True)
    qtbot.addWidget(window)
    window.show()
    window.repo_input.setText("example/nightguard")
    window.enabled_box.setChecked(True)
    window.language_combo.setCurrentIndex(1)
    assert window.language == "en"
    assert window.save_button.text() == "Save settings"
    assert window.repo_input.text() == "example/nightguard"
    assert window.enabled_box.isChecked()
    with qtbot.waitSignal(window.save_requested) as signal:
        qtbot.mouseClick(window.save_button, Qt.MouseButton.LeftButton)
    assert signal.args[0].language == "en"
    assert signal.args[0].update_repo == "example/nightguard"
    window.close()
    assert not window.isVisible()


@pytest.fixture
def controller(qapp, tmp_path, monkeypatch):
    qapp.setQuitOnLastWindowClosed(False)
    # Every GUI integration test uses a hard-disabled OS adapter.
    def forbid(*args, **kwargs):
        raise AssertionError("Real OS mutation forbidden in GUI tests")
    monkeypatch.setattr("nightguard.platforms.set_autostart", forbid)
    monkeypatch.setattr("nightguard.platforms.request_shutdown", forbid)
    store = Store(tmp_path)
    control = Controller(qapp, store, demo=True, language="zh")
    yield control
    control.timer.stop()
    control.preview_timer.stop()
    for widget in (control.settings, control.reminder, control.preview):
        if widget:
            widget.hide()
            widget.deleteLater()
    control.deleteLater()


def test_background_starts_without_windows_or_tray(controller):
    controller.tick()
    assert controller.settings is None
    assert controller.reminder is None
    assert controller.preview is None


def test_preview_does_not_enable_or_shutdown(controller, qtbot):
    controller.show_settings()
    controller.show_preview()
    controller.preview_deadline = 0
    controller.tick_preview()
    assert "没有执行关机" in controller.preview.message.text()
    assert not controller.config.enabled
    assert controller.engine.phase == Phase.IDLE
    controller.preview.phrase_input.setText(PHRASES["zh"])
    controller.preview.submit_bypass()
    assert not controller.preview.isVisible()
    assert controller.store.load_bypass() is None


def test_saving_demo_never_modifies_autostart(controller):
    controller.show_settings()
    controller.save(Config(language="en", autostart=True, enabled=False))
    assert controller.store.load().language == "en"
    assert controller.config.language == "en"


def test_bypass_is_persisted_before_hiding(controller):
    controller.engine.enabled = True
    controller.engine.tick(datetime(2026, 9, 27, 1), 0)
    controller.show_reminder()
    controller.bypass(PHRASES["zh"])
    assert not controller.reminder.isVisible()
    assert controller.store.load_bypass() == "2026-09-27|00:00|06:00"
    assert controller.engine.phase == Phase.BYPASSED


def test_failed_bypass_save_keeps_countdown_visible(controller, monkeypatch):
    controller.engine.enabled = True
    controller.engine.tick(datetime(2026, 9, 27, 1), 0)
    controller.show_reminder()
    def fail(_):
        raise OSError("disk full")
    monkeypatch.setattr(controller.store, "save_bypass", fail)
    controller.bypass(PHRASES["zh"])
    assert controller.reminder.isVisible()
    assert controller.engine.phase == Phase.WARNING


def test_invalid_schedule_not_saved(controller):
    controller.show_settings()
    controller.save(Config(start="06:00", end="06:00", language="zh"))
    assert "不能相同" in controller.settings.feedback.text()
    assert controller.config.end == "06:00"
    assert controller.config.start == "00:00"


def test_network_failure_is_localized(controller, qtbot):
    controller.show_settings()
    controller.check_updates("")
    qtbot.waitUntil(lambda: not controller.workers, timeout=3000)
    assert "尚未配置更新仓库" in controller.settings.update_message.text()
    assert controller.settings.check_button.isEnabled()


def test_shutdown_failure_no_automatic_permission_loop(controller):
    controller.engine.enabled = True
    controller.engine.tick(datetime(2026, 9, 27, 1), 0)
    controller.engine.phase = Phase.REQUESTED
    controller.show_reminder()
    controller.shutdown_result((False, "denied"))
    assert controller.shutdown_failed
    assert controller.retry_at is None
    assert controller.reminder.snooze_button.isEnabled()


def test_complete_countdown_dispatches_only_demo_adapter(controller, monkeypatch, qtbot):
    from datetime import timedelta
    from types import SimpleNamespace
    clock = [0.0]
    base = datetime(2026, 9, 27, 1)
    monkeypatch.setattr("nightguard.app.time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr("nightguard.app.datetime", SimpleNamespace(now=lambda: base + timedelta(seconds=clock[0])))
    calls = []
    def fake_shutdown(demo):
        calls.append(demo)
        return True, "demo"
    monkeypatch.setattr("nightguard.platforms.request_shutdown", fake_shutdown)
    controller.engine.enabled = True
    controller.tick()
    assert controller.reminder.isVisible()
    for second in range(1, 61):
        clock[0] = second
        controller.tick()
    qtbot.waitUntil(lambda: not controller.workers, timeout=3000)
    assert calls == [True]
    assert controller.engine.phase == Phase.REQUESTED
    assert controller.retry_at == 120
    assert controller.reminder.counter.text() == "00:00"
    assert "没有执行关机" in controller.reminder.message.text()


def test_preview_does_not_have_real_close_restriction(qtbot):
    preview = ReminderDialog("en", preview=True)
    qtbot.addWidget(preview)
    preview.show()
    qtbot.keyClick(preview, Qt.Key.Key_Escape)
    assert not preview.isVisible()
