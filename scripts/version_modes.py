"""Local cross-install launcher; delegates inference and mode logic unchanged.

Only registered sibling installations are considered. No cloud requests, native
login copying, unknown process termination, or direct Codex chat database edits.
"""
import argparse
import base64
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('gateway', 'gateway_mixed')
PROVIDERS = {'mgc_vertex_gateway': 'gateway', 'mgc_mixed_gateway': 'gateway_mixed'}
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.version-pending')
    pending.write_bytes(data)
    pending.replace(path)


def crypt(data, decrypt=False):
    sys.path.insert(0, str(ROOT / 'src'))
    from mgc.vault import protect
    return protect(data, decrypt=decrypt)


def worker(root, target):
    # A fresh interpreter loads ONLY the selected installation's mode code.
    sys.path.insert(0, str(root / 'gateway'))
    import mode
    options = {}
    if (root / 'src/mgc/codex_routes.py').is_file():
        from mgc.codex_routes import sync_routes
        options['route_sync'] = sync_routes
    result = mode.select_mode(target, root=root, **options)
    print(json.dumps(result, ensure_ascii=False))


def python_for(root):
    path = root / 'runtime/python/python.exe'
    if not path.is_file():
        raise RuntimeError('便携 Python 缺失，请保留完整版本目录。')
    return path


def loopback(folder, route='/health', method='GET'):
    token_path = folder / 'state/token.dpapi'
    if not token_path.is_file():
        return None
    settings = json.loads((folder / 'settings.json').read_text(encoding='utf-8'))
    token = crypt(token_path.read_bytes(), decrypt=True).decode()
    request = urllib.request.Request(f"http://127.0.0.1:{int(settings['port'])}{route}",
        method=method, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=2) as reply:
        return json.load(reply)


def health(folder):
    try:
        result = loopback(folder)
        if (result and result.get('service') == 'mgc-vertex-responses'
                and Path(result.get('root', '')).resolve() == folder.resolve()):
            return result
    except Exception:
        pass
    return None


def stop(folder):
    if not health(folder):
        return
    loopback(folder, '/admin/stop', 'POST')
    for _ in range(80):
        if not health(folder):
            return
        time.sleep(.1)
    raise RuntimeError('所属网关尚未退出，未结束未知进程；请稍后再试。')


def merge_replay(source, destination):
    """Append encrypted records only; never replace or delete an existing item."""
    if not source.is_file() or source.resolve() == destination.resolve():
        return 0
    with contextlib.closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as src:
        rows = src.execute('SELECT id, body FROM items').fetchall()
    if not rows:
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(destination, timeout=15)) as dst, dst:
        dst.execute('CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, body BLOB NOT NULL)')
        # DPAPI ciphertext is copied intact. Account-scoping is still enforced
        # by each original adapter when it reads a record.
        before = dst.total_changes
        dst.executemany('INSERT OR IGNORE INTO items (id, body) VALUES (?, ?)', rows)
        return dst.total_changes - before


