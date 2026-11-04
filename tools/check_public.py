"""Standard-library-only checks for files intentionally prepared for publication.

Run from any checkout: python tools/check_public.py
Use --manifest to verify the exact reviewed release snapshot too.
No network requests and no printing of detected secret values.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {'.codex', 'browser', 'secrets', 'data', 'outputs', 'logs', 'backups',
                'exports', 'downloads', 'cache', '.cache', '__pycache__', '.pytest_cache'}
PRIVATE_NAMES = {'auth.json', 'credentials.dpapi', 'local-install.json', 'connection.json',
                 'cookies', 'cookies.sqlite', 'login data', 'local state', 'local-components.json'}
PATTERNS = {
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{80,}'),
    'google_api_key': re.compile(rb'AIza[0-9A-Za-z_-]{30,}'),
    'oauth_token': re.compile(rb'ya29\.[0-9A-Za-z_-]{30,}'),
    'github_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'openai_key': re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{35,}'),
    'signed_token': re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{15,}'),
    'personal_windows_path': re.compile(rb'[A-Za-z]:(?:\\\\|\\|/)(?:Users(?:\\\\|\\|/)[A-Za-z0-9_.-]+(?:\\\\|\\|/)|Codex(?:\\\\|\\|/)Creation)', re.I),
}


def scan_bytes(relative, data):
    return [{'file': relative, 'rule': name} for name, regex in PATTERNS.items() if regex.search(data)]


def scan_files(root, files, validate_syntax=True):
    findings = []
    for relative in files:
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts or ':' in relative:
            findings.append({'file': relative, 'rule': 'unsafe_path'}); continue
        path = root / rel
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            findings.append({'file': relative, 'rule': 'non_regular_file'}); continue
        if set(p.lower() for p in rel.parts) & PRIVATE_DIRS or rel.name.lower() in PRIVATE_NAMES:
            findings.append({'file': relative, 'rule': 'private_path'})
        if path.suffix.lower() in {'.dpapi', '.sqlite', '.sqlite3', '.db', '.log', '.pyc', '.pyo', '.lnk'}:
            findings.append({'file': relative, 'rule': 'private_or_generated_file'})
        data = path.read_bytes()
        findings.extend(scan_bytes(relative, data))
        if validate_syntax and path.suffix == '.py':
            try: ast.parse(data.decode('utf-8-sig'), filename=relative)
            except (ValueError, SyntaxError, UnicodeError): findings.append({'file': relative, 'rule': 'python_syntax'})
        if path.suffix == '.json':
            try:
                value = json.loads(data.decode('utf-8-sig'))
                if isinstance(value, dict) and value.get('type') == 'service_account' and value.get('private_key'):
                    findings.append({'file': relative, 'rule': 'service_account_document'})
            except (ValueError, UnicodeError): findings.append({'file': relative, 'rule': 'invalid_json'})
    return findings


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest', action='store_true');args=parser.parse_args()
    manifest=json.loads((ROOT/'PUBLISH-MANIFEST.json').read_text(encoding='utf-8'))
    files=list(manifest['files'])+['PUBLISH-MANIFEST.json']
    if (ROOT/'.git').exists():
        result=subprocess.run(['git','-C',str(ROOT),'ls-files','-z'],capture_output=True,check=True)
        files=sorted(set(files)|set(result.stdout.decode('utf-8').strip('\0').split('\0'))-{''})
    findings=scan_files(ROOT,files)
    if args.manifest:
        for rel,digest in manifest['files'].items():
            if not (ROOT/rel).is_file() or hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:
                findings.append({'file':rel,'rule':'snapshot_hash_changed'})
    print(json.dumps({'passed':not findings,'files_checked':len(files),'findings':findings},ensure_ascii=False,indent=2))
    return 1 if findings else 0


if __name__=='__main__':sys.exit(main())
