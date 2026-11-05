# MultiGoogleCloud Codex Portable 0.3

在 Codex 中使用 Vertex AI Gemini，并提供混合 GPT/Gemini 与原生 GPT 模式入口。

Windows x64；非官方社区工具。每位使用者需要自己的服务权限与网络。本仓库和 Release 不包含任何开发者或使用者的账号、密钥、Cookie、聊天或作品。

## 功能

- 非混合采用 0.3.3 核心；Google 推理使用自己的 Vertex AI 凭证，不依赖 GPT 的认证和额度。
- 混合以 0.3.0-timeout600 为基础，追加下述故障恢复补丁，可在同一支持的聊天中选择 GPT/Gemini；保留该旧版的认证与历史限制。
- 两种 Google 路由均保留每次请求 600 秒生成期限；Google 网络读取 630 秒、Codex 流空闲等待 660 秒，128 MiB 本机请求上限。
- Google 在收到任何上游数据之前返回 HTTP 429 时，依次等待 **3 秒、6 秒**后重试，最多 **3 次请求（2 次重试）**。成功即停止重试；其他错误不重放。
- 已收到文本、思考摘要、工具、签名或用量数据后不重放，避免重复输出/工具调用；等待期间观察到断开即停止下一次请求。SDK 和 Codex 外层重试仍关闭，防止次数叠加。
- 两种模式统一 429/504/网络读取超时/流提前关闭的脱敏错误提示与请求次数、耗时诊断；补齐旧混合版 Google 630 秒传输缓冲和 GPT 660 秒读取等待。GPT 请求本身不增加重试。
- 包含流式输出、工具调用与签名保存、图片输入，以及已有桌面聊天的模式路由同步。
- 这是便携模式切换套件，不需要在 Codex 插件列表中注册。

## 首次使用

1. 设备需已有兼容的 Windows x64 Codex 桌面版、可用网络和自己的 Vertex AI 项目/服务账号。
2. 下载本仓库 Release 的 Windows ZIP，完整解压到可写目录；不要把 GitHub 自动生成的 Source code ZIP 当成便携运行包。
3. 填写 `VertexAI/Cloud.txt`：第一行项目 ID，第二行存储桶名，第三行服务账号 JSON 文件名；JSON 自行放入同目录。包内不带密钥，也不用 AI Studio API Key。
4. 运行 `Codex-Modes-0.3/00-Import-VertexAI.cmd`。
5. 保存工作并完全退出 Codex，然后选择下表入口。普通 Codex 快捷方式沿用最近一次所选模式。

| 入口 | 效果 |
| --- | --- |
| `01-Gemini.cmd` | 最新 0.3.3 非混合核心，默认 Gemini 4 Argon |
| `02-Mixed.cmd` | 0.3.0 超时修正混合核心，默认 GPT-6 Astra |
| `03-Original-Codex.cmd` | 恢复原生 Codex / GPT |
| `04-Check.cmd` | 只读检查配置与活动组件 |
| `05-Stop-Gateways.cmd` | 退出 Codex 后停止所属后台网关 |

GPT 额度、登录或服务异常时，完全退出 Codex 后使用 `01-Gemini.cmd`；不要把旧混合核心当作已具备最新混合版的额度隔离修复。Google 自身的权限、网络、模型可用性与配额仍需有效。

## 数据、权限与限制

切换会修改 Codex 用户级 config.toml 并通过官方接口同步支持的已有桌面聊天路由；不删除聊天正文或原生登录。恢复记录和签名在套件内加密保存，不要删除 gateway/state 后继续旧工具调用。Codex 自身的插件同步与账户刷新是独立后台行为。

本组合使用 0.3.3 的模式协调器进入三个模式；这项启动协调是相对直接运行原 0.3.0 混合入口的差异。两套核心基于原来源版本，追加 2026-11-03 `429-retry-3-6` 定向补丁，并非逐文件原样。原始来源与补丁后哈希见 SUITE-COMPONENTS.json；认证、路由、历史/签名、模型参数保持原方案。

## 源码与开发

仓库代码不附带运行环境。普通用户使用 Release 中带 `windows-x64` 的 ZIP。

开发者可以先下载同版本 Release，再在仓库内运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Restore-Runtime.ps1 -ReleaseZip "下载的发布包.zip"
```

该脚本按 RELEASE-ARTIFACT.json 与 RUNTIME-MANIFEST.json 校验，只恢复本仓库内被忽略的运行环境。不要提交恢复后的 runtime 或 node_modules。源码构建说明见 DEVELOPMENT.md。

发布步骤见 PUBLISH-GUIDE.md；隐私规则见 SECURITY.md；授权状态见 LICENSING.md。

## 已安装版本更新

只更新程序文件，不覆盖自己的凭证、配置和历史。保存工作并完全退出 Codex 后，从原来的模式入口重新打开；启动器会认证并识别所属旧网关，再加载补丁，绝不结束未知进程。需要手动停止时先使用 `05-Stop-Gateways.cmd`。健康检查包含 `recovery_patch: 429-retry-3-6`。

短暂限流可能通过重试恢复；持续配额不足不会因重试而解除。此次只做离线模拟/回归、公开文件扫描和可重复构建，无付费生成或第二台物理设备验收。

## 许可证

本项目维护者拥有或有权授权的代码使用 **GPL-3.0-only**，Copyright (c) 2026 Z5-Bit。详见 [LICENSE](LICENSE)、[授权范围](LICENSING.md) 和 [第三方声明](THIRD-PARTY-NOTICES.md)。

本次许可修订标签为 `v0.3-license.1`；源码与便携附件应成对发布，见 [对应源码说明](CORRESPONDING-SOURCE.md)。
