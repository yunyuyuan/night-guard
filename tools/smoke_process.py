"""Exercise a packaged binary or source launcher with isolated, no-shutdown data."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
command = [str(Path(sys.argv[1]).resolve())] if len(sys.argv) > 1 else [sys.executable, str(ROOT / "launcher.py")]
env = dict(os.environ)
env.setdefault("QT_QPA_PLATFORM", "offscreen")
with tempfile.TemporaryDirectory(prefix="nightguard-smoke-") as temporary:
    root = Path(temporary)
    demo = root / "demo"
    demo.mkdir()
    (demo / "config.json").write_text(json.dumps({
        "start": "00:00", "end": "23:59", "enabled": True,
        "autostart": False, "language": "en", "update_repo": ""
    }), encoding="utf-8")
    base = command + ["--demo", "--data-dir", str(root)]
    process = subprocess.Popen(base + ["--background"], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        started = time.monotonic()
        while not (demo / "agent.lock").exists():
            if process.poll() is not None:
                raise RuntimeError(f"Startup failed: {process.communicate()}")
            if time.monotonic() - started > 15:
                raise RuntimeError("Startup timeout")
            time.sleep(0.1)
        assert subprocess.run(base + ["--background"], env=env, timeout=15).returncode == 0
        assert process.poll() is None, "Duplicate launch killed the primary process"
        assert subprocess.run(base, env=env, timeout=15).returncode == 0
        assert subprocess.run(base + ["--preview"], env=env, timeout=15).returncode == 0
        assert subprocess.run(base + ["--stop"], env=env, timeout=15).returncode == 0
        stdout, stderr = process.communicate(timeout=40)
        assert process.returncode == 0, stderr.decode(errors="replace")
        print("SMOKE_OK: hidden start, single instance, settings IPC, preview IPC, clean stop; demo only.")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
