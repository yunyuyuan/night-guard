"""Package source and any previously built archives; include SHA-256 checksums."""
from pathlib import Path
import argparse
import hashlib
import shutil
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nightguard import __version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = output / f"NightGuard-{__version__}-source.zip"
    allowed = ["launcher.py", "pyproject.toml", "requirements.txt", "requirements-dev.txt", "NightGuard.spec",
               "README.md", "README.en.md", "LICENSE", "THIRD_PARTY_NOTICES.md", ".gitignore"]
    files = [ROOT / name for name in allowed]
    for directory, suffixes in [("nightguard", {".py"}), ("tests", {".py"}), ("tools", {".py", ".plist"}),
                                ("docs", {".md", ".png"}), ("licenses", None), (".github", {".yml"})]:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file()
                     and "__pycache__" not in path.parts and (suffixes is None or path.suffix in suffixes))
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            assert path.stat().st_size > 0, path
            archive.write(path, Path("NightGuard-source") / path.relative_to(ROOT))
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None
        assert "NightGuard-source/.github/workflows/build.yml" in archive.namelist()
        assert not any(".venv/" in name or name.endswith(".log") for name in archive.namelist())
        print("SOURCE_OK", len(archive.namelist()), "files")
    delivered = [source]
    for path in sorted((ROOT / "artifacts").glob(f"NightGuard-{__version__}-*")):
        if path.name.endswith((".tar.gz", ".zip")) and "source" not in path.name:
            destination = output / path.name
            shutil.copy2(path, destination)
            delivered.append(destination)
    manual = output / "NightGuard-使用与打包说明.md"
    shutil.copy2(ROOT / "README.md", manual)
    delivered.append(manual)
    entries = []
    for path in delivered:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        entries.append(f"{digest.hexdigest()}  {path.name}")
        print("VERIFIED", path, path.stat().st_size, "bytes")
    checksum = output / "SHA256SUMS.txt"
    checksum.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print("VERIFIED", checksum, checksum.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