class Switcher:
    def __init__(self, base=ROOT, home=None):
        self.base = base.resolve()
        self.home = (home or Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))).resolve()
        self.config = self.home / 'config.toml'
        self.roots = {'0.3.3': self.base}
        old = self.base / 'versions/0.3.0-timeout600'
        if (old / 'gateway/mode.py').is_file():
            self.roots['0.3.0'] = old
        self.storage = self.base / 'runtime/version-switch'

    def selected(self, version):
        if version not in self.roots:
            raise RuntimeError('未找到所选版本，请保留完整 versions 目录。')
        return self.roots[version]

    def read_config(self):
        return tomllib.loads(self.config.read_text(encoding='utf-8-sig')) if self.config.exists() else {}

    def active(self):
        cfg = self.read_config()
        provider = cfg.get('model_provider', 'openai')
        if provider == 'openai':
            return None, 'original'
        if provider not in PROVIDERS:
            raise RuntimeError('当前是其他提供商，请先恢复原生 Codex 后再切换。')
        folder = PROVIDERS[provider]
        catalog = Path(cfg.get('model_catalog_json', '')).resolve()
        for version, root in self.roots.items():
            if catalog == (root / folder / 'models.json').resolve():
                return version, folder
        raise RuntimeError('当前网关不属于这两个版本，未改写未知安装的配置。')

    def run(self, root, relative, *args):
        completed = subprocess.run([str(python_for(root)), '-B', str(root / relative), *args],
            cwd=root, env={**os.environ, 'CODEX_HOME': str(self.home), 'MGC_ROOT': str(root),
                'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1',
                'TEMP': str(root / 'runtime/temp'), 'TMP': str(root / 'runtime/temp')},
            capture_output=True, encoding='utf-8', creationflags=FLAGS)
        if completed.returncode:
            # Do not expose captured credentials, private config, or upstream text.
            raise RuntimeError('所选版本配置操作失败；请查看本机切换恢复记录。')
        return completed.stdout

    def restore_active(self):
        version, folder = self.active()
        records = []
        for root in self.roots.values():
            for name in FOLDERS:
                path = root / name / 'backups/activation.json'
                if path.is_file():
                    info = json.loads(path.read_text(encoding='utf-8'))
                    if Path(info['config']).resolve() != self.config:
                        raise RuntimeError('已有激活记录属于另一 CODEX_HOME，未修改其配置。')
                    records.append((root, name))
        expected = [(self.roots[version], folder)] if version else []
        if records != expected:
            raise RuntimeError('当前配置与版本恢复记录不一致；未覆盖现有记录。')
        if version:
            self.run(self.roots[version], folder + '/configure.py', 'restore')

    def ensure_credentials(self, target):
        destination = target / 'secrets/credentials.dpapi'
        if destination.exists():
            return
        source = self.base / 'secrets/credentials.dpapi'
        if not source.is_file():
            raise RuntimeError('请先运行该版本的 00-Import-VertexAI.cmd 导入凭证。')
        # Same-user encrypted local copy. Never copy plaintext JSON or native login.
        crypt(source.read_bytes(), decrypt=True)
        atomic(destination, source.read_bytes())

    def transfer_replay(self, target):
        count = 0
        for root in self.roots.values():
            if root == target:
                continue
            for folder in FOLDERS:
                count += merge_replay(root / folder / 'state/replay.sqlite',
                                      target / folder / 'state/replay.sqlite')
        return count

    def stop_all(self):
        for root in self.roots.values():
            for folder in FOLDERS:
                stop(root / folder)

    def apply(self, version, target):
        root = self.selected(version)
        return self.run(root, str(ROOT / 'scripts/version_modes.py'), '--worker', str(root), target)

    def switch(self, version, target):
        root = self.selected(version)
        if target not in (*FOLDERS, 'original'):
            raise ValueError('Unknown mode')
        cfg = self.read_config()
        if cfg.get('profile'):
            raise RuntimeError('请先取消命名 profile，避免覆盖所选模式。')
        self.active()  # Refuse unknown installations before any mutation.
        if target != 'original':
            self.ensure_credentials(root)
        tracked = [self.config]
        for install in self.roots.values():
            for name in FOLDERS:
                tracked.extend(install / name / 'backups' / p for p in ('activation.json', 'config-before.dpapi'))
        before = {str(p): base64.b64encode(p.read_bytes()).decode() if p.exists() else None for p in tracked}
        running = [(r, f) for r in self.roots.values() for f in FOLDERS if health(r / f)]
        self.storage.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        journal = self.storage / f'before-switch-{stamp}.dpapi'
        record = {'status': 'switching', 'home': str(self.home), 'version': version, 'target': target, 'files': before}
        atomic(journal, crypt(json.dumps(record).encode()))
        try:
            self.stop_all()
            if target != 'original':
                port = json.loads((root / target / 'settings.json').read_text())['port']
                with socket.socket() as probe:
                    probe.settimeout(.3)
                    if probe.connect_ex(('127.0.0.1', int(port))) == 0:
                        raise RuntimeError('目标端口被其他进程占用，未结束或接管该进程。')
            self.restore_active()
            copied = self.transfer_replay(root) if target != 'original' else 0
            result = self.apply(version, target)
        except Exception as error:
            try:
                self.stop_all()
                for path, data in before.items():
                    if data is None:
                        Path(path).unlink(missing_ok=True)
                    else:
                        atomic(Path(path), base64.b64decode(data))
                for install, name in running:
                    self.run(install, name + '/manage.py', 'start')
                record['status'] = 'rolled_back'
                message = '切换失败；已恢复切换前的配置和运行状态。'
            except Exception:
                record['status'] = 'recovery_required'
                message = '切换未完成；已保存加密恢复记录，请勿删除 runtime/version-switch。'
            atomic(journal, crypt(json.dumps(record).encode()))
            raise RuntimeError(message + ' ' + str(error)) from None
        # Commit metadata errors must not roll back a successful official route sync.
        record['status'] = 'complete'
        try:
            atomic(journal, crypt(json.dumps(record).encode()))
        except OSError:
            pass
        return {'selected_version': version, 'mode': target, 'signature_records_added': copied,
                'selected_mode_result': json.loads(result), 'inference_performed': False}

    def check(self, version):
        root = self.selected(version)
        active, mode = self.active()
        status = json.loads(self.run(root, 'scripts/gateway_suite.py', 'check'))
        status.update(entry_version=version, active_version=active or 'native',
                      active_mode=mode, installation=str(root),
                      google_deadline_seconds=json.loads((root / 'gateway/settings.json').read_text(encoding='utf-8'))['timeout_seconds'])
        status['running_services'] = [
            {'installation_version': v, 'mode': f, 'core_version': info.get('version')}
            for v, install in self.roots.items() for f in FOLDERS
            if (info := health(install / f))]
        return status


