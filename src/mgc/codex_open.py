"""Open the existing Codex window, without Windows URI activation or model calls."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET
from .paths import ROOT

_launches = {}
_lock = threading.Lock()
LAUNCH_TTL = 120


def launch_log(event, launch_id=None):
    """Only fixed event names and random receipt IDs; no URLs or exception text."""
    record = {'time': datetime.now(timezone.utc).isoformat(), 'event': event}
    if launch_id:
        record['launch_id'] = launch_id
    try:
        path = ROOT / 'logs/launcher.log'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as output:
            output.write(json.dumps(record) + '\n')
    except OSError:
        pass


def new_launch():
    now = time.monotonic()
    with _lock:
        for key, value in list(_launches.items()):
            if now - value['created'] > LAUNCH_TTL:
                del _launches[key]
        identity = uuid.uuid4().hex
        _launches[identity] = {'created': now, 'ready': False}
    launch_log('launch_created', identity)
    return {'id': identity, 'ready': False}


def launch_status(identity, acknowledge=False):
    with _lock:
        value = _launches.get(identity)
        if value is None or time.monotonic() - value['created'] > LAUNCH_TTL:
            raise ValueError('打开请求已过期，请重新打开工作台')
        if acknowledge and not value['ready']:
            value['ready'] = True
            launch_log('page_ready', identity)
        return {'id': identity, 'ready': value['ready']}


def codex_app_executable():
    """Discover the installed package, including its actual executable name."""
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
               "Get-AppxPackage -Name OpenAI.Codex | Sort-Object Version -Descending | "
               "Select-Object -First 1 -ExpandProperty InstallLocation")
    try:
        result = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, encoding='utf-8', timeout=12,
                                creationflags=subprocess.CREATE_NO_WINDOW, check=True)
        package = Path(result.stdout.strip())
        if not package.is_absolute():
            raise ValueError()
        tree = ET.parse(package / 'AppxManifest.xml')
        ns = {'m': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10'}
        for app in tree.findall('./m:Applications/m:Application', ns):
            executable = (package / app.attrib.get('Executable', '')).resolve()
            if (executable.is_relative_to(package.resolve()) and executable.is_file() and
                    executable.name.lower() in ('chatgpt.exe', 'codex.exe')):
                return executable
    except (OSError, subprocess.SubprocessError, ValueError, ET.ParseError):
        pass
    raise ValueError('未找到已安装的 Codex 桌面程序，请先安装并打开 Codex。')


def codex_browser_link(connection, launch_id=None):
    base = connection['url']
    parsed = urlsplit(base)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or
            not parsed.port or parsed.username or parsed.password or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('工作台地址必须是本机服务地址')
    token = connection.get('token')
    if not isinstance(token, str) or not token:
        raise ValueError('本地工作台连接尚未就绪')
    # The outer Codex URL must have no literal fragment; encode the complete URL.
    target = base.rstrip('/') + '/'
    if launch_id is not None:
        if not isinstance(launch_id, str) or len(launch_id) != 32 or any(c not in '0123456789abcdef' for c in launch_id):
            raise ValueError('无效的打开请求')
        target += '?launch=' + launch_id
    target += '#access=' + quote(token, safe='')
    return 'codex://browser?url=' + quote(target, safe='')


def open_in_codex(connection, launch_id=None):
    link = codex_browser_link(connection, launch_id)
    executable = codex_app_executable()
    try:
        # ShellExecute's packaged URI activation silently fails on the tested host.
        # Direct argv preserves the nested URL and reaches the existing instance.
        subprocess.Popen([str(executable), '--single-argument', link], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    except OSError:
        launch_log('host_start_failed', launch_id)
        raise ValueError('未能唤起 Codex，请确认桌面程序可以正常启动。') from None
    launch_log('host_requested', launch_id)
    return {'requested': True, 'destination': 'codex', 'generated': False}
