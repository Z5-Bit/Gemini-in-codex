# 开发与重新打包

源码不包含任何登录数据。不要从正在使用的安装目录复制 runtime、data 或配置进入源码库。

1. 按 README 用 `tools/Restore-Runtime.ps1` 从经过哈希核对的同版本 Release 恢复运行时。原文件有不同哈希时脚本停止，不覆盖。
2. 使用 Python 3.11+ 运行 `python tools/check_public.py --manifest` 检查本次源码快照。CI 使用标准库，不导入服务凭证或调用模型。
3. `python tools/build_release.py` 仅收集 RELEASE-PLAN.json 中列出的源文件及 RUNTIME-MANIFEST.json 中的运行文件，不递归复制使用数据。输出在被忽略的 dist 目录。已填写的登录配置不会成为发布输入。
4. 功能修改后重新检查代码、许可、配置模板和隐私，再更新发布清单与版本；不要把旧安全检查结果当作新代码的验证。

Python 程序无须编译。可使用从正式 Release 恢复的 `runtime/python/python.exe -B` 运行开发工具；或在本目录创建虚拟环境，按 requirements.lock.txt 安装依赖。Windows DPAPI 部分需要 Windows。

首次凭证模板只含占位文字。不要用自己的服务账号文件代替模板提交，也不要用真实聊天做公开测试夹具。

## 重试补丁离线测试

在隔离副本里安装 pytest 后，分别运行以下两条命令（模块名相同，不要合并为一个 pytest 进程）。测试不使用真实凭证，HTTP 上游是 MockTransport；不要在公开仓库中保存真实故障请求。

```powershell
python -B -m pytest gateway/tests/test_retry_429.py -p no:cacheprovider
python -B -m pytest gateway_mixed/tests/test_retry_429.py -p no:cacheprovider
```

断开测试同时覆盖 ASGI 2.3/2.4。600 秒仍是每次上游请求的生成期限，不是心跳间隔，也不是重试后整个会话的总时限。
