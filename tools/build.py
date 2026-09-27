"""Build on the target OS; produce a relocatable folder archive, never enable it."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nightguard import __version__
from nightguard.build_info import DEFAULT_UPDATE_REPO
from nightguard.updates import validate_repo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-repo", default=os.environ.get("NIGHTGUARD_UPDATE_REPO", DEFAULT_UPDATE_REPO),
                        help="Public owner/repository; blank disables unconfigured network requests")
    args = parser.parse_args()
    repo = validate_repo(args.update_repo) if args.update_repo else ""
    metadata = ROOT / "nightguard/build_info.py"
    original = metadata.read_bytes()
    try:
        metadata.write_text("# Generated for this build.\nDEFAULT_UPDATE_REPO = " + json.dumps(repo) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "NightGuard.spec"], cwd=ROOT, check=True)
    finally:
        metadata.write_bytes(original)
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    arch = platform.machine().lower()
    arch = {"amd64": "x86_64", "aarch64": "arm64"}.get(arch, arch)
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    name = f"NightGuard-{__version__}-{system}-{arch}"
    bundle = ROOT / "dist/NightGuard"
    if sys.platform == "darwin":
        archive = artifacts / (name + ".zip")
        subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(ROOT / "dist/NightGuard.app"), str(archive)], check=True)
    else:
        for file in ("README.md", "README.en.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
            shutil.copy2(ROOT / file, bundle / file)
        shutil.copytree(ROOT / "licenses", bundle / "licenses", dirs_exist_ok=True)
        shutil.copytree(ROOT / "docs", bundle / "docs", dirs_exist_ok=True)
        if sys.platform == "win32":
            archive = Path(shutil.make_archive(str(artifacts / name), "zip", ROOT / "dist", "NightGuard"))
        else:
            archive = artifacts / (name + ".tar.gz")
            with tarfile.open(archive, "w:gz") as output:
                output.add(bundle, arcname="NightGuard")
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="utf-8")
    print(f"BUILD_OK {archive}", flush=True)
    print(f"CHECKSUM {checksum}", flush=True)


if __name__ == "__main__":
    main()
