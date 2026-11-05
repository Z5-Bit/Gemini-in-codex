# Gemini-in-codex：补充许可与更新已有 GitHub 仓库

实际仓库：https://github.com/Z5-Bit/Gemini-in-codex

许可：**GPL-3.0-only**。本次是 `license.1` 发布材料修订，建议新标签 `v0.3-license.1`；原功能版本和旧标签保持不变。

## 第一步：更新现有 main

只把本材料的 `repository/` 内文件放到现有仓库根目录，保留远端现有提交历史。不要重新运行首次发布用的 `tools/Prepare-Git.ps1`，也不要 force push。

本地若已由本次整理建立 origin/main 基线并暂存更新，可在 `repository/` 中执行：

```powershell
git status --short
git diff --cached --stat
git config --local user.name "Z5-Bit"
git config --local user.email "你的GitHub提供的noreply地址@users.noreply.github.com"
git commit -m "Add project license, third-party notices and missing publication files"
git push origin main
```

把示例邮箱改为 GitHub Settings → Emails 显示的 noreply 地址；使用 Git 自己的登录流程，不把令牌放进命令。若未准备 Git，可先克隆上述已有仓库，再按 PUBLISH-MANIFEST.json 复制审核文件；或使用 GitHub Desktop 的 Add local repository 导入已经准备好的目录。

务必包含 `.gitignore`、`.gitattributes`、`.github/`；插件项目另须包含 `.agents/` 与 `plugins/*/.codex-plugin/`。网页手工上传曾遗漏这些文件，不能只看普通文件已出现就视为完整。

验证：`python -B tools/check_public.py --manifest`、`python -B tools/check_licenses.py` 和 `tools/Check-Publish.ps1` 应通过。推送后检查 GitHub Actions 的 Public source checks；GitHub 应识别根目录 LICENSE。

## 第二步：发布对应的修订附件

在 Releases 创建新标签 `v0.3-license.1`，Target 选刚更新的 main。标题与正文使用 `publish-text/`。上传本材料 `release-assets/` 中的四个文件：

1. `MultiGoogleCloud-Codex-0.3-github-windows-x64-license.1.zip`
2. `MultiGoogleCloud-Codex-0.3-github-windows-x64-license.1.zip.sha256`
3. `multigooglecloud-codex-portable-0.3-license.1-source.zip`
4. `multigooglecloud-codex-portable-0.3-license.1-source.zip.sha256`

新标签及附件实际存在后再发布。旧 Release 和旧标签保留；可在旧 Release 正文添加新许可修订版链接。不要只把 LICENSE 加到 main 就声称旧 ZIP 已更新。

## 第三步：下载复核

从新 Release 重新下载 ZIP，以 `Get-FileHash -Algorithm SHA256` 对照同页校验文件。便携包须能找到 LICENSE、LICENSING.md、THIRD-PARTY-NOTICES.md、THIRD-PARTY-INVENTORY.json、third_party/licenses/ 与 CORRESPONDING-SOURCE.md。

完整对应源码 ZIP 直接解压后就是仓库根目录结构，包含点开头文件。源码仓库不提交运行时、登录数据、Release ZIP 或整个交付包。

## 本次核对边界

本次检查许可证、原文副本、公开文件完整性、语法、敏感信息模式及可重复打包，不代表运行时已升级、所有依赖已做漏洞审计或所有云端功能已重新测试。Python 两个项目保留的 Python 3.11.3 / OpenSSL 1.1.1t 需要单独安排运行时升级和兼容性测试。
