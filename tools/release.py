"""Deterministic release helpers. Publishing is called only by the tag CI job."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
NUMBER = r"(?:0|[1-9]\d*)"
TAG = re.compile(rf"v(?P<base>{NUMBER}\.{NUMBER}\.{NUMBER})(?:-(?P<kind>alpha|beta|rc)\.(?P<serial>{NUMBER}))?")
TARGETS = {"linux-x86_64": ".tar.gz", "windows-x86_64": ".zip", "macos-x86_64": ".zip", "macos-arm64": ".zip"}


@dataclass(frozen=True)
class Metadata:
    version: str
    prerelease: bool


def tag_metadata(tag: str) -> Metadata:
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError("Use vX.Y.Z or vX.Y.Z-alpha.N / -beta.N / -rc.N (no leading zeroes)")
    version = match["base"]
    if match["kind"]:
        version += {"alpha": "a", "beta": "b", "rc": "rc"}[match["kind"]] + match["serial"]
    return Metadata(str(Version(version)), bool(match["kind"]))


def prepare_version(version: str, root: Path = ROOT):
    parsed = Version(version)
    if len(parsed.release) != 3 or parsed.is_devrelease or parsed.is_postrelease or parsed.local:
        raise ValueError("Release version must have three components and optional alpha/beta/rc suffix")
    path = root / "nightguard/__init__.py"
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(r'^__version__\s*=\s*[\'"][^\'"]+[\'"]\s*$',
                            f'__version__ = "{parsed}"', text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("Expected exactly one __version__ assignment")
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    # A same-length edit within one timestamp tick must not reuse a stale pyc.
    cache = path.parent / "__pycache__"
    for bytecode in cache.glob("__init__.*.pyc"):
        bytecode.unlink()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_assets(directory: Path, version: str) -> list[Path]:
    expected = {f"NightGuard-{version}-{target}{suffix}" for target, suffix in TARGETS.items()}
    actual = {path.name for path in directory.iterdir() if path.name.endswith((".zip", ".tar.gz"))}
    if actual != expected:
        raise ValueError(f"Expected exactly four native archives; missing={expected - actual}, unexpected={actual - expected}")
    lines = []
    assets = []
    for name in sorted(expected):
        archive = directory / name
        if archive.stat().st_size == 0:
            raise ValueError(f"Empty archive: {name}")
        line = f"{sha256(archive)}  {name}"
        checksum = directory / f"{name}.sha256"
        if checksum.read_text(encoding="utf-8").strip() != line:
            raise ValueError(f"Checksum mismatch: {name}")
        lines.append(line)
        assets.extend([archive, checksum])
    combined = directory / "SHA256SUMS.txt"
    combined.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return assets + [combined]


def gh(*arguments: str, check=True):
    return subprocess.run(["gh", *arguments], text=True, capture_output=True, check=check)


def publish_release(repository: str, tag: str, directory: Path):
    metadata = tag_metadata(tag)
    assets = collect_assets(directory, metadata.version)
    existing = gh("api", f"repos/{repository}/releases/tags/{tag}", check=False)
    if existing.returncode == 0:
        release = json.loads(existing.stdout)
        if not release["draft"]:
            # Do not mutate an already-published release, even if immutability is off.
            expected_sizes = {path.name: path.stat().st_size for path in assets}
            actual_sizes = {item["name"]: item["size"] for item in release["assets"]}
            if any(actual_sizes.get(name) != size for name, size in expected_sizes.items()):
                raise RuntimeError("Published release already exists with different assets; use a new version tag")
            print(f"Release already published; left unchanged: {release['html_url']}")
            return
    else:
        # A missing release is normal, but auth/network/other API errors must fail.
        if "HTTP 404" not in existing.stderr:
            raise RuntimeError(existing.stderr or "Release lookup failed")
        arguments = ["release", "create", tag, "--repo", repository, "--verify-tag", "--draft",
                     "--title", f"NightGuard {tag}", "--generate-notes"]
        if metadata.prerelease:
            arguments.append("--prerelease")
        gh(*arguments)
    # Upload before publishing: a failed transfer leaves a recoverable draft,
    # not a public release missing one of the native packages.
    gh("release", "upload", tag, "--repo", repository, "--clobber", *(str(path) for path in assets))
    gh("release", "edit", tag, "--repo", repository, "--draft=false",
       f"--prerelease={'true' if metadata.prerelease else 'false'}")
    print(f"Published https://github.com/{repository}/releases/tag/{tag}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    metadata = sub.add_parser("metadata")
    metadata.add_argument("--tag", default="")
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--version", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--version", required=True)
    collect.add_argument("--directory", type=Path, required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("--tag", required=True)
    publish.add_argument("--repository", required=True)
    publish.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "metadata":
        result = tag_metadata(args.tag) if args.tag else Metadata(runpy.run_path(str(ROOT / "nightguard/__init__.py"))["__version__"], False)
        values = {"version": result.version, "prerelease": str(result.prerelease).lower()}
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                for name, value in values.items():
                    stream.write(f"{name}={value}\n")
        print(json.dumps(values))
    elif args.command == "prepare":
        prepare_version(args.version)
        print(f"Build version: {args.version}")
    elif args.command == "collect":
        print("\n".join(str(path) for path in collect_assets(args.directory, args.version)))
    else:
        publish_release(args.repository, args.tag, args.directory)


if __name__ == "__main__":
    main()
