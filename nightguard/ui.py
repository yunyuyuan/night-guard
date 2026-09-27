from __future__ import annotations

from dataclasses import replace
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QProgressBar, QPushButton, QStackedWidget, QTimeEdit,
    QVBoxLayout, QWidget,
)
from . import __version__
from .i18n import placeholder, tr
from .storage import Config

STYLE = """
QWidget { background: #121a23; color: #ecf0ec; font-family: 'Inter', 'Segoe UI', 'Noto Sans CJK SC', 'PingFang SC', sans-serif; font-size: 14px; }
QMainWindow, QDialog { background: #121a23; }
QLabel { background: transparent; }
QLabel#brand { font-size: 19px; font-weight: 700; }
QLabel#monogram { background: #b9dac7; color: #182c26; border-radius: 14px; font-size: 18px; font-weight: 700; }
QLabel#title { font-size: 27px; font-weight: 650; }
QLabel#popupTitle { font-size: 30px; font-weight: 650; }
QLabel#muted { color: #a3afb9; font-size: 13px; }
QLabel#kicker { color: #b9dac7; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#section { font-size: 16px; font-weight: 600; }
QLabel#status { color: #b9dac7; font-size: 12px; }
QLabel#notice { color: #dec89f; background: #292920; border: 1px solid #444232; border-radius: 9px; padding: 12px; font-size: 12px; }
QLabel#feedback { color: #b9dac7; font-size: 12px; }
QLabel#counter { color: #d2e8da; font-size: 68px; font-weight: 500; font-family: 'Cascadia Mono', 'DejaVu Sans Mono', monospace; }
QFrame#sidebar { background: #0e151e; border-right: 1px solid #26333d; }
QFrame#card { background: #1a2530; border: 1px solid #2b3944; border-radius: 12px; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QPushButton { background: #23313d; border: 1px solid #394956; border-radius: 8px; padding: 11px 18px; font-weight: 600; }
QPushButton:hover { background: #304451; border-color: #739588; }
QPushButton:pressed { background: #3b514f; }
QPushButton:disabled { background: #1a252e; color: #71808a; border-color: #2a3945; }
QPushButton#primary { background: #b9dac7; color: #172c24; border-color: #b9dac7; }
QPushButton#primary:hover { background: #d3ebde; }
QPushButton#nav { background: transparent; color: #98a7b5; border: none; text-align: left; padding: 13px 12px; font-size: 13px; }
QPushButton#nav:checked { background: #22342f; color: #c5e6d3; }
QPushButton#nav:hover { background: #1e2b33; }
QPushButton#danger { background: transparent; color: #deb6a8; border-color: #604a48; }
QLineEdit, QComboBox, QTimeEdit { background: #101921; color: #eff4ef; border: 1px solid #41525e; border-radius: 8px; padding: 10px 12px; selection-background-color: #426757; }
QLineEdit:focus, QComboBox:focus, QTimeEdit:focus { border: 1px solid #b9dac7; }
QTimeEdit { font-size: 28px; min-width: 150px; padding: 12px 18px; }
QTimeEdit::up-button, QTimeEdit::down-button { width: 22px; }
QComboBox { min-width: 200px; }
QComboBox QAbstractItemView { background: #1a2530; selection-background-color: #385147; }
QCheckBox { spacing: 12px; font-size: 15px; font-weight: 600; }
QCheckBox::indicator { width: 21px; height: 21px; border: 1px solid #617481; border-radius: 5px; background: #101921; }
QCheckBox::indicator:checked { background: #b9dac7; border: 5px solid #638b74; }
QProgressBar { background: #2a3945; border: none; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #b9dac7; border-radius: 3px; }
QToolTip { background: #23313d; color: #eff4ef; border: 1px solid #41525e; }
"""


def label(text: str = "", name: str = "", wrap: bool = True) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def card(parent_layout, spacing=12):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(spacing)
    parent_layout.addWidget(frame)
    return layout


