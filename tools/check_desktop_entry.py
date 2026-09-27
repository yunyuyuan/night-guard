"""Linux-only optional check using real GLib/GIO, not an auto-start install."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nightguard.platforms import autostart_payload

with tempfile.TemporaryDirectory(prefix="nightguard-xdg-") as directory:
    root = Path(directory)
    values = ['quote"test', '$literal', '`literal', 'a\\b', '100%', '中文']
    for index, name in enumerate(['plain', 'space 中文', 'dollar$', 'tick`', 'quote"', 'back\\slash', 'percent%', 'equal=sign']):
        executable = root / name
        executable.write_text('#!/usr/bin/env python3\nimport sys,json\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps(sys.argv[2:]), encoding="utf-8")\n')
        executable.chmod(0o700)
        output = root / f"result-{index}.json"
        desktop = root / f"test-{index}.desktop"
        desktop.write_bytes(autostart_payload([str(executable), str(output)] + values, "linux"))
        subprocess.run(["desktop-file-validate", str(desktop)], check=True)
        launch = subprocess.run(["gio", "launch", str(desktop)], capture_output=True)
        assert launch.returncode == 0, launch.stderr.decode(errors="replace")
        deadline = time.monotonic() + 5
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert output.exists(), f"GIO did not execute {name!r}"
        assert json.loads(output.read_text()) == values
        print(f"XDG_OK: {name!r}, all special-character arguments preserved.", flush=True)
