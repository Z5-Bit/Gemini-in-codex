# MultiGoogleCloud Codex Portable GitHub 发布步骤

建议仓库名：`multigooglecloud-codex-portable`；首次 Release 标签：`v0.3`。

## 文件分工

- `repository`：只把这个目录内的文件放到仓库根目录。它是干净源码，不含旧 Git 历史、运行数据或第三方运行环境。
- `release-assets`：把其中的 Windows ZIP 与 SHA256 文件上传到 GitHub Release 的附件区，不要提交到源码仓库。
- `publish-text`：仓库简介、发布标题与 Release 正文，可直接复制。
- Source ZIP 是 `repository` 的备用副本；不要把 ZIP 本身当作仓库源码上传。

## 推荐操作

1. 登录自己的 GitHub。先在 Settings → Emails 找到 GitHub 提供的 noreply 邮箱并启用邮箱隐私选项；提交作者使用公开昵称。不要将本机原工作区的 `.git` 拷过来。
2. 点击 New repository，填写 `multigooglecloud-codex-portable`。建议先选 Private 做最后预览；需要公开时再改 Public。不要勾选自动 README、gitignore 或 License，以免和已准备内容冲突。
3. 只进入本发布材料的 `repository`。运行 `tools/Check-Publish.ps1`，应显示 PASS。它核对审核后的文件哈希；如文件变化，先检查变化再重新整理，不要无条件跳过。
4. 如果有 Git，运行以下脚本创建全新的本地首次提交。邮箱应替换为你的 GitHub noreply 地址，不要使用个人邮箱。脚本不会上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Prepare-Git.ps1 -PublicName "你的公开昵称" -NoReplyEmail "GitHub给你的地址@users.noreply.github.com"
git status
git log -1 --format=fuller
git remote add origin https://github.com/YOUR_USERNAME/multigooglecloud-codex-portable.git
git push -u origin main
```

最后两行由你填写新仓库地址后执行。使用 Git 自己的登录/凭证管理流程；不要把 Token 拼进 URL、脚本或聊天。脚本只添加审核清单中的文件，不使用 `git add .`。

没有 Git 也可以在仓库页面使用 Add file → Upload files，分批上传 `repository` 内的文件和目录；包括以点开头的 `.github`、`.agents`（存在时）、`.gitignore`、`.gitattributes`。不要上传原始软件目录、source ZIP、release-assets 或整个发布总目录。

5. 查看 GitHub 文件列表和 Actions 检查。确认没有 browser、secrets、data、outputs、auth.json、填写后的 Cloud.txt、服务账号 JSON、运行日志或真实本机路径。README 已放在仓库根目录。
6. 进入 Releases → Draft a new release，创建标签 `v0.3`，Target 选 main；复制 publish-text 中的标题和正文。上传 release-assets 中的 ZIP 与 `.sha256`。先 Save draft，检查附件名称和数量，再 Publish release。
7. 从发布页面重新下载一次，核对 SHA256。公开前再检查首次提交的作者、邮箱和附件。授权选择见 LICENSING.md；如决定使用开源许可，使用公开署名添加 LICENSE，并保留第三方许可。

## 更新版本

使用新的干净导出目录；禁止打包登录后使用过的安装目录。更新版本号、README、发布说明和清单，审阅新文件与提交历史；公开附件也必须重新扫描，不能只依赖 `.gitignore`。本次提供的清单对应本次快照，不是后续任意修改的安全证明。

官方说明：
- https://docs.github.com/en/get-started/start-your-journey/uploading-a-project-to-github
- https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
