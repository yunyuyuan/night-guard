import json
from pathlib import Path
import subprocess

import pytest

from tools import release


@pytest.mark.parametrize("tag,version,prerelease", [
    ("v1.0.0", "1.0.0", False),
    ("v12.30.40", "12.30.40", False),
    ("v1.2.0-alpha.0", "1.2.0a0", True),
    ("v1.2.0-beta.2", "1.2.0b2", True),
    ("v1.2.0-rc.1", "1.2.0rc1", True),
])
def test_tag_metadata(tag, version, prerelease):
    assert release.tag_metadata(tag) == release.Metadata(version, prerelease)


@pytest.mark.parametrize("tag", ["1.0.0", "v1", "v1.2", "v01.2.3", "v1.2.3-rc.01", "v1.2.3+local", "v1.2.3;rm", "v1.2.3\n", "v1.2.3-dev.1"])
def test_invalid_tag(tag):
    with pytest.raises(ValueError):
        release.tag_metadata(tag)


def test_prepare_single_version_source(tmp_path):
    directory = tmp_path / "nightguard"
    directory.mkdir()
    init = directory / "__init__.py"
    init.write_text('"""NightGuard."""\n__version__ = "1.0.0"\n')
    cache = directory / "__pycache__"
    cache.mkdir()
    (cache / "__init__.cpython-312.pyc").write_bytes(b"stale")
    release.prepare_version("2.0.0rc1", tmp_path)
    assert '__version__ = "2.0.0rc1"' in init.read_text()
    assert not list(cache.iterdir())


@pytest.mark.parametrize("version", ["1.2", "1.2.3.dev1", "1.2.3.post1", "1.2.3+local"])
def test_prepare_rejects_non_release_versions(tmp_path, version):
    with pytest.raises(ValueError):
        release.prepare_version(version, tmp_path)


def populate(directory: Path, version="1.0.0"):
    for target, suffix in release.TARGETS.items():
        name = f"NightGuard-{version}-{target}{suffix}"
        archive = directory / name
        archive.write_bytes((target + version).encode())
        (directory / f"{name}.sha256").write_text(f"{release.sha256(archive)}  {name}\n")


def test_collect_all_four_packages(tmp_path):
    populate(tmp_path)
    assets = release.collect_assets(tmp_path, "1.0.0")
    assert len(assets) == 9
    assert len((tmp_path / "SHA256SUMS.txt").read_text().splitlines()) == 4


def test_missing_architecture_blocks_release(tmp_path):
    populate(tmp_path)
    (tmp_path / "NightGuard-1.0.0-macos-arm64.zip").unlink()
    with pytest.raises(ValueError, match="exactly four"):
        release.collect_assets(tmp_path, "1.0.0")


def test_bad_digest_blocks_release(tmp_path):
    populate(tmp_path)
    (tmp_path / "NightGuard-1.0.0-windows-x86_64.zip").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        release.collect_assets(tmp_path, "1.0.0")


def test_wrong_version_blocks_release(tmp_path):
    populate(tmp_path)
    with pytest.raises(ValueError, match="exactly four"):
        release.collect_assets(tmp_path, "2.0.0")


@pytest.mark.parametrize("tag,version,is_prerelease", [("v1.0.0", "1.0.0", False), ("v1.1.0-rc.1", "1.1.0rc1", True)])
def test_publish_uploads_before_making_public(tmp_path, monkeypatch, tag, version, is_prerelease):
    populate(tmp_path, version)
    calls = []
    def fake_gh(*args, check=True):
        calls.append(args)
        if args[0] == "api":
            return subprocess.CompletedProcess(args, 1, "", "gh: Not Found (HTTP 404)")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(release, "gh", fake_gh)
    release.publish_release("owner/repo", tag, tmp_path)
    assert [call[:2] for call in calls[1:]] == [("release", "create"), ("release", "upload"), ("release", "edit")]
    assert "--draft" in calls[1]
    assert "--verify-tag" in calls[1]
    assert ("--prerelease" in calls[1]) == is_prerelease
    assert "--draft=false" in calls[-1]


def test_lookup_permission_failure_never_creates_release(tmp_path, monkeypatch):
    populate(tmp_path)
    calls = []
    def fake_gh(*args, check=True):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "gh: Forbidden (HTTP 403)")
    monkeypatch.setattr(release, "gh", fake_gh)
    with pytest.raises(RuntimeError, match="403"):
        release.publish_release("owner/repo", "v1.0.0", tmp_path)
    assert len(calls) == 1


def test_failed_upload_leaves_draft_unpublished(tmp_path, monkeypatch):
    populate(tmp_path)
    calls = []
    def fake_gh(*args, check=True):
        calls.append(args)
        if args[0] == "api":
            return subprocess.CompletedProcess(args, 1, "", "HTTP 404")
        if args[:2] == ("release", "upload"):
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(release, "gh", fake_gh)
    with pytest.raises(subprocess.CalledProcessError):
        release.publish_release("owner/repo", "v1.0.0", tmp_path)
    assert not any(args[:2] == ("release", "edit") for args in calls)


def test_rerun_recovers_existing_draft(tmp_path, monkeypatch):
    populate(tmp_path)
    calls = []
    def fake_gh(*args, check=True):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps({"draft": True}), "")
    monkeypatch.setattr(release, "gh", fake_gh)
    release.publish_release("owner/repo", "v1.0.0", tmp_path)
    assert not any(args[:2] == ("release", "create") for args in calls)
    assert calls[-1][:2] == ("release", "edit")


def test_published_release_is_never_overwritten(tmp_path, monkeypatch):
    populate(tmp_path)
    assets = release.collect_assets(tmp_path, "1.0.0")
    calls = []
    def fake_gh(*args, check=True):
        calls.append(args)
        body = {"draft": False, "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
                "assets": [{"name": path.name, "size": path.stat().st_size} for path in assets]}
        return subprocess.CompletedProcess(args, 0, json.dumps(body), "")
    monkeypatch.setattr(release, "gh", fake_gh)
    release.publish_release("owner/repo", "v1.0.0", tmp_path)
    assert len(calls) == 1
