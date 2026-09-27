from __future__ import annotations

import argparse
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import sys
import time

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

from .core import Engine, Phase, Schedule, PHRASES
from .i18n import tr
from .instance import Instance
from . import platforms
from .storage import Config, Store, data_directory
from .ui import ReminderDialog, SettingsWindow
from .updates import UpdateError, check_update, validate_repo

LOG = logging.getLogger("nightguard")


class Worker(QThread):
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, work, parent=None):
        super().__init__(parent)
        self.work = work

    def run(self):
        try:
            self.result.emit(self.work())
        except UpdateError as error:
            self.failed.emit(str(error))
        except Exception:
            LOG.exception("Background operation failed")
            self.failed.emit("network")


class Controller(QObject):
    reopen_requested = Signal()

    def __init__(self, app: QApplication, store: Store, demo=False, language=None):
        super().__init__()
        self.app, self.store, self.demo = app, store, demo
        self.reopen_requested.connect(self.show_settings, Qt.ConnectionType.QueuedConnection)
        self.config = store.load()
        if language:
            self.config.language = language
        self.engine = Engine(Schedule(self.config.start, self.config.end), self.config.enabled, store.load_bypass())
        self.settings = None
        self.reminder = None
        self.preview = None
        self.preview_deadline = None
        self.preview_snooze_until = None
        self.workers = set()
        self.shutdown_busy = False
        self.shutdown_failed = False
        self.retry_at = None
        self.release_url = None
        self.closing = False
        self.preview_only = False
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(200)
        self.preview_timer.timeout.connect(self.tick_preview)

    def command(self, command):
        if self.closing:
            return
        if command == "settings":
            self.show_settings()
        elif command == "preview":
            self.show_preview()
        elif command == "stop":
            self.stop()

    def show_settings(self):
        self.preview_only = False
        if self.settings is None:
            self.settings = SettingsWindow(self.config, self.demo, bool(self.store.warning))
            self.settings.save_requested.connect(self.save)
            self.settings.preview_requested.connect(self.show_preview)
            self.settings.quit_requested.connect(self.confirm_quit)
            self.settings.check_requested.connect(self.check_updates)
            self.settings.release_requested.connect(self.open_release)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()
        self.refresh_status()

    def save(self, config: Config):
        if self.shutdown_busy:
            self.settings.feedback.setText(tr(config.language, "shutdown_pending"))
            return
        try:
            config.validate()
        except ValueError:
            self.settings.feedback.setText(tr(config.language, "invalid_time"))
            return
        try:
            if config.update_repo:
                validate_repo(config.update_repo)
        except UpdateError as error:
            self.settings.feedback.setText(tr(config.language, str(error)))
            return
        old = self.config
        changed_autostart = False
        previous_autostart = False
        try:
            if not self.demo:
                previous_autostart = platforms.autostart_installed()
                # Rewrite an enabled entry to pick up a moved executable path.
                platforms.set_autostart(config.autostart, self.store.root)
                changed_autostart = previous_autostart != config.autostart
            self.store.save(config)
        except (OSError, ValueError) as error:
            if changed_autostart:
                try:
                    platforms.set_autostart(previous_autostart, self.store.root)
                except OSError:
                    LOG.exception("Auto-start rollback failed")
            self.settings.feedback.setText(tr(config.language, "save_error", reason=str(error)))
            LOG.warning("Settings save failed: %s", error)
            return
        self.config = config
        if old.start != config.start or old.end != config.end or old.enabled != config.enabled:
            self.hide_reminder()
            self.retry_at = None
            self.shutdown_failed = False
        self.engine.configure(Schedule(config.start, config.end), config.enabled)
        if self.reminder and old.language != config.language:
            self.reminder.retranslate(config.language)
        self.settings.notice.setVisible(self.demo)
        self.settings.feedback.setText(tr(config.language, "saved" if config.enabled else "saved_paused"))
        self.tick()

    def tick(self):
        if self.closing:
            return
        monotonic = time.monotonic()
        now = datetime.now().astimezone()
        # If an accepted shutdown was blocked/cancelled by another app, offer a
        # fresh minute rather than leaving the user permanently unprotected.
        if self.retry_at is not None and monotonic >= self.retry_at and not self.shutdown_busy:
            self.retry_at = None
            if self.engine.phase == Phase.REQUESTED:
                self.engine.snooze(monotonic - 60)
        event = self.engine.tick(now, monotonic)
        if event == "show":
            self.show_reminder()
        elif event == "hide":
            self.hide_reminder()
            self.retry_at = None
        elif event == "shutdown":
            self.dispatch_shutdown()
        if self.reminder and self.engine.phase == Phase.WARNING:
            self.reminder.set_remaining(self.engine.remaining(monotonic))
        self.refresh_status()

    def refresh_status(self):
        if not self.settings:
            return
        key = "status_disabled" if not self.config.enabled else "status_" + self.engine.phase.value
        if self.engine.phase == Phase.REQUESTED and self.shutdown_failed:
            key = "status_failed"
        self.settings.status.setText(tr(self.settings.language, key))

    def show_reminder(self):
        if self.reminder is None:
            self.reminder = ReminderDialog(self.config.language)
            self.reminder.snooze_requested.connect(self.snooze)
            self.reminder.bypass_requested.connect(self.bypass)
        self.reminder.message.setText(tr(self.config.language, "demo_badge") if self.demo else "")
        self.reminder.phrase_input.clear()
        self.reminder.set_busy(False)
        self.reminder.set_remaining(60)
        self.shutdown_failed = False
        self.reminder.present()

    def hide_reminder(self):
        if self.reminder:
            self.reminder.hide()
            self.reminder.phrase_input.clear()

    def snooze(self):
        if not self.shutdown_busy and self.engine.snooze(time.monotonic()):
            self.retry_at = None
            self.hide_reminder()
            self.refresh_status()

    def bypass(self, text):
        if self.shutdown_busy or text != PHRASES[self.config.language]:
            return
        if not self.engine.active_session or self.engine.phase not in (Phase.WARNING, Phase.REQUESTED):
            return
        try:
            self.store.save_bypass(self.engine.active_session)
        except OSError:
            self.reminder.message.setText(tr(self.config.language, "bypass_save_error"))
            return
        # Persist first: a failed write must not claim the exemption survives relaunch.
        if self.engine.bypass(text, self.config.language):
            self.retry_at = None
            self.hide_reminder()
            self.refresh_status()

    def start_worker(self, function, result, failed=None):
        worker = Worker(function, self)
        self.workers.add(worker)
        worker.result.connect(result)
        if failed:
            worker.failed.connect(failed)
        worker.finished.connect(lambda w=worker: self.worker_finished(w))
        worker.start()
        return worker

    def worker_finished(self, worker):
        self.workers.discard(worker)
        worker.deleteLater()
        if self.closing and not self.workers:
            self.app.quit()

    def dispatch_shutdown(self):
        if self.shutdown_busy:
            return
        self.shutdown_busy = True
        if self.reminder:
            self.reminder.set_remaining(0)
            self.reminder.set_busy(True)
            self.reminder.message.setText(tr(self.config.language, "requesting"))
        self.start_worker(lambda: platforms.request_shutdown(self.demo), self.shutdown_result,
                          lambda _: self.shutdown_result((False, "Worker error")))

    def shutdown_result(self, result):
        self.shutdown_busy = False
        ok, detail = result
        self.shutdown_failed = not ok
        if not ok:
            LOG.warning("Shutdown request failed: %s", detail)
        if self.closing:
            return
        # No repeated permission requests on failure; retry is user-initiated.
        self.retry_at = time.monotonic() + 60 if ok else None
        if self.reminder:
            self.reminder.set_busy(False)
            key = "preview_done" if self.demo else "requested" if ok else "shutdown_failed"
            self.reminder.message.setText(tr(self.config.language, key))
        self.refresh_status()

    def show_preview(self):
        language = self.settings.language if self.settings else self.config.language
        if self.preview is None:
            self.preview = ReminderDialog(language, preview=True)
            self.preview.snooze_requested.connect(self.snooze_preview)
            self.preview.bypass_requested.connect(lambda _: self.close_preview())
            self.preview.preview_closed.connect(self.close_preview)
        self.preview.retranslate(language)
        self.preview.message.clear()
        self.preview_deadline = time.monotonic() + 60
        self.preview_snooze_until = None
        self.preview.set_remaining(60)
        self.preview.present()
        self.preview_timer.start()

    def snooze_preview(self):
        self.preview.hide()
        self.preview_deadline = None
        self.preview_snooze_until = time.monotonic() + 60

    def tick_preview(self):
        now = time.monotonic()
        if self.preview_snooze_until is not None and now >= self.preview_snooze_until:
            self.preview_snooze_until = None
            self.preview_deadline = now + 60
            self.preview.phrase_input.clear()
            self.preview.present()
        if self.preview_deadline is not None:
            import math
            remaining = max(0, math.ceil(self.preview_deadline - now))
            self.preview.set_remaining(remaining)
            if remaining == 0:
                self.preview_timer.stop()
                self.preview.message.setText(tr(self.preview.language, "preview_done"))

    def close_preview(self):
        self.preview_timer.stop()
        self.preview_deadline = self.preview_snooze_until = None
        if self.preview:
            self.preview.hide()
        if self.preview_only and not self.closing:
            self.stop()

    def check_updates(self, repository):
        settings = self.settings
        settings.check_button.setEnabled(False)
        settings.release_button.hide()
        settings.update_message.setText(tr(settings.language, "checking"))
        self.release_url = None
        self.start_worker(lambda: check_update(repository), self.update_result, self.update_error)

    def update_result(self, release):
        if self.closing:
            return
        settings = self.settings
        settings.check_button.setEnabled(True)
        settings.update_message.setText(tr(settings.language, "available", version=release.version) if release.newer
                                       else tr(settings.language, "latest"))
        self.release_url = release.url if release.newer else None
        settings.release_button.setVisible(release.newer)

    def update_error(self, key):
        if self.closing:
            return
        settings = self.settings
        settings.check_button.setEnabled(True)
        settings.update_message.setText(tr(settings.language, "update_failed", reason=tr(settings.language, key)))

    def open_release(self):
        if self.release_url:
            QDesktopServices.openUrl(QUrl(self.release_url))

    def confirm_quit(self):
        language = self.settings.language
        box = QMessageBox(self.settings)
        box.setWindowTitle(tr(language, "quit_title"))
        box.setText(tr(language, "quit_body"))
        quit_button = box.addButton(tr(language, "yes_quit"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr(language, "cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == quit_button:
            self.stop()

    def stop(self):
        self.closing = True
        self.timer.stop()
        self.close_preview()
        self.hide_reminder()
        if self.settings:
            self.settings.hide()
        # Let bounded network/OS calls finish instead of destroying a live thread.
        if not self.workers:
            self.app.quit()


def main(argv=None):
    parser = argparse.ArgumentParser(description="NightGuard — local bedtime protection")
    parser.add_argument("--background", action="store_true", help="Run without a settings window or tray")
    parser.add_argument("--stop", action="store_true", help="Stop the existing background instance")
    parser.add_argument("--preview", action="store_true", help="Show a safe reminder preview")
    parser.add_argument("--demo", action="store_true", help="Isolated demo: no shutdown and no auto-start changes")
    parser.add_argument("--language", choices=["zh", "en"], help="Initial interface language")
    parser.add_argument("--data-dir", type=Path, help="Use a separate configuration directory")
    args = parser.parse_args(argv)
    if args.preview:
        args.demo = True  # CLI preview must never activate the real scheduler.
    root = args.data_dir.resolve() if args.data_dir else data_directory()
    if args.demo:
        root = root / "demo"
    store = Store(root)
    handler = RotatingFileHandler(root / "nightguard.log", maxBytes=300_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    # Never log placeholder input, secrets, or file contents.
    app = QApplication([sys.argv[0]])
    app.setApplicationName("NightGuard")
    app.setOrganizationName("NightGuard")
    app.setQuitOnLastWindowClosed(False)
    platforms.hide_macos_dock()
    instance = Instance(root)
    if args.stop:
        return 0 if instance.send("stop") else 1
    if not instance.acquire():
        if args.background:
            return 0
        return 0 if instance.send("preview" if args.preview else "settings") else 1
    controller = Controller(app, store, args.demo, args.language)
    platforms.install_macos_reopen_handler(controller.reopen_requested.emit)
    instance.command.connect(controller.command)
    app.aboutToQuit.connect(instance.close)
    signal.signal(signal.SIGINT, lambda *_: controller.stop())
    signal.signal(signal.SIGTERM, lambda *_: controller.stop())
    if args.preview:
        controller.preview_only = True
        controller.show_preview()
    elif not args.background:
        controller.show_settings()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
