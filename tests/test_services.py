import json
import plistlib
import subprocess
from unittest.mock import patch

import pytest

from nightguard import platforms
from nightguard.storage import Store, Config
from nightguard.updates import UpdateError, check_update, parse_release, validate_repo
from nightguard.i18n import STRINGS


def test_store_roundtrip_and_bypass(tmp_path):
    store = Store(tmp_path)
    config = Config(start="23:00", end="06:00", enabled=True, language="zh")
    store.save(config)
    assert store.load() == config
    store.save_bypass("2026-09-27|23:00|06:00")
    assert store.load_bypass() == "2026-09-27|23:00|06:00"
    assert not list(tmp_path.glob(".*.json.*"))


@pytest.mark.parametrize("data", ["{broken", '[]', '{"start":"25:00"}', '{"enabled":"true"}', '{"language":"fr"}'])
def test_bad_config_fails_closed(tmp_path, data):
    (tmp_path / "config.json").write_text(data)
    store = Store(tmp_path)
    assert store.load().enabled is False
    assert store.warning


def test_first_launch_safe(tmp_path):
    config = Store(tmp_path).load()
    assert not config.enabled
    assert config.autostart


def test_write_failure_preserves_old_config(tmp_path):
    store = Store(tmp_path)
    store.save(Config(language="en"))
    with patch("nightguard.storage.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            store.save(Config(language="zh", enabled=True))
    assert store.load().language == "en"
    assert not list(tmp_path.glob(".*.json.*"))


def test_all_translations_have_same_keys():
    assert STRINGS["en"].keys() == STRINGS["zh"].keys()


def test_windows_shutdown_is_immediate_non_force_request():
    command = platforms.shutdown_command("win32")
    assert command[1:] == ["/s", "/t", "0"]
    assert "/f" not in command


def test_linux_shutdown_respects_policy():
    command = platforms.shutdown_command("linux")
    assert command[-3:] == ["PowerOff", "b", "true"]
    assert "sudo" not in command
    assert "--force" not in command


def test_mac_shutdown_normal_apple_event():
    command = platforms.shutdown_command("darwin")
    assert command[0] == "/usr/bin/osascript"
    assert command[-1] == 'tell application "System Events" to shut down'


def test_demo_never_starts_shutdown_process():
    with patch("nightguard.platforms.subprocess.run") as run:
        assert platforms.request_shutdown(True) == (True, "demo")
        run.assert_not_called()


def test_denied_shutdown_is_reported():
    with patch("nightguard.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 1, b"", b"denied")):
        assert platforms.request_shutdown() == (False, "denied")


def test_timeout_is_reported():
    with patch("nightguard.platforms.subprocess.run", side_effect=subprocess.TimeoutExpired([], 35)):
        assert platforms.request_shutdown()[0] is False


def test_mac_agent_has_no_restart_loop():
    args = ["/Applications/Night Guard.app/Contents/MacOS/NightGuard", "--background"]
    payload = plistlib.loads(platforms.autostart_payload(args, "darwin"))
    assert payload["ProgramArguments"] == args
    assert payload["RunAtLoad"] is True
    assert "KeepAlive" not in payload
    assert payload["LimitLoadToSessionType"] == "Aqua"


def test_linux_desktop_entry_quotes_paths():
    payload = platforms.autostart_payload(["/a path/晚安", "--background"], "linux").decode()
    assert 'Exec="/bin/sh" "-c"' in payload
    assert '"/a path/晚安" "--background"' in payload
    assert "Terminal=false" in payload
    assert "Hidden=true" not in payload
    assert "%%" in platforms.desktop_quote("/path/100%/app")
    with pytest.raises(ValueError):
        platforms.desktop_quote("/a\npath")


def test_autostart_install_uninstall_only_test_home(tmp_path, monkeypatch):
    monkeypatch.setattr(platforms.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(platforms, "launch_command", lambda: ["/test/NightGuard", "--background"])
    platforms.set_autostart(True)
    assert platforms.autostart_installed()
    assert (tmp_path / "autostart/nightguard.desktop").exists()
    platforms.set_autostart(False)
    assert not platforms.autostart_installed()


@pytest.mark.parametrize("repo", ["", "https://github.com/a/b", "../../secret", "a/b/c", "a/b?query", "a/b\nheader"])
def test_invalid_repository(repo):
    with pytest.raises(UpdateError):
        validate_repo(repo)


def release(tag="v1.2.0", url="https://github.com/example/nightguard/releases/tag/v1.2.0", **kwargs):
    return dict(tag_name=tag, html_url=url, **kwargs)


def test_version_comparison():
    assert parse_release(release(), "example/nightguard", "1.0.0").newer
    assert not parse_release(release("v1.0.0"), "example/nightguard", "1.0.0").newer
    assert parse_release(release("v1.10.0"), "example/nightguard", "1.9.0").newer


@pytest.mark.parametrize("payload", [release("latest"), release("v2.0.0rc1"), release(prerelease=True), release(draft=True), release(url="javascript:alert(1)"), release(url="https://evil.test/app"), release(url="https://github.com/other/app/releases/tag/v1"), {}, []])
def test_reject_bad_release(payload):
    with pytest.raises(UpdateError):
        parse_release(payload, "example/nightguard")


def test_no_network_without_repo():
    with patch("nightguard.updates.urlopen") as urlopen:
        with pytest.raises(UpdateError, match="no_repo"):
            check_update("")
        urlopen.assert_not_called()


def test_update_success_mock_network():
    with patch("nightguard.updates.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(release()).encode()
        result = check_update("example/nightguard")
        assert result.version == "1.2.0"
        assert urlopen.call_args.kwargs["timeout"] == 12
