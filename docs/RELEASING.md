# 维护与发布 / Releasing NightGuard

开发仓库：https://github.com/yunyuyuan/night-guard

## 触发规则

| 操作 | 构建、测试、上传 Artifacts | 自动公开 Release |
|---|---|---|
| 推送 `main` | 是 | 否 |
| 创建或更新 PR | 是 | 否 |
| Actions 手动运行 | 是 | 否，即使选择了标签 ref |
| 推送 `vX.Y.Z` 标签 | 是 | 是，四个平台全部成功后 |
| 推送 `vX.Y.Z-alpha.N` / `-beta.N` / `-rc.N` | 是 | 是，标为 Pre-release |
| 其他 `v*` 标签 | 版本校验失败 | 否 |

**推送版本标签就是发布动作。** 不需要再在 GitHub 页面手动创建 Release。请只给已审核、准备发布的提交打标签。

## 正式发布

```bash
git switch main
git pull --ff-only
# 检查工作区干净，且该提交在 Actions 已构建成功。
git status
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

示例版本号请换成尚未使用的新版本。无需手工同步三处版本号：CI 从标签修改构建工作区中的 `nightguard/__init__.py`；Python 项目元数据动态读取它，PyInstaller 文件名和 macOS Bundle 也从同一来源取值。源代码分支中的版本可按开发进度调整，CI 不会为打包修改反向推送提交。

预发布示例：

```bash
git tag -a v1.1.0-rc.1 -m "Release candidate 1"
git push origin v1.1.0-rc.1
```

预发布包内版本为 `1.1.0rc1`；更新检查只跟踪正式 Release，不会向普通用户推荐预发布版本。版本数字不得带多余前导零。

## 产物

- `NightGuard-<version>-windows-x86_64.zip`
- `NightGuard-<version>-linux-x86_64.tar.gz`
- `NightGuard-<version>-macos-x86_64.zip`
- `NightGuard-<version>-macos-arm64.zip`
- 四个对应的 `.sha256` 文件。
- 一个包含四个安装包摘要的 `SHA256SUMS.txt`。

这些是保留完整运行依赖目录的便携包，不是 MSI/DMG 安装向导。GitHub 还会自动提供该标签的源码归档。

构建使用四个独立原生 runner：`windows-2022`、`ubuntu-22.04`、`macos-15-intel`、`macos-15`。每个 runner 运行测试、打包，再用 `--demo` 模式测试后台启动、单实例、设置页唤起和退出；CI 不会执行真实关机，也不会修改 runner 的登录自启。

## 发布流程的保护措施

1. 校验标签格式，自动确定正式版或预发布。
2. 四个平台全部通过后，下载所有构建产物。
3. 确认恰好包含四种目标包，重新计算 SHA-256 并比对各自校验文件。
4. 通过 `--verify-tag` 确认远程标签已存在，不意外创建标签。
5. 创建未公开草稿、上传全部包及校验文件，最后才发布。
6. 生成 GitHub Release 自动更新日志。

发布任务单独请求 `contents: write`。其他任务只有 `contents: read`，无需额外 PAT、上传密钥或本机凭据。CI 不更改仓库权限、分支保护或账号设置。

## 失败与重跑

- 测试或某个平台失败：不会创建 Release，先修复失败原因。
- 上传中断：保留草稿；在 Actions 页面重跑失败任务，继续上传后发布。
- 已公开版本：不覆盖现有包；相同产物已存在则保持不变，不同产物报错并要求新版本标签。压缩包构建不保证逐字节可复现，因此重新构建可能产生不同摘要或大小；发布后请使用新版本号。
- 403 / 权限失败：工作流会直接报错，不会把它误当成「版本不存在」。请由仓库管理员检查 Actions / 组织策略。
- 不要移动已经公开发布的标签，也不要用同一版本号替换用户已经下载的程序。

## 不发版的验证

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/release.py metadata --tag v2.3.4-rc.1
python tools/build.py
```

运行工作流的 `workflow_dispatch` 或推送 `main` 可以做四平台验证，但不发版。发布脚本的 GitHub API 调用有 mock 单元测试，覆盖草稿恢复、上传失败、已发布版本保护和权限错误。**实际公开发布只在维护者推送发布标签后执行。**

## 更新源与签名

官方更新源默认是 `yunyuyuan/night-guard`。CI 打包时使用当前 `github.repository`，因此 Fork 的构建会默认查询 Fork 自己的 Release。没有发布正式 Release 时，应用会显示未找到公开版本。

当前流水线不包含 Windows 证书签名或 macOS 开发者证书签名、公证。unsigned/ad-hoc 开发包可能被 SmartScreen 或 Gatekeeper 提醒/限制；CI 成功不等于完成生产签名。真实关机、登录自启、锁屏和权限授权仍须在桌面测试机上验收。

## English summary

Push `vX.Y.Z` to build all four native targets and publish a stable GitHub Release. `vX.Y.Z-alpha.N`, `-beta.N` and `-rc.N` publish prereleases. Main pushes, PRs and manual runs build artifacts only. The tag is the version source of truth; all targets must pass before publication. SHA-256 digests are verified, files are uploaded to a draft, and only then is the release made public. Existing published assets are never overwritten. Only the built-in `GITHUB_TOKEN` is required. Packages are portable archives and are not production-signed/notarized.
