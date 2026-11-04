"""0.3 composition entry; existing 0.3.3 / 0.3.0 installations stay immutable."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('original_version_modes', ROOT / 'scripts/version_modes.py')
original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
health, stop = original.health, original.stop


class CombinedSwitcher(original.Switcher):
    def __init__(self, bundle=ROOT, home=None):
        self.bundle = bundle.resolve()
        local = self.bundle / 'LOCAL-COMPONENTS.json'
        self.shared = local.is_file()
        base = self.bundle
        if self.shared:
            value = json.loads(local.read_text(encoding='utf-8'))
            base = (self.bundle / value['shared_installation']).resolve()
            if not (base / 'gateway/mode.py').is_file() or not (base / 'versions/0.3.0-timeout600/gateway_mixed/mode.py').is_file():
                raise RuntimeError('本机组合入口找不到原有两版。新设备请使用干净的 0.3 ZIP。')
        super().__init__(base=base, home=home)
        self.coordinator = base

    def component_version(self, target):
        return '0.3.0' if self.shared and target == 'gateway_mixed' else '0.3.3'

    def apply(self, version, target):
        selected = self.selected(version)
        return self.run(selected, str(self.bundle / 'scripts/combined_modes.py'), '--worker',
            str(self.coordinator), str(selected), target)

    def activate(self, target):
        result = super().switch(self.component_version(target), target)
        return {'suite_version': '0.3', 'variant': 'combined', **result}

    def status(self):
        result = super().check('0.3.3')
        result['entry_version'] = result['suite_version'] = '0.3'
        result['components'] = json.loads((self.bundle / 'SUITE-COMPONENTS.json').read_text(encoding='utf-8'))['components']
        result['uses_original_local_installations'] = self.shared
        return result

    def import_credentials(self):
        if not self.shared:
            print(self.run(self.bundle, 'scripts/gateway_suite.py', 'import')); return
        statuses = [json.loads(self.run(root, 'scripts/gateway_suite.py', 'check'))
                    for root in self.roots.values()]
        if all(v['vertex_credentials_configured'] for v in statuses):
            print('本机组合入口沿用原有两版的已配置凭证，无需重新导入，原凭证没有修改。')
        else:
            raise RuntimeError('请先通过原有 Codex-Modes 和 Codex-Modes-0.3.0 的导入入口配置对应凭证。')


def worker(coordinator, selected, target):
    # Use the latest mode coordinator for saved-chat routing, while each actual
    # configure.py/server.py still comes from its requested original component.
    sys.path.insert(0, str(coordinator / 'gateway'))
    import mode
    from mgc.codex_routes import sync_routes
    result = mode.select_mode(target, root=selected, route_sync=sync_routes)
    print(json.dumps(result, ensure_ascii=False))


def main():
    if len(sys.argv) == 5 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]); return
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['gateway', 'gateway_mixed', 'original', 'check', 'stop', 'import'])
    args = parser.parse_args()
    switcher = CombinedSwitcher()
    if args.action == 'check':
        print(json.dumps(switcher.status(), ensure_ascii=False, indent=2)); return
    if args.action == 'import':
        switcher.import_credentials(); return
    executable = original.desktop_closed()
    with original.lock(switcher.storage):
        if args.action == 'stop':
            switcher.stop_all(); print('已停止组合版使用的后台网关。'); return
        print(json.dumps(switcher.activate(args.action), ensure_ascii=False, indent=2))
    subprocess.Popen([str(executable)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('0.3 组合版：非混合使用 0.3.3 最新版；混合使用 0.3.0 超时修正版。')
    print('GPT 额度或登录异常时，请完全退出 Codex 后运行 01-Gemini.cmd。')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr); sys.exit(1)
    except Exception:
        print('组合模式操作失败；没有输出私有配置，请保留恢复记录。', file=sys.stderr); sys.exit(1)
