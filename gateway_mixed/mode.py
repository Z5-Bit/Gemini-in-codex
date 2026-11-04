"""Select a coherent model/catalog/provider mode before opening Codex."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import os,json,tomllib,subprocess,datetime
from mgc.vault import protect
from mgc.paths import python_executable
from configure import replace_top,atomic_write

ROOT=bootstrap.ROOT
HERE=bootstrap.HERE
OWN_PROVIDERS=('mgc_vertex_gateway','mgc_mixed_gateway')


def native_providers(text):
    """Resolve saved gateway IDs through Codex's native OpenAI transport.

    Name=OpenAI selects the native capability defaults; omitting base_url lets
    Codex choose the official ChatGPT/API URL from its existing login. No local
    auth command, catalog, token, request limit or proxy is inherited.
    """
    output=[];own=False
    for line in text.splitlines(keepends=True):
        if line.strip()=='# Saved chat compatibility; direct native OpenAI transport.':continue
        if line.strip().startswith(('# BEGIN MultiGoogleCloud ', '# END MultiGoogleCloud ')):
            continue
        if line.lstrip().startswith('['):
            header=line.strip().split('#',1)[0].strip()
            own=any(header==f'[model_providers.{p}]' or header.startswith(f'[model_providers.{p}.') for p in OWN_PROVIDERS)
        if not own:output.append(line)
    result=''.join(output).rstrip()+'\n'
    for provider in OWN_PROVIDERS:
        result+=f'\n# Saved chat compatibility; direct native OpenAI transport.\n[model_providers.{provider}]\nname = "OpenAI"\nwire_api = "responses"\nrequires_openai_auth = true\nsupports_websockets = true\n'
    return result

def run_config(folder,command):
    p=subprocess.run([str(python_executable()),'-B',str(folder/'configure.py'),command],
        cwd=folder,capture_output=True,encoding='utf-8',timeout=40,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode:raise RuntimeError(f'{folder.name} 配置切换失败；已恢复修改前配置，请检查现有激活状态。')

def native_default(raw):
    old=tomllib.loads(raw.decode('utf-8-sig'))
    if old.get('model_provider','openai')!='openai':
        raise ValueError('当前提供商没有可用的恢复记录，未改写；请先恢复原 Codex 配置。')
    result=native_providers('model = "gpt-6-astra"\n'+replace_top(raw.decode('utf-8-sig'),{'model'})).encode()
    expected={**old,'model':'gpt-6-astra'}
    providers=dict(expected.get('model_providers',{}))
    for provider in OWN_PROVIDERS:
        providers[provider]={'name':'OpenAI','wire_api':'responses','requires_openai_auth':True,'supports_websockets':True}
    expected['model_providers']=providers
    if tomllib.loads(result.decode())!=expected:raise ValueError('无法无损更新默认模型')
    return result

def select_mode(target,config_path=None,root=ROOT,runner=run_config,crypt=protect):
    config_path=config_path or Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'config.toml'
    if target not in ('gateway','gateway_mixed','original'):raise ValueError('Unknown mode')
    raw=config_path.read_bytes() if config_path.exists() else b''
    current=tomllib.loads(raw.decode('utf-8-sig'))
    if current.get('profile'):raise ValueError('请先取消当前命名 profile，避免它覆盖打开入口的模型设置')
    if current.get('model_provider','openai') not in ('openai','mgc_vertex_gateway','mgc_mixed_gateway'):
        raise ValueError('当前使用另一提供商；请先恢复原 Codex 模式后再切换')
    tracked=[config_path]
    for name in ('gateway','gateway_mixed'):
        tracked.extend(root/name/'backups'/f for f in ('activation.json','config-before.dpapi'))
    before={p:p.read_bytes() if p.exists() else None for p in tracked}
    backups=root/('gateway' if target=='original' else target)/'backups'
    backups.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (backups/f'before-mode-{stamp}.dpapi').write_bytes(crypt(raw))
    try:
        # Restore the previously active mode before applying a new one. This also
        # removes mixed-mode compatibility aliases and restores native tool flags.
        for name in ('gateway','gateway_mixed'):
            folder=root/name
            if (folder/'backups/activation.json').exists():runner(folder,'restore')
        baseline=config_path.read_bytes() if config_path.exists() else b''
        atomic_write(config_path,native_default(baseline))
        if target!='original':runner(root/target,'enable')
        actual=tomllib.loads(config_path.read_text(encoding='utf-8-sig'))
        provider={'original':'openai','gateway':'mgc_vertex_gateway','gateway_mixed':'mgc_mixed_gateway'}[target]
        model='gemini-4-argon' if target=='gateway' else 'gpt-6-astra'
        if actual.get('model_provider','openai')!=provider or actual.get('model')!=model:
            raise RuntimeError('切换后模型和提供商不一致，已回滚')
        return {'mode':target,'default_model':model,'provider':provider}
    except Exception:
        for path,data in before.items():
            if data is None:path.unlink(missing_ok=True)
            else:atomic_write(path,data)
        raise

def main():
    action=sys.argv[1] if len(sys.argv)>1 else 'open'
    from mgc.codex_open import codex_app_executable
    executable=codex_app_executable()
    # The existing desktop instance keeps its loaded providers/catalog. Opening
    # another copy merely focuses it, which was the original routing failure.
    ps=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    script="@(Get-Process -Name Codex,ChatGPT -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq '"+str(executable).replace("'","''")+"' }).Count"
    check=subprocess.run([str(ps),'-NoProfile','-NonInteractive','-Command',script],capture_output=True,
        text=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if check.returncode or not check.stdout.strip().isdigit():raise RuntimeError('无法确认 Codex 是否已退出，配置未修改')
    if int(check.stdout.strip()):raise RuntimeError('请先保存工作并完全退出 Codex，再双击此入口；当前配置未修改。')
    target='original' if action in ('original','open-original') else HERE.name
    result=select_mode(target)
    print(json.dumps(result,ensure_ascii=False))
    if target=='original':
        # Only request shutdown from our authenticated services. Never kill an
        # unknown process or make native mode depend on a running gateway.
        for name in ('gateway','gateway_mixed'):
            try:
                subprocess.run([str(python_executable()),'-B',str(ROOT/name/'manage.py'),'stop'],
                    cwd=ROOT/name,capture_output=True,encoding='utf-8',timeout=10,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
            except (OSError,subprocess.SubprocessError):
                print('旧网关未确认退出；原版请求仍直接连接 OpenAI，可稍后运行 05-Stop-Gateways.cmd。')
    if action in ('open','open-original'):
        subprocess.Popen([str(executable)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    print('模型模式已准备；新启动的 Codex 将加载对应默认模型、目录和路由。')
    if target=='gateway_mixed':
        print('混合模式：新聊天默认 GPT-6 Astra；原 Google 网关聊天重新打开后也使用混合路由。')
    if target=='original':
        print('原版模式：默认 GPT-6 Astra；旧网关聊天也直接连接 OpenAI，不经过本机网关。')
        print('已有聊天如保留了 Gemini 选择，请先在模型列表中选回 GPT。')

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError) as e:print(str(e),file=sys.stderr);sys.exit(1)
    except Exception:print('模式切换失败，未输出私有配置，请检查路径和权限。',file=sys.stderr);sys.exit(1)