@contextlib.contextmanager
def lock(storage):
    import msvcrt
    storage.mkdir(parents=True, exist_ok=True)
    with (storage / 'switch.lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('另一个切换入口正在运行，请等待完成后再操作。') from None
        try:
            yield
        finally:
            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def desktop_closed():
    sys.path.insert(0, str(ROOT / 'src'))
    from mgc.codex_open import codex_app_executable
    executable = codex_app_executable()
    ps = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    script = "@(Get-Process -Name Codex,ChatGPT -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq '" + str(executable).replace("'", "''") + "' }).Count"
    result = subprocess.run([str(ps), '-NoProfile', '-NonInteractive', '-Command', script],
        capture_output=True, text=True, timeout=15, creationflags=FLAGS)
    if result.returncode or not result.stdout.strip().isdigit():
        raise RuntimeError('无法确认 Codex 是否完全退出，配置未修改。')
    if int(result.stdout.strip()):
        raise RuntimeError('请先保存工作并完全退出 Codex，再双击此入口；当前配置未修改。')
    return executable


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]).resolve(), sys.argv[3]); return
    parser = argparse.ArgumentParser()
    parser.add_argument('version', choices=['0.3.3', '0.3.0'])
    parser.add_argument('action', choices=['gateway', 'gateway_mixed', 'original', 'check', 'stop', 'import'])
    args = parser.parse_args()
    switcher = Switcher()
    root = switcher.selected(args.version)
    if args.action == 'check':
        print(json.dumps(switcher.check(args.version), ensure_ascii=False, indent=2)); return
    if args.action == 'import':
        print(switcher.run(root, 'scripts/gateway_suite.py', 'import')); return
    executable = desktop_closed()
    with lock(switcher.storage):
        if args.action == 'stop':
            switcher.stop_all(); print('已停止这两个版本所属的后台网关。'); return
        result = switcher.switch(args.version, args.action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    subprocess.Popen([str(executable)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=FLAGS)
    print('已选择版本和模式并打开 Codex。普通 Codex 快捷方式沿用最近选择。')
    if args.version == '0.3.0':
        print('0.3.0 仅延长超时；未包含新版额度隔离及历史兼容修复。旧聊天请自行选择该模式支持的模型。')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr); sys.exit(1)
    except Exception:
        print('版本切换失败，请检查路径或权限；未输出私有配置。', file=sys.stderr); sys.exit(1)
