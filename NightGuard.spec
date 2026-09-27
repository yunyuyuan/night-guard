# Build on each target OS. PyInstaller does not cross-compile desktop binaries.
import os
import sys
import runpy
from pathlib import Path
from packaging.version import Version

root = Path(SPECPATH)
version = runpy.run_path(str(root / 'nightguard/__init__.py'))['__version__']
bundle_version = '.'.join(str(part) for part in Version(version).release)
a = Analysis(
    [str(root / 'launcher.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / name), '.') for name in ('README.md', 'README.en.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md')]
          + [(str(root / 'licenses'), 'licenses'), (str(root / 'docs'), 'docs')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick', 'tkinter', 'numpy', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='NightGuard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=os.environ.get('NIGHTGUARD_TARGET_ARCH') or None,
    codesign_identity=os.environ.get('NIGHTGUARD_CODESIGN_IDENTITY') or None,
    entitlements_file=str(root / 'tools/macos-entitlements.plist') if sys.platform == 'darwin' else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='NightGuard')
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='NightGuard.app',
        bundle_identifier='app.nightguard.desktop',
        version=bundle_version,
        info_plist={
            'CFBundleDisplayName': 'NightGuard',
            'CFBundleShortVersionString': bundle_version,
            'NightGuardVersion': version,
            'LSUIElement': True,
            'NSHighResolutionCapable': True,
            'NSAppleEventsUsageDescription': 'NightGuard requests a normal shutdown after your bedtime countdown. / 晚安守护在倒计时结束后请求正常关机。',
        },
    )