class SettingsWindow(QMainWindow):
    save_requested = Signal(object)
    preview_requested = Signal()
    quit_requested = Signal()
    check_requested = Signal(str)
    release_requested = Signal()

    def __init__(self, config: Config, demo=False, config_warning=False):
        super().__init__()
        self.language = config.language
        self.demo = demo
        self.config_warning = config_warning
        self.text_refs = []
        self.setMinimumSize(910, 730)
        self.resize(1020, 790)
        self.setStyleSheet(STYLE)
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(222)
        sidebar = QVBoxLayout(side)
        sidebar.setContentsMargins(22, 30, 20, 24)
        sidebar.setSpacing(10)
        monogram = label("NG", "monogram", False)
        monogram.setFixedSize(46, 46)
        monogram.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar.addWidget(monogram)
        sidebar.addSpacing(8)
        sidebar.addWidget(label("NightGuard", "brand", False))
        sidebar.addWidget(label("A LITTLE LESS LATE", "kicker", False))
        sidebar.addSpacing(36)
        self.nav = []
        for index, key in enumerate(("general", "system", "updates")):
            button = self.button(key, "nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.select_page(i))
            sidebar.addWidget(button)
            self.nav.append(button)
        sidebar.addStretch()
        sidebar.addWidget(label("LOCAL FIRST\nWindows · Linux · macOS", "muted"))
        sidebar.addSpacing(12)
        sidebar.addWidget(label(f"v{__version__}", "muted"))
        outer.addWidget(side)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(32, 30, 32, 24)
        body.setSpacing(16)
        body.addWidget(label("NIGHTGUARD / SETTINGS", "kicker"))
        body.addWidget(self.text("tagline", "title"))
        self.notice = self.text("demo_badge" if demo else "corrupt" if config_warning else "first_run", "notice")
        self.notice.setVisible(demo or config_warning or not config.enabled)
        body.addWidget(self.notice)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        self.build_general(config)
        self.build_system(config)
        self.build_updates(config)
        self.feedback = label("", "feedback")
        self.feedback.setMinimumHeight(20)
        body.addWidget(self.feedback)
        footer = QHBoxLayout()
        self.status = label("", "status")
        footer.addWidget(self.status, 1)
        self.preview_button = self.button("preview")
        self.preview_button.clicked.connect(self.preview_requested)
        footer.addWidget(self.preview_button)
        self.save_button = self.button("save", "primary")
        self.save_button.clicked.connect(self.save)
        footer.addWidget(self.save_button)
        body.addLayout(footer)
        outer.addWidget(content, 1)
        self.translate()
        self.select_page(0)
        self.language_combo.currentIndexChanged.connect(self.language_changed)

    def text(self, key, name=""):
        widget = label(tr(self.language, key), name)
        self.text_refs.append((widget, key))
        return widget

    def button(self, key, name=""):
        widget = QPushButton(tr(self.language, key))
        widget.setObjectName(name)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_refs.append((widget, key))
        return widget

    def page(self, title, desc):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.text(title, "section"))
        layout.addWidget(self.text(desc, "muted"))
        self.stack.addWidget(page)
        return layout

    def build_general(self, config):
        layout = self.page("schedule_title", "schedule_desc")
        controls = card(layout)
        self.enabled_box = QCheckBox()
        self.enabled_box.setChecked(config.enabled)
        self.text_refs.append((self.enabled_box, "enabled"))
        controls.addWidget(self.enabled_box)
        controls.addWidget(self.text("enabled_desc", "muted"))
        times = QHBoxLayout()
        times.setSpacing(22)
        for key, name in (("start", "start_time"), ("end", "end_time")):
            column = QVBoxLayout()
            column.addWidget(self.text(key, "muted"))
            field = QTimeEdit(QTime.fromString(getattr(config, key), "HH:mm"))
            field.setDisplayFormat("HH:mm")
            field.setAccessibleName(tr(self.language, key))
            setattr(self, name, field)
            column.addWidget(field)
            times.addLayout(column, 1)
        controls.addLayout(times)
        controls.addWidget(self.text("local", "muted"))
        rules = card(layout)
        rules.addWidget(self.text("flow_title", "section"))
        rules.addWidget(self.text("flow", "muted"))
        layout.addWidget(self.text("safety", "muted"))
        layout.addStretch()

    def build_system(self, config):
        layout = self.page("background_title", "background_desc")
        auto = card(layout)
        self.autostart_box = QCheckBox()
        self.autostart_box.setChecked(config.autostart)
        self.text_refs.append((self.autostart_box, "autostart"))
        auto.addWidget(self.autostart_box)
        auto.addWidget(self.text("autostart_desc", "muted"))
        language = card(layout)
        language.addWidget(self.text("language", "section"))
        language.addWidget(self.text("language_desc", "muted"))
        self.language_combo = QComboBox()
        self.language_combo.addItem("简体中文", "zh")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(0 if config.language == "zh" else 1)
        language.addWidget(self.language_combo)
        layout.addWidget(self.text("background_note", "muted"))
        layout.addStretch()
        quit_button = self.button("quit", "danger")
        quit_button.clicked.connect(self.quit_requested)
        layout.addWidget(quit_button, 0, Qt.AlignmentFlag.AlignLeft)

    def build_updates(self, config):
        layout = self.page("version_title", "version_desc")
        version = card(layout)
        version.addWidget(self.text("current", "muted"))
        version.addWidget(label(f"NightGuard  {__version__}", "section"))
        repo = card(layout)
        repo.addWidget(self.text("repo", "section"))
        self.repo_input = QLineEdit(config.update_repo)
        self.repo_input.setMaxLength(160)
        repo.addWidget(self.repo_input)
        repo.addWidget(self.text("repo_help", "muted"))
        row = QHBoxLayout()
        self.check_button = self.button("check")
        self.check_button.clicked.connect(lambda: self.check_requested.emit(self.repo_input.text()))
        row.addWidget(self.check_button)
        row.addStretch()
        repo.addLayout(row)
        self.update_message = label("", "muted")
        layout.addWidget(self.update_message)
        self.release_button = self.button("open_release", "primary")
        self.release_button.clicked.connect(self.release_requested)
        self.release_button.hide()
        layout.addWidget(self.release_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

    def select_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(index == i)

    def language_changed(self):
        self.language = self.language_combo.currentData()
        self.feedback.clear()
        self.update_message.clear()
        self.translate()

    def translate(self):
        self.setWindowTitle(tr(self.language, "name") + " — " + tr(self.language, "settings"))
        for widget, key in self.text_refs:
            value = tr(self.language, key)
            widget.setText(value.replace("&", "&&") if isinstance(widget, QPushButton) else value)
        self.repo_input.setPlaceholderText(tr(self.language, "repo_placeholder"))
        self.start_time.setAccessibleName(tr(self.language, "start"))
        self.end_time.setAccessibleName(tr(self.language, "end"))
        self.language_combo.setAccessibleName(tr(self.language, "language"))

    def save(self):
        self.save_requested.emit(Config(
            start=self.start_time.time().toString("HH:mm"),
            end=self.end_time.time().toString("HH:mm"),
            enabled=self.enabled_box.isChecked(), autostart=self.autostart_box.isChecked(),
            language=self.language_combo.currentData(), update_repo=self.repo_input.text().strip(),
        ))

    def closeEvent(self, event: QCloseEvent):
        event.ignore()
        self.hide()


class ReminderDialog(QDialog):
    snooze_requested = Signal()
    bypass_requested = Signal(str)
    preview_closed = Signal()

    def __init__(self, language="en", preview=False):
        super().__init__()
        self.language = language
        self.preview = preview
        self.allow_close = False
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setMinimumWidth(630)
        self.resize(660, 650)
        self.setStyleSheet(STYLE)
        self.refs = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(16)
        layout.addWidget(self.text("warning_kicker", "kicker"))
        if preview:
            layout.addWidget(self.text("preview_badge", "notice"))
        layout.addWidget(self.text("warning_title", "popupTitle"))
        layout.addWidget(self.text("warning_desc", "muted"))
        self.counter = label("01:00", "counter", False)
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.counter)
        caption = self.text("seconds", "muted")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)
        self.progress = QProgressBar()
        self.progress.setRange(0, 60)
        self.progress.setValue(60)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.snooze_button = QPushButton()
        self.snooze_button.setObjectName("primary")
        self.refs.append((self.snooze_button, "snooze"))
        self.snooze_button.clicked.connect(self.snooze_requested)
        layout.addWidget(self.snooze_button)
        layout.addSpacing(4)
        layout.addWidget(self.text("bypass_hint", "muted"))
        self.phrase_input = QLineEdit()
        self.phrase_input.setMaxLength(100)
        self.phrase_input.setMinimumHeight(45)
        self.phrase_input.setFont(QFont("", 11))
        self.phrase_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.phrase_input.textChanged.connect(self.update_bypass_button)
        self.phrase_input.returnPressed.connect(self.submit_bypass)
        layout.addWidget(self.phrase_input)
        self.bypass_button = QPushButton()
        self.refs.append((self.bypass_button, "bypass"))
        self.bypass_button.setEnabled(False)
        self.bypass_button.clicked.connect(self.submit_bypass)
        layout.addWidget(self.bypass_button)
        layout.addWidget(self.text("bypass_note", "muted"))
        self.message = label("", "feedback")
        layout.addWidget(self.message)
        if preview:
            close = QPushButton()
            self.refs.append((close, "preview_close"))
            close.clicked.connect(self.reject)
            layout.addWidget(close)
        self.retranslate(language)
        self.snooze_button.setFocus()

    def text(self, key, name):
        widget = label(tr(self.language, key), name)
        self.refs.append((widget, key))
        return widget

    def retranslate(self, language):
        self.language = language
        self.setWindowTitle(tr(language, "name"))
        for widget, key in self.refs:
            widget.setText(tr(language, key))
        self.phrase_input.clear()
        self.phrase_input.setPlaceholderText(placeholder(language))
        self.phrase_input.setAccessibleName(tr(language, "bypass_hint"))
        self.update_bypass_button()

    def update_bypass_button(self):
        self.bypass_button.setEnabled(self.phrase_input.text() == placeholder(self.language)
                                      and self.phrase_input.isEnabled())

    def submit_bypass(self):
        if self.bypass_button.isEnabled():
            self.bypass_requested.emit(self.phrase_input.text())

    def set_remaining(self, seconds):
        self.counter.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")
        self.progress.setValue(seconds)

    def set_busy(self, busy):
        self.snooze_button.setEnabled(not busy)
        self.phrase_input.setEnabled(not busy)
        self.update_bypass_button()

    def present(self):
        self.adjustSize()
        screen = self.screen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())
        self.show()
        self.raise_()
        self.activateWindow()

    def reject(self):
        if self.preview or self.allow_close:
            self.preview_closed.emit()
            super().reject()
        # Escape and window-close must not silently bypass a live countdown.

    def closeEvent(self, event):
        if self.preview or self.allow_close:
            self.preview_closed.emit()
            event.accept()
        else:
            event.ignore()
