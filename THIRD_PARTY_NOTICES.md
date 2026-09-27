# Third-party notices / 第三方组件说明

This repository retains its existing Apache-2.0 license. The imported early NightGuard source's MIT notice is preserved in `licenses/NightGuard-original-MIT.txt`. These application licenses do not replace the licenses of the components below.

| Component | Version used for this delivery | License / source |
|---|---|---|
| PySide6 / Shiboken6 | 6.9.3 | LGPL-3.0 / GPL-3.0 / commercial alternatives; [Qt for Python](https://code.qt.io/cgit/pyside/pyside-setup.git/), tag `v6.9.3` |
| Qt shared libraries | 6.9.3 | LGPL-3.0 / GPL / commercial alternatives depending on module; [Qt source](https://download.qt.io/archive/qt/6.9/6.9.3/), [module source trees](https://code.qt.io/cgit/qt/) |
| CPython runtime | 3.12.3 for local Linux build; other builds use their interpreter version | PSF License and included notices; [CPython source](https://github.com/python/cpython/tree/v3.12.3) |
| platformdirs | 4.12.0 | MIT; [source](https://github.com/tox-dev/platformdirs) |
| packaging | 25.0 | Apache-2.0 or BSD-2-Clause; [source](https://github.com/pypa/packaging) |
| PyInstaller bootloader | 6.22.3 | GPL with application-distribution exception; [source/license](https://github.com/pyinstaller/pyinstaller) |

Full base license texts are included in `licenses/`; `LICENSE`, `LICENSE.APACHE` and `LICENSE.BSD` in that directory are the files shipped by the `packaging` dependency. `Python-copyright.txt` is the Python runtime distributor's copyright notice for the local Linux build.

## Qt / PySide6

The build uses a folder-based, dynamically linked distribution. The Qt / PySide6 libraries are not statically incorporated into proprietary application code. Users may inspect, modify and replace the corresponding compatible shared libraries, and may reverse engineer the combined work for debugging modifications to those LGPL components. NightGuard imposes no restriction on those LGPL rights.

QtCore, QtGui, QtWidgets and QtNetwork are the main modules used. Qt and the packaging process can include platform plugins and additional third-party libraries, whose notices and license obligations remain applicable. Official component sources are linked above. No Qt/PySide6 source modifications were made by this project.

Before commercial/public binary distribution, audit the exact resulting bundle, ship all applicable module and platform-library notices, and provide corresponding source / source-access arrangements as required by the selected licenses. The included development workflow is not a substitute for that distribution review, nor for Windows/macOS signing and notarization.

## Privacy

No telemetry, analytics, cloud scheduling, account login or embedded credentials are included. Update checks are user-initiated requests to GitHub for the configured public repository. Input-box contents are never included in logs or update requests.
