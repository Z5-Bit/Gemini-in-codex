"""Generate a provider fragment; opt-in activation with encrypted, conflict-safe backup."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tomllib

from mgc.paths import python_executable
from mgc.vault import protect

HERE = bootstrap.HERE
PROVIDER = "mgc_mixed_gateway"
LEGACY = "mgc_vertex_gateway"
BEGIN = "# BEGIN MultiGoogleCloud Mixed Gateway (managed)"
END = "# END MultiGoogleCloud Mixed Gateway (managed)"
MANAGED = {"model", "model_provider", "model_catalog_json", "model_reasoning_effort",
           "model_reasoning_summary", "model_supports_reasoning_summaries", "service_tier",
           "web_search", "model_context_window", "model_auto_compact_token_limit"}
MANAGED.discard('web_search')


def quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def fragment():
    cfg = json.loads((HERE / "settings.json").read_text(encoding="utf-8"))
    from manage import load_token
    local_token=load_token()
    head = f'''{BEGIN}
model = {quote(cfg["default_model"])}
model_provider = "{PROVIDER}"
model_catalog_json = {quote(HERE / "models.json")}
model_reasoning_effort = "medium"
{END}
'''
    tail = f'''
{BEGIN}
[model_providers.{PROVIDER}]
name = "MultiGoogleCloud Mixed Gateway"
base_url = "http://127.0.0.1:{cfg['port']}/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true
http_headers = {{ "X-MGC-Local-Token" = {quote(local_token)} }}
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
stream_idle_timeout_ms = 660000

{END}
'''
    # Saved Google-only chats keep their provider ID. While mixed mode is active,
    # that ID must resolve to the SAME authenticated mixed transport, not 18161.
    tail += tail.replace(PROVIDER, LEGACY).replace('MultiGoogleCloud Mixed Gateway"', 'MultiGoogleCloud Mixed Gateway (saved Google chats)"')
    return head, tail


def provider_block(text, name):
    selected, own = [], False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('['):
            h=line.strip().split('#',1)[0].strip()
            own=h==f'[model_providers.{name}]' or h.startswith(f'[model_providers.{name}.')
        if own and line.strip() not in (BEGIN,END):selected.append(line)
    return ''.join(selected)


def strip_provider(text, name):
    kept, own = [], False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('['):
            h=line.strip().split('#',1)[0].strip()
            own=h==f'[model_providers.{name}]' or h.startswith(f'[model_providers.{name}.')
        if not own:kept.append(line)
    return ''.join(kept)


def replace_top(text, keys):
    """Remove managed scalar assignments before the first TOML table only.

    Validate parsed semantic equality below to refuse exotic/multiline keys instead
    of rewriting user tables, comments or unrelated values.
    """
    lines, output, top = text.splitlines(keepends=True), [], True
    for line in lines:
        if line.lstrip().startswith("["):
            top = False
        match = re.match(r'^\s*(?:([A-Za-z0-9_-]+)|"([A-Za-z0-9_-]+)"|\'([A-Za-z0-9_-]+)\')\s*=', line)
        if top and match and next((g for g in match.groups() if g), "") in keys:
            continue
        output.append(line)
    return "".join(output)


def make_config(original):
    text = original.decode("utf-8-sig")
    old = tomllib.loads(text)
    if old.get('model_provider') == 'mgc_vertex_gateway':
        raise ValueError('请先运行第一版 Restore-Codex-Models.cmd，再启用混合版')
    if BEGIN in text:
        raise ValueError("配置中已存在启用标记，请先恢复")
    # Profiles may override the file's model/provider. Do not silently switch profiles.
    if old.get("profile"):
        raise ValueError("当前配置启用了命名 profile；请先在 Codex 取消该 profile，再启用网关")
    head, tail = fragment()
    text=strip_provider(text, LEGACY)
    # A dormant provider definition is deliberately retained for old chats.
    if PROVIDER in old.get('model_providers', {}):
        kept, own = [], False
        for line in text.splitlines(keepends=True):
            if line.lstrip().startswith('['):
                h=line.strip().split('#',1)[0].strip()
                own=h==f'[model_providers.{PROVIDER}]' or h.startswith(f'[model_providers.{PROVIDER}.')
            if not own or line.lstrip().startswith('#'):kept.append(line)
        text=''.join(kept)
    new = head + replace_top(text, MANAGED).rstrip() + "\n" + tail
    parsed = tomllib.loads(new)
    before = {k: v for k, v in old.items() if k not in MANAGED}
    after = {k: v for k, v in parsed.items() if k not in MANAGED}
    after["model_providers"].pop(PROVIDER)
    after['model_providers'].pop(LEGACY,None)
    if LEGACY in before.get('model_providers',{}):
        before['model_providers']=dict(before['model_providers'])
        before['model_providers'].pop(LEGACY)
    if PROVIDER in before.get('model_providers',{}):
        before['model_providers']=dict(before['model_providers'])
        before['model_providers'].pop(PROVIDER)
        if not before['model_providers']:before.pop('model_providers')
    if before.get('model_providers') == {}:before.pop('model_providers')
    if not after["model_providers"] and "model_providers" not in before:
        after.pop("model_providers")
    if before != after:
        raise ValueError("配置存在本脚本无法无损处理的 TOML 语法，未写入任何配置")
    return new.encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def restore_managed(current, original):
    """Restore only our keys, preserving settings edited by Codex after activation."""
    current_text, original_text = current.decode("utf-8-sig"), original.decode("utf-8-sig")
    now, before = tomllib.loads(current_text), tomllib.loads(original_text)
    retained = []
    own_table = False
    for line in current_text.splitlines(keepends=True):
        if line.strip() in (BEGIN, END):
            continue
        if line.lstrip().startswith("["):
            header = line.strip().split("#", 1)[0].strip()
            own_table = header.startswith(f"[model_providers.{PROVIDER}.") or header == f"[model_providers.{PROVIDER}]"
        if not own_table or line.lstrip().startswith("#"):
            retained.append(line)
    prefix = []
    # Supported managed values are scalars; refuse a future exotic value rather than corrupt it.
    for key in MANAGED:
        if key in before:
            value = before[key]
            if not isinstance(value, (str, bool, int, float)):
                raise ValueError("旧配置的模型设置包含复杂值，请使用手动恢复")
            prefix.append(key + " = " + json.dumps(value, ensure_ascii=False) + "\n")
    result = "".join(prefix) + replace_top("".join(retained), MANAGED)
    expected = dict(now)
    for key in MANAGED:
        expected.pop(key, None)
        if key in before:
            expected[key] = before[key]
    providers = dict(now.get("model_providers", {}))
    providers.pop(PROVIDER, None)
    if providers:
        expected["model_providers"] = providers
    else:
        expected.pop("model_providers", None)
    parsed = tomllib.loads(result)
    if parsed.get("model_providers") == {}:
        parsed.pop("model_providers")
    if parsed != expected:
        raise ValueError("无法无损恢复此 TOML 格式，请使用 README 中的手动恢复步骤")
    return result.encode("utf-8")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".mgc-pending")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def activation(config_path, state_dir, crypt=protect):
    manifest_path = state_dir / "activation.json"
    if manifest_path.exists():
        info = json.loads(manifest_path.read_text(encoding="utf-8"))
        current = config_path.read_bytes() if config_path.exists() else b""
        if info["config"] == str(config_path) and info["active_sha256"] == digest(current):
            return "已启用；没有重复改写配置或覆盖备份。"
        raise ValueError("已有激活记录且配置发生变化，请先恢复或人工核对；没有覆盖配置")
    existed = config_path.exists()
    original = config_path.read_bytes() if existed else b""
    updated = make_config(original)
    backup = state_dir / "config-before.dpapi"
    state_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(backup, crypt(original))
    manifest = {"config": str(config_path), "existed": existed, "before_sha256": digest(original),
                "active_sha256": digest(updated), "backup": str(backup)}
    # Save recovery information before replacing the host file.
    atomic_write(manifest_path, json.dumps(manifest, indent=2).encode())
    try:
        atomic_write(config_path, updated)
    except Exception:
        manifest_path.unlink(missing_ok=True)
        raise
    return "已启用 GPT / Gemini 混合模式，默认 GPT-6 Astra。请重新打开 Codex。"


def restoration(config_path, state_dir, crypt=protect):
    manifest_path = state_dir / "activation.json"
    if not manifest_path.exists():
        return "没有本脚本的激活记录；当前配置未改动。"
    info = json.loads(manifest_path.read_text(encoding="utf-8"))
    if info["config"] != str(config_path):
        raise ValueError("当前 CODEX_HOME 与启用时不同；请在原环境中运行恢复入口")
    current = config_path.read_bytes() if config_path.exists() else b""
    original = crypt(Path(info["backup"]).read_bytes(), decrypt=True)
    if digest(original) != info["before_sha256"]:
        raise ValueError("配置备份校验失败，未修改当前配置")
    exact = digest(current) in (info["active_sha256"], info["before_sha256"])
    # Undo the compatibility alias before restoring our own managed settings.
    # Restore the exact previous provider/auth, preserving its saved chats.
    if not exact:
        current_text=strip_provider(current.decode('utf-8-sig'),LEGACY)
        current_text=current_text.rstrip()+'\n'+provider_block(original.decode('utf-8-sig'),LEGACY)
        current=current_text.encode('utf-8')
    restored = original if exact else restore_managed(current, original)
    restored = retain_provider(restored)
    if info["existed"] or restored.strip():
        atomic_write(config_path, restored)
    else:
        config_path.unlink(missing_ok=True)
    manifest_path.unlink()
    return "已恢复启用前的 Codex 配置。请重新打开 Codex。登录资料没有改动。"


def retain_provider(raw):
    text = raw.decode('utf-8-sig')
    parsed = tomllib.loads(text)
    if PROVIDER not in parsed.get('model_providers',{}):
        tail = fragment()[1].replace(BEGIN,'# Inactive provider retained so saved chats can reopen.').replace(END,'')
        tail = strip_provider(tail, LEGACY)
        text = text.rstrip() + '\n' + tail
    tomllib.loads(text)
    return text.encode('utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "enable", "restore", "recover-copy", "repair"])
    args = parser.parse_args()
    config_path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve() / "config.toml"
    head, tail = fragment()
    (HERE / "generated/provider.config.toml").write_text(head + tail, encoding="utf-8")
    if args.command == "prepare":
        print("配置模板已生成；当前 Codex 配置未修改。")
    elif args.command == "enable":
        from catalog import build_mixed
        (HERE/'models.json').write_text(json.dumps(build_mixed(),ensure_ascii=False,indent=2),encoding='utf-8')
        from manage import ensure_started
        # Validate host config before starting the gateway.
        if not (HERE / "backups/activation.json").exists():
            make_config(config_path.read_bytes() if config_path.exists() else b"")
        ensure_started()
        print(activation(config_path, HERE / "backups"))
    elif args.command == "restore":
        print(restoration(config_path, HERE / "backups"))
    elif args.command == 'repair':
        raw = config_path.read_bytes() if config_path.exists() else b''
        repaired = retain_provider(raw)
        if repaired != raw:
            atomic_write(HERE/'backups/before-provider-repair.dpapi', protect(raw))
            atomic_write(config_path, repaired)
        print('旧聊天 provider 定义已修复；当前默认模型和登录资料未改变。')
    else:
        data = protect((HERE / "backups/config-before.dpapi").read_bytes(), decrypt=True)
        target = HERE / "backups/config-before.recovered.toml"
        target.write_bytes(data)
        print("恢复副本已保存到 gateway/backups/config-before.recovered.toml。该文件可能包含你的私有配置，请勿分享。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("配置操作失败；请检查文件权限、凭证和运行环境。没有输出私有配置。", file=sys.stderr)
        sys.exit(1)
