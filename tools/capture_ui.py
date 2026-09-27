"""Render actual Qt widgets only. Never instantiates the background controller."""
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from nightguard.storage import Config
from nightguard.ui import SettingsWindow, ReminderDialog

output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/screenshots")
output.mkdir(parents=True, exist_ok=True)
app = QApplication([])
for language in ("zh", "en"):
    settings = SettingsWindow(Config(enabled=True, language=language), demo=False)
    settings.status.setText("等待守护时段" if language == "zh" else "Waiting for quiet hours")
    settings.show()
    app.processEvents()
    for page in range(3):
        settings.select_page(page)
        app.processEvents()
        path = output / f"settings-{language}-{page}.png"
        assert settings.grab().save(str(path))
        print(path.resolve())
    reminder = ReminderDialog(language, preview=False)
    reminder.set_remaining(48)
    reminder.present()
    app.processEvents()
    path = output / f"reminder-{language}.png"
    assert reminder.grab().save(str(path))
    print(path.resolve())
    reminder.hide()
    settings.hide()
    reminder.deleteLater()
    settings.deleteLater()
app.processEvents()
