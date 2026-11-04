# 安全与隐私

本仓库及正式 Release 只应包含程序、公开依赖、模板及说明。登录后产生的数据属于使用者，不能重新压缩上传。

禁止提交：服务账号 JSON、填写后的 Cloud.txt、API Key、OAuth Token、Windows 加密凭证、Codex auth.json、浏览器资料/Cookie、私人项目与剧本、素材、输出、聊天、工具签名、日志、备份、绝对本机配置、原工作区 Git 历史。

模板只使用占位文字。程序需要访问的服务账号文件应放在仓库以外或明确被忽略的本机凭证目录。加密文件也不是可公开文件。

反馈问题时只提交版本、复现步骤和已脱敏的错误类别。不要上传完整日志、配置、屏幕截图或作品包来公开排查；先检查其中的账号、项目、路径和内容。项目维护者可在 GitHub 开启 Private vulnerability reporting，安全问题通过私密渠道报告。

首次发布使用 tools/Check-Publish.ps1 核对已审核清单。tools/Prepare-Git.ps1 只将清单文件加入一个新 Git 仓库，不复制旧历史，并要求 GitHub 的 noreply 提交邮箱。自动检查不能证明未来添加的内容绝对没有隐私；新增文件和提交历史仍须人工检查。

如果曾上传有效凭证，应先撤销或轮换凭证，再按 GitHub 官方敏感数据清理流程处理 Git 历史和已有 Release。只删除当前文件不代表旧提交或下载副本消失。

参考：https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
