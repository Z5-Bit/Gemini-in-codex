# 第三方许可与来源声明

本清单基于 2026-11-05 核对的实际 Windows 发布 ZIP。第三方权利属于原权利人；本项目顶层 LICENSE 不覆盖或撤销以下条款。`third_party/licenses/` 保存原始许可/NOTICE 的逐字副本，完整路径、版本、来源和 SHA-256 记录在 [THIRD-PARTY-INVENTORY.json](THIRD-PARTY-INVENTORY.json)。运行包也保留依赖原位置的文本。

## 本项目组件来源

本项目的 0.3.3 非混合组件与 0.3.0-timeout600 混合组件、定向重试补丁记录在 [SUITE-COMPONENTS.json](SUITE-COMPONENTS.json)。这些是本套件的版本来源记录，不代表复制 OpenAI/Codex 或 Google 的专有程序。维护者有权授权的部分按根目录 GPL-3.0-only 分发。

## 随包运行时与子组件

便携包包含 CPython **3.11.3** 及 59 个 Python distribution。版本和许可来自实际 ZIP 内的 METADATA，不以顶层项目许可覆盖依赖。

- CPython 及其捆绑库：原文 `runtime/python/LICENSE.txt`，副本 [Python LICENSE](third_party/licenses/runtime/python/LICENSE.txt)。该文件还包含 OpenSSL/SSLeay、libffi、bzip2 等条件；补充官方 [Python 3.11.3 许可说明](third_party/licenses/supplemental/Python-3.11.3-license.rst)。其中上游 RST 的 include 指令应结合保留的原 LICENSE 阅读。
- Tcl/Tk **8.6.12**：保留包内 Tk 的 license.terms，补充 [Tcl 原始许可](third_party/licenses/supplemental/Tcl-8.6.12-license.terms)。它们具有独立版权条件。
- `certifi 2026.7.22`：**MPL-2.0**，包括 Mozilla CA 证书集合；保留原声明，另附 [MPL 2.0 全文](third_party/licenses/supplemental/MPL-2.0.txt)。可修改形式的 `certifi/*.py` 和 `certifi/cacert.pem` 已在运行包 `runtime/python/Lib/site-packages/certifi/` 内提供，仍按 MPL 授权；上游源码见 [python-certifi](https://github.com/certifi/python-certifi)。
- `pywin32 312` 的顶层 METADATA 写作 PSF，但内部存在不同许可，不能概括为全部 MIT 或 PSF。保留其 `*.dist-info/licenses/` 下全部原文：COM/win32/pythonwin 的 BSD 风格条款、MAPIStubLibrary 的 MIT、Scintilla 的许可，以及 **adodbapi 的 LGPL-2.1-or-later**。
- `adodbapi 2.6.2.0` 的 12 个 `.py` 源码文件已随运行包位于 `runtime/python/Lib/site-packages/adodbapi/`，保留 Henrik Ekelund / Vernon Cole 等原署名；LGPL 2.1 全文位于 `third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/adodbapi/license.txt`。它是独立第三方模块，本项目未修改该模块；不得限制接受者依法修改、替换该模块的权利。
- Apache-2.0 组件的原 NOTICE（包括 requests）与双许可组件的全部许可证一并保留。下表只概括元数据，遇到差异以组件自身原文和具体文件声明为准。

本次只整理许可与打包材料，运行时字节未升级。上述 CPython 3.11.3 所带 OpenSSL 为 1.1.1t；OpenSSL 1.1.1 已结束公开支持，升级运行时及相关兼容性测试仍是单独的发布维护工作。

OpenAI、Google、Codex、Gemini、Vertex AI 均属于相应权利人；本项目不分发 Codex 桌面应用，不授予其产品、商标、服务账号、模型或云服务使用权，也不代表官方背书。

## 实际安装依赖

许可栏来自上游包元数据，复合组件仍须阅读原文。源码仓库不包含运行时本体；下表许可副本在源码与便携包中都可直接阅读。

| 组件 | 版本 | 声明许可 | 许可/NOTICE 副本 |
| --- | --- | --- | --- |
| `annotated-doc` | `0.0.5` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/annotated_doc-0.0.5.dist-info/licenses/LICENSE) |
| `annotated-types` | `0.8.0` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/annotated_types-0.8.0.dist-info/licenses/LICENSE) |
| `anyio` | `4.15.1` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/anyio-4.15.1.dist-info/licenses/LICENSE) |
| `attrs` | `26.1.0` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/attrs-26.1.0.dist-info/licenses/LICENSE) |
| `certifi` | `2026.7.22` | MPL-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/certifi-2026.7.22.dist-info/licenses/LICENSE) |
| `cffi` | `2.1.1` | MIT-0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/cffi-2.1.1.dist-info/licenses/LICENSE) |
| `charset-normalizer` | `3.5.2` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/charset_normalizer-3.5.2.dist-info/licenses/LICENSE) |
| `click` | `8.5.0` | BSD-3-Clause | [LICENSE.txt](third_party/licenses/runtime/python/Lib/site-packages/click-8.5.0.dist-info/licenses/LICENSE.txt) |
| `colorama` | `0.4.6` | BSD-3-Clause (see retained text) | [LICENSE.txt](third_party/licenses/runtime/python/Lib/site-packages/colorama-0.4.6.dist-info/licenses/LICENSE.txt) |
| `cryptography` | `50.0.2` | Apache-2.0 OR BSD-3-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/cryptography-50.0.2.dist-info/licenses/LICENSE) / [LICENSE.APACHE](third_party/licenses/runtime/python/Lib/site-packages/cryptography-50.0.2.dist-info/licenses/LICENSE.APACHE) / [LICENSE.BSD](third_party/licenses/runtime/python/Lib/site-packages/cryptography-50.0.2.dist-info/licenses/LICENSE.BSD) |
| `distro` | `1.9.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/distro-1.9.0.dist-info/LICENSE) |
| `fastapi` | `0.143.5` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/fastapi-0.143.5.dist-info/licenses/LICENSE) |
| `google-api-core` | `2.42.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/google_api_core-2.42.0.dist-info/licenses/LICENSE) |
| `google-auth` | `2.62.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/google_auth-2.62.0.dist-info/licenses/LICENSE) |
| `google-cloud-core` | `2.8.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/google_cloud_core-2.8.0.dist-info/licenses/LICENSE) |
| `google-cloud-storage` | `3.17.1` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/google_cloud_storage-3.17.1.dist-info/licenses/LICENSE) |
| `google-crc32c` | `1.9.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/google_crc32c-1.9.0.dist-info/licenses/LICENSE) |
| `google-genai` | `2.31.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/google_genai-2.31.0.dist-info/licenses/LICENSE) |
| `google-resumable-media` | `2.11.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/google_resumable_media-2.11.0.dist-info/licenses/LICENSE) |
| `googleapis-common-protos` | `1.75.5` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/googleapis_common_protos-1.75.5.dist-info/licenses/LICENSE) |
| `h11` | `0.16.0` | MIT | [LICENSE.txt](third_party/licenses/runtime/python/Lib/site-packages/h11-0.16.0.dist-info/licenses/LICENSE.txt) |
| `httpcore` | `1.0.9` | BSD-3-Clause | [LICENSE.md](third_party/licenses/runtime/python/Lib/site-packages/httpcore-1.0.9.dist-info/licenses/LICENSE.md) |
| `httpx` | `0.28.1` | BSD-3-Clause | [LICENSE.md](third_party/licenses/runtime/python/Lib/site-packages/httpx-0.28.1.dist-info/licenses/LICENSE.md) |
| `httpx-sse` | `0.4.3` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/httpx_sse-0.4.3.dist-info/licenses/LICENSE) |
| `idna` | `3.20` | BSD-3-Clause | [LICENSE.md](third_party/licenses/runtime/python/Lib/site-packages/idna-3.20.dist-info/licenses/LICENSE.md) |
| `iniconfig` | `2.3.1` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/iniconfig-2.3.1.dist-info/licenses/LICENSE) |
| `jsonschema` | `4.26.0` | MIT | [COPYING](third_party/licenses/runtime/python/Lib/site-packages/jsonschema-4.26.0.dist-info/licenses/COPYING) |
| `jsonschema-specifications` | `2025.9.1` | MIT | [COPYING](third_party/licenses/runtime/python/Lib/site-packages/jsonschema_specifications-2025.9.1.dist-info/licenses/COPYING) |
| `mcp` | `1.30.0` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/mcp-1.30.0.dist-info/licenses/LICENSE) |
| `opentelemetry-api` | `1.45.1` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/opentelemetry_api-1.45.1.dist-info/licenses/LICENSE) |
| `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/packaging-26.3.dist-info/licenses/LICENSE) / [LICENSE.APACHE](third_party/licenses/runtime/python/Lib/site-packages/packaging-26.3.dist-info/licenses/LICENSE.APACHE) / [LICENSE.BSD](third_party/licenses/runtime/python/Lib/site-packages/packaging-26.3.dist-info/licenses/LICENSE.BSD) |
| `pluggy` | `1.7.0` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pluggy-1.7.0.dist-info/licenses/LICENSE) |
| `proto-plus` | `1.29.0` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/proto_plus-1.29.0.dist-info/licenses/LICENSE) |
| `protobuf` | `7.36.2` | BSD-3-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/protobuf-7.36.2.dist-info/LICENSE) |
| `pyasn1` | `0.6.4` | BSD-2-Clause | [LICENSE.rst](third_party/licenses/runtime/python/Lib/site-packages/pyasn1-0.6.4.dist-info/licenses/LICENSE.rst) |
| `pyasn1_modules` | `0.4.2` | BSD (see retained text) | [LICENSE.txt](third_party/licenses/runtime/python/Lib/site-packages/pyasn1_modules-0.4.2.dist-info/licenses/LICENSE.txt) |
| `pycparser` | `3.11` | BSD-3-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pycparser-3.11.dist-info/licenses/LICENSE) |
| `pydantic` | `2.14.1` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pydantic-2.14.1.dist-info/licenses/LICENSE) |
| `pydantic_core` | `2.50.1` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pydantic_core-2.50.1.dist-info/licenses/LICENSE) |
| `pydantic-settings` | `2.16.0` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pydantic_settings-2.16.0.dist-info/licenses/LICENSE) |
| `Pygments` | `2.21.0` | BSD-2-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pygments-2.21.0.dist-info/licenses/LICENSE) |
| `PyJWT` | `2.15.1` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pyjwt-2.15.1.dist-info/licenses/LICENSE) |
| `pytest` | `9.1.1` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pytest-9.1.1.dist-info/licenses/LICENSE) |
| `python-dotenv` | `1.2.4` | BSD-3-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/python_dotenv-1.2.4.dist-info/licenses/LICENSE) |
| `python-multipart` | `0.0.32` | Apache-2.0 | [LICENSE.txt](third_party/licenses/runtime/python/Lib/site-packages/python_multipart-0.0.32.dist-info/licenses/LICENSE.txt) |
| `pywin32` | `312` | PSF metadata; includes BSD / MIT / LGPL-2.1-or-later subcomponents | [license.txt](third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/adodbapi/license.txt) / [License.txt](third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/com/License.txt) / [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/com/win32comext/mapi/src/MAPIStubLibrary/LICENSE) / [License.txt](third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/pythonwin/License.txt) / [License.txt](third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/pythonwin/Scintilla/License.txt) / [LICENSE.txt](third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/pythonwin/pywin/idle/LICENSE.txt) / [License.txt](third_party/licenses/runtime/python/Lib/site-packages/pywin32-312.dist-info/licenses/win32/License.txt) |
| `PyYAML` | `6.0.3` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/pyyaml-6.0.3.dist-info/licenses/LICENSE) |
| `referencing` | `0.37.0` | MIT | [COPYING](third_party/licenses/runtime/python/Lib/site-packages/referencing-0.37.0.dist-info/licenses/COPYING) |
| `requests` | `2.34.2` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/requests-2.34.2.dist-info/licenses/LICENSE) / [NOTICE](third_party/licenses/runtime/python/Lib/site-packages/requests-2.34.2.dist-info/licenses/NOTICE) |
| `rpds-py` | `2026.9.1` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/rpds_py-2026.9.1.dist-info/licenses/LICENSE) |
| `sniffio` | `1.3.1` | MIT OR Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/sniffio-1.3.1.dist-info/LICENSE) / [LICENSE.APACHE2](third_party/licenses/runtime/python/Lib/site-packages/sniffio-1.3.1.dist-info/LICENSE.APACHE2) / [LICENSE.MIT](third_party/licenses/runtime/python/Lib/site-packages/sniffio-1.3.1.dist-info/LICENSE.MIT) |
| `sse-starlette` | `3.5.0` | BSD-3-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/sse_starlette-3.5.0.dist-info/licenses/LICENSE) |
| `starlette` | `1.8.0` | BSD-3-Clause | [LICENSE.md](third_party/licenses/runtime/python/Lib/site-packages/starlette-1.8.0.dist-info/licenses/LICENSE.md) |
| `tenacity` | `9.1.4` | Apache-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/tenacity-9.1.4.dist-info/licenses/LICENSE) |
| `typing_extensions` | `4.16.0` | PSF-2.0 | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/typing_extensions-4.16.0.dist-info/licenses/LICENSE) |
| `typing-inspection` | `0.4.4` | MIT | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/typing_inspection-0.4.4.dist-info/licenses/LICENSE) |
| `urllib3` | `2.8.0` | MIT | [LICENSE.txt](third_party/licenses/runtime/python/Lib/site-packages/urllib3-2.8.0.dist-info/licenses/LICENSE.txt) |
| `uvicorn` | `0.54.0` | BSD-3-Clause | [LICENSE.md](third_party/licenses/runtime/python/Lib/site-packages/uvicorn-0.54.0.dist-info/licenses/LICENSE.md) |
| `websockets` | `16.1.1` | BSD-3-Clause | [LICENSE](third_party/licenses/runtime/python/Lib/site-packages/websockets-16.1.1.dist-info/licenses/LICENSE) |
