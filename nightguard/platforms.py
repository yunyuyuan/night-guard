"""User-session integration. No elevation, privileged services or forced power-off."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AGENT_LABEL = "app.nightguard.agent"


def launch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        command = [str(Path(sys.executable).resolve())]
    else:
        executable = Path(sys.executable)
        if sys.platform == "win32" and executable.name.lower() == "python.exe":
            pythonw = executable.with_name("pythonw.exe")
            if pythonw.exists():
                executable = pythonw
        # Absolute entry script works independently of working directory/PYTHONPATH.
        command = [str(executable.absolute()), str(Path(__file__).resolve().parent.parent / "launcher.py")]
    return command + ["--background"]


def desktop_quote(argument: str) -> str:
    """XDG Exec quoting: quoted-argument escaping followed by desktop string escaping."""
    if any(c in argument for c in "\n\r\0"):
        raise ValueError("Invalid character in launch path")
    value = argument.replace("%", "%%")
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return '"' + value.replace("\\", "\\\\") + '"'


def autostart_path(platform: str | None = None, home: Path | None = None) -> Path:
    platform, home = platform or sys.platform, home or Path.home()
    if platform == "darwin":
        return home / "Library/LaunchAgents" / f"{AGENT_LABEL}.plist"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "autostart/nightguard.desktop"


def autostart_payload(command: list[str], platform: str) -> bytes:
    if platform == "darwin":
        return plistlib.dumps({
            "Label": AGENT_LABEL,
            "ProgramArguments": command,
            "RunAtLoad": True,
            "LimitLoadToSessionType": "Aqua",
            "ProcessType": "Interactive",
        })
    # GIO validates argv[0] before %% expansion and XDG forbids '=' in argv[0].
    # A fixed POSIX wrapper keeps the path in a normal argument. No user data is
    # interpolated into shell source: quoted "$@" preserves every argument.
    command = ["/bin/sh", "-c", 'exec "$@"', "nightguard", *command]
    return ("[Desktop Entry]\nType=Application\nVersion=1.0\nName=NightGuard\n"
            "Comment=Quiet bedtime protection\nTerminal=false\n"
            "Exec=" + " ".join(desktop_quote(arg) for arg in command) + "\n").encode("utf-8")


def autostart_installed() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                return bool(winreg.QueryValueEx(key, "NightGuard")[0])
        except FileNotFoundError:
            return False
    return autostart_path().is_file()


def set_autostart(enabled: bool, data_dir: Path | None = None):
    command = launch_command()
    if data_dir is not None:
        command += ["--data-dir", str(data_dir.resolve())]
    if sys.platform == "win32":
        import winreg
        value = subprocess.list2cmdline(command)
        if enabled and len(value) > 260:
            raise ValueError("Auto-start path is too long. Move NightGuard to a shorter path.")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, "NightGuard", 0, winreg.REG_SZ, value)
            else:
                try:
                    winreg.DeleteValue(key, "NightGuard")
                except FileNotFoundError:
                    pass
        return
    path = autostart_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".nightguard-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(autostart_payload(command, sys.platform))
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    # No launchctl bootstrap/bootout here: this running process is already the
    # agent. The plist takes effect next sign-in; removing it doesn't kill us.


def shutdown_command(platform: str | None = None) -> list[str]:
    platform = platform or sys.platform
    if platform == "win32":
        executable = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/shutdown.exe")
        # /t > 0 implies /f on Windows. Countdown stays in our own process.
        return [executable, "/s", "/t", "0"]
    if platform == "darwin":
        return ["/usr/bin/osascript", "-e", 'tell application "System Events" to shut down']
    if platform.startswith("linux"):
        # Go through logind/PolicyKit. No sudo, no --force or inhibitor bypass.
        return ["/usr/bin/busctl", "--system", "--timeout=25s", "call",
                "org.freedesktop.login1", "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager", "PowerOff", "b", "true"]
    raise RuntimeError("Unsupported operating system")


def request_shutdown(demo: bool = False) -> tuple[bool, str]:
    if demo:
        return True, "demo"
    try:
        options = {}
        if sys.platform == "win32":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(shutdown_command(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=35, **options)
        return result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[:1000]
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        return False, str(error)[:1000]


def hide_macos_dock():
    """LSUIElement also covers packaged apps; this covers source launches."""
    if sys.platform != "darwin":
        return
    try:
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        send_policy = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(("objc_msgSend", objc))
        app = send(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
        send_policy(app, objc.sel_registerName(b"setActivationPolicy:"), 1)  # accessory
    except (OSError, AttributeError):
        pass


_mac_reopen_callback = None


def install_macos_reopen_handler(callback) -> bool:
    """Bridge Finder's reopen event; Finder may not start a second process.

    Keep the C callback alive for the process lifetime. The supplied callable
    must only enqueue a Qt signal, not manipulate Cocoa widgets in this callback.
    """
    global _mac_reopen_callback
    if sys.platform != "darwin":
        return False
    try:
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        for name in ("objc_getClass", "sel_registerName"):
            function = getattr(objc, name)
            function.argtypes = [ctypes.c_char_p]
            function.restype = ctypes.c_void_p
        objc.object_getClass.argtypes = [ctypes.c_void_p]
        objc.object_getClass.restype = ctypes.c_void_p
        objc.class_addMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        objc.class_addMethod.restype = ctypes.c_bool
        objc.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.class_getInstanceMethod.restype = ctypes.c_void_p
        objc.method_setImplementation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.method_setImplementation.restype = ctypes.c_void_p
        send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        app = send(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
        delegate = send(app, objc.sel_registerName(b"delegate"))
        if not delegate:
            return False
        cls = objc.object_getClass(delegate)
        selector = objc.sel_registerName(b"applicationShouldHandleReopen:hasVisibleWindows:")
        signature = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
        def reopen(_self, _selector, _app, _visible):
            callback()
            return True
        _mac_reopen_callback = signature(reopen)
        pointer = ctypes.cast(_mac_reopen_callback, ctypes.c_void_p)
        if not objc.class_addMethod(cls, selector, pointer, b"B@:@B"):
            method = objc.class_getInstanceMethod(cls, selector)
            if not method:
                return False
            objc.method_setImplementation(method, pointer)
        return True
    except (OSError, AttributeError):
        return False
