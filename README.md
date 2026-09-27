# NightGuard · 晚安守护

一个本地运行的 Windows / Linux / macOS 熬夜阻止程序。原生 Qt 界面，中英双语，无托盘，无云端调度。

[English documentation](README.en.md)

仓库：[yunyuyuan/night-guard](https://github.com/yunyuyuan/night-guard) · [下载 Release](https://github.com/yunyuyuan/night-guard/releases) · [构建状态](https://github.com/yunyuyuan/night-guard/actions/workflows/build.yml)

> **这不是网页演示。** 提醒、设置、时间规则和系统关机适配均已实现。CI 在四种原生环境构建并执行安全演示测试；实际关机、自启登录和权限流程仍需要在目标桌面机器验收。历史本地测试记录见 `docs/VALIDATION.md`。

## 功能

- 自定义每天的守护时段，默认 `00:00–06:00`，支持 `23:00–06:00` 等跨午夜时段。
- 进入时段立即显示一个置顶提醒，进行 **60 秒关机倒计时**。
- 点击「再给我 1 分钟」：取消当前倒计时，隐藏弹窗 **60 秒**，然后弹出新一轮 **60 秒**倒计时。不会堆叠多个提醒。
- 输入框的 **placeholder** 是当天关闭提示所需的完整句子。输入完全一致后按钮才可用。
- 暂停状态落盘，重启应用后仍有效；下一轮守护时段自动恢复。
- 独立设置页：作息计划、后台与语言、检查更新。提醒弹窗不包含自启或更新设置。
- 当前用户登录后静默启动，无控制台、无主窗口、无托盘。macOS 使用代理应用模式隐藏 Dock 图标。
- 单实例：再次启动程序唤起设置页，而不是创建另一个计时器。
- 更新检查使用 GitHub 公开 Release，检查完成后由用户打开发布页下载；不静默安装、不自动执行下载文件。
- 提供 `--demo` 与「预览提醒」，无需真的关机即可体验交互。

## 中英文占位文案

| 语言 | 输入框 placeholder / 完全匹配的关闭口令 |
|---|---|
| 简体中文 | 我是傻逼，我就是要熬夜 |
| English | I'm an idiot, and I insist on staying up late. |

英文使用 ASCII 单引号 `'`，并包括结尾句号。匹配区分大小写、标点和空格；只接受当前提醒语言对应的句子。应用不会把输入内容写入日志。

在「后台与语言」切换语言，设置页立即切换；保存后应用到正在运行的提醒窗口。首次启动根据本机语言选择中文或英文。

## 时间行为的精确定义

1. 时段使用**本机当前时间**，开始时间包含在内，结束时间不包含在内。开始和结束相同会被拒绝，不默认为全天。
2. 「关闭今天提醒」定义为**暂停当前这一轮守护时段**。例如 23:00–06:00，在 23:30 暂停后，跨过零点仍暂停，下一天 23:00 才恢复。
3. 修改起止时间会生成新时段标识，原来的豁免不适用于新计划。
4. 倒计时或延期过程中到达结束时间，当前提醒和待执行的关机动作立即取消。
5. 倒计时使用单调时钟。检测到超过 5 秒的事件循环中断，或墙钟与单调时钟显著偏离时，在仍处于守护时段的前提下重新给予完整 60 秒。休眠期间不执行程序，不会在唤醒瞬间补做过期关机。
6. 系统接受请求但一分钟后应用仍在运行时，会提供新一轮提醒。若请求明确失败，则保持错误提示，用户可延期后重试，不反复请求系统权限。
7. 输入句子或延期仅能取消**尚未发出**的关机请求。系统请求已经发送后，是否能取消由系统决定。
8. 它是自律工具，不是反作弊软件。不会阻止任务管理器、强制卸载或用户自行修改本机配置。

## 安全边界

**保存工作后再启用。正常关机也可能造成未保存内容丢失，尤其某些 Linux 桌面不会逐一提示应用保存。**

- 第一次打开时保护默认未启用。选择时间、勾选「启用熬夜守护」并保存后才开始执行；自启选项默认勾选，保存时注册。
- 不使用 `sudo`、提权服务、强制关机参数或强制杀进程。
- `--demo` 将配置隔离到独立的 `demo` 子目录，既不关机，也不修改系统自启。
- 命令行 `--preview` 隐含演示模式。设置页里的「预览提醒」不执行关机，但不会暂停已启用的正式守护任务。
- 程序无法在未登录的系统桌面或锁屏界面显示可交互提醒。**锁屏不会自动暂停计时，提醒可能被锁屏遮住，关机请求仍可能发出。** 请不要把它当作锁屏、关机前保存或唤醒保障工具。
- Wayland、全屏应用、系统安全桌面或窗口管理器策略可能影响置顶和焦点。置顶是请求，不是跨桌面环境的绝对保证。
- 权限、其他会话、系统策略、未保存文档和用户取消都可能阻止正常关机。不会自动绕过系统策略。

## 立即运行

### Linux 已打包版本

从 Releases 下载 `NightGuard-<版本>-linux-x86_64.tar.gz`。CI 使用 **Ubuntu 22.04 x86_64** 构建；建议使用 Ubuntu 22.04+ 兼容桌面，不能假定兼容任意旧 glibc 发行版。下面以 1.0.0 为例。

```bash
tar -xzf NightGuard-1.0.0-linux-x86_64.tar.gz
cd NightGuard
./NightGuard --demo --language zh   # 推荐：先安全试用
./NightGuard --demo --stop          # 退出演示后台
./NightGuard                      # 打开正式设置
```

解压后请保留整个 `NightGuard` 目录；不要只复制里面的可执行文件。先把目录放在长期保留的位置，再启用自启。

需要可用的图形桌面；关机适配依赖 `systemd-logind`、系统 D-Bus、`busctl` 和当前用户的 PolicyKit 权限。非 systemd 发行版、无桌面的服务器不在当前支持范围。

若 Qt 提示 xcb 依赖缺失，在 Debian / Ubuntu 安装：

```bash
sudo apt-get install libegl1 libxcb-cursor0 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0
```

缺少中文字体时可安装 `fonts-noto-cjk`。应用本身不需要 root 运行。

### 源码版（三平台）

需要 Python **3.10–3.12**；本次验证使用 Python 3.12.3、PySide6 6.9.3。请使用受支持的 64 位桌面系统。

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\pythonw.exe launcher.py --demo --language zh
# 正式运行：
.venv\Scripts\pythonw.exe launcher.py
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launcher.py --demo --language zh
# 正式运行：
.venv/bin/python launcher.py
```

源码版自启会引用该目录和虚拟环境，不要移动或删除它们。Linux 从终端运行源码时可能保留调用终端；正式的 GUI 包及登录自启不创建控制台。

### 常用命令

| 参数 | 作用 |
|---|---|
| 无参数 | 打开设置；已有后台实例时唤起原窗口 |
| `--background` | 只启动后台逻辑，不主动打开设置 |
| `--demo` | 独立演示配置；绝不关机、绝不改自启 |
| `--preview` | 打开安全提醒预览；隐含 `--demo` |
| `--stop` | 退出相同配置目录下的后台实例；不改变自启偏好 |
| `--demo --stop` | 退出演示后台 |
| `--language zh` / `--language en` | 本次初始界面语言；保存设置后持久化 |
| `--data-dir PATH` | 指定独立配置目录，用于开发或独立实例 |

关闭设置窗口只会隐藏窗口，守护继续运行。可在「后台与语言」点击「退出后台守护」结束当前进程。

## 「服务式自启」如何实现

这里指**登录后运行的用户会话代理**，不是启动到登录屏幕之前的系统服务。真正的系统服务不能可靠地直接向用户桌面弹窗，因此没有采用 Windows Session 0 服务或 macOS LaunchDaemon。

| 系统 | 自启注册 | 关机请求 |
|---|---|---|
| Windows | 当前用户 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 的 `NightGuard` 项，GUI 可执行文件带 `--background` | 应用倒计时结束后 `shutdown.exe /s /t 0`，**不带 `/f`** |
| Linux | `$XDG_CONFIG_HOME/autostart/nightguard.desktop`，通常为 `~/.config/autostart/`，`Terminal=false` | logind 的 `PowerOff(true)` D-Bus 调用，允许系统按自身策略授权 |
| macOS | `~/Library/LaunchAgents/app.nightguard.agent.plist`，`RunAtLoad`、Aqua 会话，无 `KeepAlive` | AppleScript 请求 System Events 正常关机，可能需要 Automation 授权 |

- Windows 的 `/t > 0` 会隐含 `/f`，因此 60 秒计时完全在应用中完成，不交给该参数。
- macOS `.app` 设置 `LSUIElement=true`，可以弹窗但平时不显示 Dock。使用 LaunchAgent，不启用失败后无限重启。
- 自启配置在下次登录时生效；当前进程在保存后继续运行。停用自启不会偷偷结束当前守护。
- 系统设置或企业策略可以禁用这些登录项目；程序不会绕过它们。
- 安装、搬动程序或更新到新路径后，请打开新程序，保存自启设置以刷新绝对路径。最好保持稳定路径。

## 检查更新与发布

默认更新仓库为 **`yunyuyuan/night-guard`**，正式版本从本仓库 GitHub Releases 检查更新。在首次正式 Release 发布前，显示「未找到公开发布版本」是正常现象。

1. 打开「检查更新」页，确认仓库为 `yunyuyuan/night-guard`。早期版本保存过空值的用户需填写一次并保存。
2. 仓库需要存在非草稿、非预发布的 Release，标签应为 `v1.0.1` 等有效版本号。
3. 点击「检查更新」。支持新版本、已最新、未配置、无公开 Release、网络失败、请求受限等反馈。
4. Fork 的 CI 会将其自身的 `owner/repository` 注入新安装默认值；本地也可用 `--update-repo` 覆盖。

不内置个人访问令牌，不支持私有 Release 的鉴权下载，不采集遥测，不在后台联网轮询。发布页链接只接受所配置仓库下的 HTTPS GitHub Release URL。

## 打包 Windows / Linux / macOS

**必须在对应操作系统上打包，不能用 Linux 的 PyInstaller 直接得到 Windows 或 macOS 可执行文件。**

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/build.py
# 有公开发布仓库时：
python tools/build.py --update-repo owner/nightguard
```

生成文件位于 `artifacts/`：

- Windows：包含 `NightGuard.exe` 及运行依赖的 ZIP，无控制台。
- Linux：包含 `NightGuard` 及运行依赖的 `.tar.gz`。
- macOS：`NightGuard.app` 的 ZIP，使用当前构建机的 CPU 架构。
- 每个包附带 `.sha256` 校验文件。

### 打标签自动发布

`.github/workflows/build.yml` 配置了 Windows x86_64、Linux x86_64、macOS Intel x86_64、macOS Apple Silicon arm64 四种原生构建。**向仓库推送版本标签会自动公开发布 Release**：

```bash
git switch main
git pull --ff-only
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

CI 会校验标签，从标签自动写入应用、文件名和 macOS Bundle 的版本，测试全部通过后打包并校验 SHA-256，上传四个原生包、各自的校验文件及总表 `SHA256SUMS.txt`，最后发布带自动更新日志的 Release。**任何一个平台失败都不会发布不完整版本。**

- 正式版标签：`v1.0.0`；预发布标签：`v1.1.0-alpha.1` / `v1.1.0-beta.1` / `v1.1.0-rc.1`，会标记为 GitHub Pre-release。预发布的包内版本按 Python 规则规范化，例如 `1.1.0rc1`。
- 日常 `main` 推送、PR、手动 Actions 只构建和上传临时 Artifacts，**不会创建 Release**。
- 只使用仓库自动提供的 `GITHUB_TOKEN`；构建任务只读，发布任务单独拥有 `contents: write`，不需要添加个人访问令牌。
- 上传失败会留下未公开的草稿；重跑失败任务可继续上传并发布。已经公开的 Release 不会被覆盖，请使用新版本标签。
- 原生包暂未做 Windows 证书签名 / macOS 开发者签名和公证。

更多发布规则见 [维护与发布指南](docs/RELEASING.md)。私有 Fork 的 Actions 用量遵循 GitHub 自身配额规则。

Linux CI 使用 Ubuntu 22.04 作为构建基线；早期本地 Linux 交付包使用 Ubuntu 24.04 构建，两者最低 glibc 兼容性不同。目标 Windows 10/11 64 位、macOS 13+；实际登录流程和关机权限仍需要原生验收。

正式分发前，Windows 应进行代码签名；macOS 应使用开发者证书签名并公证，否则可能遇到 SmartScreen / Gatekeeper 限制。构建配置提供 `NIGHTGUARD_CODESIGN_IDENTITY` 以及 Apple Events entitlement 入口，但**本次没有签名证书，也没有声称已签名或已公证**。

## 测试与项目结构

```bash
# 无显示器的 Linux：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python tools/smoke_process.py
# 已构建程序的安全进程测试：
.venv/bin/python tools/smoke_process.py dist/NightGuard/NightGuard
# 实际 Qt 界面截图（不运行调度器）：
.venv/bin/python tools/capture_ui.py
```

测试中的系统关机接口全部模拟或禁用；没有对开发环境执行关机，也没有启用开发环境自启。详见 `docs/VALIDATION.md`。

```text
nightguard/
  core.py        纯状态机：时段、延期、豁免、恢复
  storage.py     原子写入配置与豁免状态
  i18n.py        完整中英文文案
  ui.py          独立设置页和提醒弹窗
  app.py         Qt 后台调度与业务集成
  instance.py    用户级单实例锁与本地 IPC
  platforms.py   三平台自启、正常关机、macOS Dock/Reopen
  updates.py     GitHub Release 检查与版本比较
  build_info.py  构建时默认更新仓库
```

## 数据、卸载与排障

配置默认放在平台的用户配置目录：Windows `%LOCALAPPDATA%\NightGuard`；macOS `~/Library/Application Support/NightGuard`；Linux `$XDG_CONFIG_HOME/NightGuard` 或 `~/.config/NightGuard`。运行后以实际目录为准，可通过 `--data-dir` 或 `NIGHTGUARD_DATA_DIR` 改写。

- `config.json`：起止时间、开关、语言、更新仓库。
- `state.json`：当前已暂停的守护时段标识，不记录输入句子。
- `nightguard.log`：错误与运行诊断，轮转保存。
- `agent.lock`：单实例锁，不要在进程运行时手工删除。

卸载：先取消自启并保存，再退出后台，最后删除程序目录；需要完全清除偏好时再删除上述用户配置目录。手工清理登录项只删除本程序命名的项目，不要清理其他程序的配置。

关机失败时检查系统的当前会话、PolicyKit / Automation / Windows 关机权限和日志。不建议为了此程序降低系统安全策略。系统弹出的授权对话框不会被程序自动批准。

## 参考与许可证

- [Microsoft：Run / RunOnce](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)
- [Microsoft：shutdown 参数及 `/t` 与 `/f` 的关系](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/shutdown)
- [XDG 桌面自启规范](https://specifications.freedesktop.org/autostart/latest/)
- [systemd-logind PowerOff 接口](https://www.freedesktop.org/software/systemd/man/org.freedesktop.login1.html)
- [Apple：LaunchAgent](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Apple：LSUIElement](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/LaunchServicesKeys.html)
- [GitHub：Release API](https://docs.github.com/en/rest/releases/releases)
- [GitHub：运行器系统与架构](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)

本仓库沿用原有 **Apache-2.0** 许可证。导入的早期 NightGuard 源码的 MIT 声明保留于 `licenses/NightGuard-original-MIT.txt`。Qt / PySide6 等第三方库使用各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
