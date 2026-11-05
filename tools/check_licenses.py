"""Check retained license texts and the release allowlist without a runtime or network."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    inventory=json.loads((ROOT/'THIRD-PARTY-INVENTORY.json').read_text('utf-8'))
    plan=json.loads((ROOT/'RELEASE-PLAN.json').read_text('utf-8'))
    findings=[]
    files={'LICENSE':{'sha256':inventory['project_license_file_sha256']},**inventory['notice_files']}
    for relative,record in files.items():
        path=ROOT/relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            findings.append({'file':relative,'rule':'license_text_missing_or_changed'})
        if plan['source_files'].get(relative)!=relative:
            findings.append({'file':relative,'rule':'license_excluded_from_release'})
    for component in inventory['components']:
        if not component['notice_copies']:
            findings.append({'component':component['name'],'rule':'no_retained_notice'})
        for relative in component['notice_copies']:
            if relative not in files:
                findings.append({'file':relative,'rule':'notice_not_in_inventory'})
    for relative in ['LICENSING.md','THIRD-PARTY-NOTICES.md','THIRD-PARTY-INVENTORY.json','CORRESPONDING-SOURCE.md']:
        if not (ROOT/relative).is_file() or plan['source_files'].get(relative)!=relative:
            findings.append({'file':relative,'rule':'missing_release_license_document'})
    if (ROOT/'app/package.json').exists():
        package=json.loads((ROOT/'app/package.json').read_text('utf-8'))
        lock=json.loads((ROOT/'app/package-lock.json').read_text('utf-8'))
        if package['license']!='MIT AND ISC' or lock['packages']['']['license']!=package['license']:
            findings.append({'rule':'upstream_and_project_license_metadata_mismatch'})
    print(json.dumps({'passed':not findings,'license':inventory['project_license'],
                      'notice_files':len(inventory['notice_files']),'components':len(inventory['components']),
                      'findings':findings},ensure_ascii=False,indent=2))
    return 1 if findings else 0

if __name__=='__main__':sys.exit(main())
