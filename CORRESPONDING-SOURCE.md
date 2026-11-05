# 对应源码与许可修订版

本次修订标识：`license.1`；建议发布标签：`v0.3-license.1`。功能版本保持不变。

- 项目源码仓库：https://github.com/Z5-Bit/Gemini-in-codex
- 本次发布页：https://github.com/Z5-Bit/Gemini-in-codex/releases/tag/v0.3-license.1
- 完整本项目源码附件：`multigooglecloud-codex-portable-0.3-license.1-source.zip`，同时提供独立 `.sha256`。该附件包含本项目全部源文件、构建/打包脚本、锁文件、配置模板及许可声明，不含用户资料。
- 便携附件：`MultiGoogleCloud-Codex-0.3-github-windows-x64-license.1.zip`。Python 项目的 `.py` 也是可修改源码；依赖的源码/许可位置见 THIRD-PARTY-NOTICES.md。

发布者应先将本目录内容提交到 main，再使上述新标签指向该提交，同时上传源码 ZIP、便携 ZIP 及两份 SHA-256。以上 URL 是本地修订包的发布目标，必须实际上传后才可对外声称已提供该版本下载。不要把旧标签自动生成的源码 ZIP 当成本次修订源码，也不要移动旧标签来伪装原始发布。

重新打包：安装 Python 3.11+，按 README 用 `tools/Restore-Runtime.ps1` 恢复经过哈希核对的便携运行时，然后运行 `python -B tools/build_release.py`。工具只使用明确允许的源文件与运行时文件；功能源码不会在此过程中联网下载。

本次仅改许可、文档、CI 与发布元数据，不修改模型调用逻辑或第三方运行库。再分发修改版本时，应保留适用的许可证、版权、修改记录和对应源码获取方式。
