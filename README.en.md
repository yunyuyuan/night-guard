# NightGuard

A quiet, local-first bedtime guardian for **Windows, Linux and macOS**, built with Python and PySide6. No tray, no cloud scheduler, and separate settings and reminder windows.

[简体中文文档](README.md)

## Delivery status

Development now takes place in [yunyuyuan/night-guard](https://github.com/yunyuyuan/night-guard). Download tagged packages from [Releases](https://github.com/yunyuyuan/night-guard/releases) and inspect native build results in [Actions](https://github.com/yunyuyuan/night-guard/actions/workflows/build.yml). CI builds four native targets and runs safe demo smoke tests; actual shutdown, login startup and desktop permission flows still require target-machine acceptance testing. Historical local verification is documented in `docs/VALIDATION.md`.

## Behavior

- Configure quiet hours, initially `00:00–06:00`. Overnight schedules such as `23:00–06:00` are supported.
- Entering quiet hours shows one always-on-top reminder with a **60-second** countdown.
- **Give me 1 more minute** cancels that countdown and hides the reminder for 60 seconds. A fresh reminder then starts a new 60-second countdown.
- The input **placeholder** contains the exact sentence required to skip the current quiet-hours session:
  - English: `I'm an idiot, and I insist on staying up late.`
  - Chinese: `我是傻逼，我就是要熬夜`
- Match the current language's phrase exactly, including punctuation, case and spaces. The English apostrophe is ASCII. Input is never logged.
- The skip is persisted across application restarts. An overnight session stays skipped across midnight; the following night's session runs normally.
- End time is exclusive. Leaving quiet hours cancels pending countdowns. Equal start/end times are rejected.
- Changing schedule hours invalidates a previous exemption for the old schedule.
- After a long event-loop/sleep gap or clock discontinuity, a fresh full minute is offered if still within quiet hours. The app does not execute while asleep.
- Closing settings leaves the background agent running. Reopening the application returns to settings through a single-instance IPC channel.
- Accepted but blocked shutdown requests lead to a fresh reminder after a minute. Explicit permission/command failures remain visible and require the user to snooze to retry, avoiding repeated authorization prompts.

## Important safety information

**Save your work before enabling protection. Unsaved data can be lost even with a normal shutdown, especially on Linux desktops that do not offer per-app save prompts.**

Protection is disabled on first launch; enable it and save to begin. Auto-start is selected by default and is registered when settings are saved.

No forced shutdown, administrator helper, `sudo`, inhibitor override or forced process termination is used. OS permissions, save dialogs, other sessions and policy can block shutdown. Once a request has been dispatched, cancellation is controlled by the operating system.

The app runs in your logged-in graphical session, **not before login**. It cannot present interactive reminders over a lock screen. **Locking does not automatically pause the countdown**, so a hidden reminder may still lead to a shutdown request. Wayland/full-screen/security desktop policies may also override topmost/focus requests.

This is a self-discipline tool, not tamper protection. Users can stop the process or change local configuration.

## Run the Linux archive

CI packages use an Ubuntu 22.04 x86_64 baseline and target compatible desktops, not arbitrary older glibc distributions. The example below uses version 1.0.0; select the actual version from Releases.

```bash
tar -xzf NightGuard-1.0.0-linux-x86_64.tar.gz
cd NightGuard
./NightGuard --demo       # Safe first trial; isolated configuration
./NightGuard --demo --stop
./NightGuard              # Real settings; protection remains off until enabled
```

Keep the full folder and place it at a stable location before enabling auto-start. Linux requires a graphical desktop, system D-Bus, `busctl`, systemd-logind and appropriate PolicyKit permissions. Headless/non-systemd systems are not currently supported.

For missing Qt X11 libraries on Debian/Ubuntu:

```bash
sudo apt-get install libegl1 libxcb-cursor0 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0
```

## Run from source

Use Python 3.10–3.12 on a supported 64-bit desktop. This delivery was tested with Python 3.12.3 and PySide6 6.9.3.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\pythonw.exe launcher.py --demo
# Real settings:
.venv\Scripts\pythonw.exe launcher.py
```

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launcher.py --demo
.venv/bin/python launcher.py
```

Source auto-start references the virtual environment and source directory. Do not move or delete them while auto-start is enabled.

| Option | Purpose |
|---|---|
| No option | Show settings, or activate the existing instance |
| `--background` | Start without opening settings or creating a tray icon |
| `--demo` | Separate `demo` profile; never shut down or modify auto-start |
| `--preview` | Safe standalone preview; implies `--demo` |
| `--stop` | Stop the matching profile's process; leave auto-start preference unchanged |
| `--demo --stop` | Stop the demo process |
| `--language en` / `--language zh` | Initial UI language; save to persist |
| `--data-dir PATH` | Alternate profile directory |

The settings-page preview does not send shutdown commands, but does not pause an already-enabled real guardian.

## Background integration

This is a **per-user login agent**, not a privileged system service. That is deliberate: system services cannot reliably present an interactive popup in the user's desktop session.

| Platform | Auto-start | Normal shutdown adapter |
|---|---|---|
| Windows | Current user's HKCU Run entry, GUI binary with `--background` | `shutdown.exe /s /t 0`, without `/f` |
| Linux | XDG `autostart/nightguard.desktop`, `Terminal=false` | logind `PowerOff(true)` through system D-Bus |
| macOS | `~/Library/LaunchAgents/app.nightguard.agent.plist`, Aqua session, no `KeepAlive` | AppleScript to System Events; Automation approval may be required |

Windows `/t > 0` implies forced shutdown, so the 60-second countdown stays inside NightGuard. macOS sets `LSUIElement=true` to hide the Dock icon while allowing windows. The source launcher also applies accessory activation policy and handles Finder reopen events.

Auto-start takes effect at the next login; the current process is already running. OS/enterprise policies may disable login items. Re-save settings after moving the executable so stored absolute paths are refreshed.

## Updates

The default update source is **`yunyuyuan/night-guard`**. Before the first stable Release exists, "No public release found" is expected. Users of an earlier version with an explicitly saved empty source should fill this repository in once and save.

The app checks the latest stable Release and opens its trusted GitHub release page on request; installation is manual. Drafts/pre-releases, malformed data, timeouts, rate limits and missing releases are handled. Fork CI builds embed their own repository as the default update channel.

There are no embedded tokens, private-release authentication, background network polling or telemetry.

## Build native packages

Build on the target OS; PyInstaller is not a cross-compiler.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/build.py
# Optional default public update source:
python tools/build.py --update-repo owner/nightguard
```

`artifacts/` contains the OS/architecture archive and a SHA-256 file. Windows is a folder ZIP with a windowed executable; Linux is a folder tarball; macOS is a `.app` ZIP. Keep all runtime libraries alongside the executable.

### Automatic tagged releases

The workflow builds Linux x86_64, Windows x86_64, macOS Intel x86_64 and macOS Apple Silicon arm64. **Pushing a version tag publishes a public GitHub Release after every target passes:**

```bash
git switch main
git pull --ff-only
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

The tag drives the application version, package filenames and macOS bundle metadata. Four native archives, their `.sha256` files, and `SHA256SUMS.txt` are uploaded before publication. A failed target blocks the release; an interrupted upload remains a draft and can be retried. Published releases are not overwritten; use a new version tag.

Stable tags use `vX.Y.Z`. Tags such as `v1.1.0-alpha.1`, `v1.1.0-beta.1` and `v1.1.0-rc.1` create GitHub Pre-releases; embedded versions follow Python normalization, e.g. `1.1.0rc1`. Main-branch pushes, pull requests and manual runs only build temporary Actions artifacts. They never publish a Release.

The built-in `GITHUB_TOKEN` is sufficient: only the release job gets `contents: write`; build jobs are read-only. No personal token is needed. See [maintainer release guide](docs/RELEASING.md). Private forks use their own GitHub Actions quotas.

The Linux workflow builds on Ubuntu 22.04; the earlier local delivery used Ubuntu 24.04 and had a different glibc floor. Target Windows 10/11 64-bit and macOS 13+; actual login and power permissions still need native desktop acceptance testing.

Production distribution should use Windows code signing and macOS signing/notarization. `NIGHTGUARD_CODESIGN_IDENTITY` and an Apple Events entitlement are provided as integration points. **No signing identity or notarization is included.** Do not treat unsigned development packages as signed releases.

## Tests, data and removal

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python tools/smoke_process.py
.venv/bin/python tools/smoke_process.py dist/NightGuard/NightGuard
.venv/bin/python tools/capture_ui.py
```

Windows uses `.venv\Scripts\python.exe`; set `QT_QPA_PLATFORM=offscreen` using the appropriate shell syntax if needed. All process smoke tests enforce demo mode. See `docs/VALIDATION.md` for this delivery's verification scope.

Data is stored in the user config directory: `%LOCALAPPDATA%\NightGuard`, `~/Library/Application Support/NightGuard`, or `$XDG_CONFIG_HOME/NightGuard` (usually `~/.config/NightGuard`). `NIGHTGUARD_DATA_DIR` or `--data-dir` can override it. Files include `config.json`, `state.json`, rotating `nightguard.log`, and a process lock. Input phrases are not stored.

To remove: disable auto-start and save, quit protection, then delete the application folder. Optionally delete its profile directory. Do not remove other programs' startup items or change security policy to work around a denied shutdown.

This repository retains its existing **Apache-2.0** license. The original MIT notice for the imported early NightGuard source is preserved in `licenses/NightGuard-original-MIT.txt`. Qt/PySide6 and other dependencies retain their own licenses; see `THIRD_PARTY_NOTICES.md` and `licenses/`.
