from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version
from . import __version__


class UpdateError(Exception):
    """Message is a translation key, not server-controlled UI text."""


def validate_repo(repo: str) -> str:
    repo = repo.strip()
    if not repo:
        raise UpdateError("no_repo")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", repo):
        raise UpdateError("repo_invalid")
    return repo


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    newer: bool


def parse_release(payload: dict, repo: str, current: str = __version__) -> Release:
    try:
        tag = payload["tag_name"]
        if not isinstance(tag, str) or len(tag) > 64 or payload.get("draft") or payload.get("prerelease"):
            raise ValueError("Invalid stable release")
        version = Version(tag.removeprefix("v"))
        if version.is_prerelease or version.is_devrelease:
            raise ValueError("Not a stable version")
        url = payload["html_url"]
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.netloc != "github.com"
                or not parsed.path.lower().startswith(f"/{repo.lower()}/releases/tag/")):
            raise ValueError("Untrusted release URL")
        return Release(str(version), url, version > Version(current))
    except (KeyError, TypeError, ValueError, InvalidVersion, AttributeError) as error:
        raise UpdateError("bad_release") from error


def check_update(repo: str) -> Release:
    repo = validate_repo(repo)
    request = Request(f"https://api.github.com/repos/{repo}/releases/latest", headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"NightGuard/{__version__}",
    })
    try:
        with urlopen(request, timeout=12) as response:
            data = response.read(1_000_001)
            if len(data) > 1_000_000:
                raise UpdateError("bad_release")
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise UpdateError("bad_release")
        return parse_release(payload, repo)
    except HTTPError as error:
        key = "not_found" if error.code == 404 else "rate_limit" if error.code in (403, 429) else "network"
        raise UpdateError(key) from error
    except (URLError, TimeoutError, OSError) as error:
        raise UpdateError("network") from error
    except (ValueError, UnicodeDecodeError) as error:
        raise UpdateError("bad_release") from error
