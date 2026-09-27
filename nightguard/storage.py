from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import locale
import os
import tempfile

from platformdirs import user_config_path
from .core import Schedule
from .build_info import DEFAULT_UPDATE_REPO


def default_language() -> str:
    language = locale.getlocale()[0] or os.environ.get("LANG", "en")
    return "zh" if language.lower().startswith(("zh", "chinese")) else "en"


def data_directory() -> Path:
    override = os.environ.get("NIGHTGUARD_DATA_DIR")
    return Path(override).expanduser().resolve() if override else user_config_path("NightGuard", appauthor=False)


@dataclass
class Config:
    start: str = "00:00"
    end: str = "06:00"
    enabled: bool = False  # First run only activates after an explicit Save.
    autostart: bool = True  # Saving uses a quiet per-user login agent by default.
    language: str = "en"
    update_repo: str = DEFAULT_UPDATE_REPO

    def validate(self):
        Schedule(self.start, self.end)
        if type(self.enabled) is not bool or type(self.autostart) is not bool:
            raise ValueError("Invalid boolean setting")
        if self.language not in ("en", "zh"):
            raise ValueError("Unsupported language")
        if not isinstance(self.update_repo, str) or len(self.update_repo) > 160:
            raise ValueError("Invalid update repository")


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or data_directory()
        self.root.mkdir(parents=True, exist_ok=True)
        self.warning = ""

    def load(self) -> Config:
        path = self.root / "config.json"
        if not path.exists():
            return Config(language=default_language())
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Config must be an object")
            values = {k: v for k, v in raw.items() if k in Config.__dataclass_fields__}
            config = Config(**values)
            config.validate()
            return config
        except (OSError, ValueError, TypeError) as error:
            # Never enable shutdown after corrupt/malformed configuration.
            self.warning = str(error)
            return Config(enabled=False, language=default_language())

    def save(self, config: Config):
        config.validate()
        self._atomic_write("config.json", asdict(config))

    def load_bypass(self) -> str | None:
        try:
            value = json.loads((self.root / "state.json").read_text(encoding="utf-8"))["bypass_session"]
            return value if isinstance(value, str) and len(value) <= 80 else None
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def save_bypass(self, session: str | None):
        self._atomic_write("state.json", {"bypass_session": session})

    def _atomic_write(self, name: str, value: dict):
        fd, tmp = tempfile.mkstemp(prefix=f".{name}.", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.root / name)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
