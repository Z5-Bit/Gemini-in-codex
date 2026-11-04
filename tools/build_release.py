"""Rebuild a portable artifact from an explicit source allowlist and verified runtime."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))


def main():
    plan=json.loads((ROOT/'RELEASE-PLAN.json').read_text(encoding='utf-8'))
    runtime=json.loads((ROOT/'RUNTIME-MANIFEST.json').read_text(encoding='utf-8'))['files']
    payload={}
    for relative,expected in runtime.items():
        p=ROOT/relative
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise SystemExit('Restore the reviewed runtime first: tools/Restore-Runtime.ps1')
        payload[relative]=p.read_bytes()
    from check_public import scan_files
    findings=scan_files(ROOT,list(plan['source_files']))
    if findings:raise SystemExit(json.dumps({'passed':False,'findings':findings}))
    for source,destination in plan['source_files'].items():
        for value in (source,destination):
            p=PurePosixPath(value)
            if p.is_absolute() or '..' in p.parts or ':' in value:raise SystemExit('Unsafe package path')
        payload[destination]=(ROOT/source).read_bytes()
    manifest={**plan['metadata'],'private_data_included':False,'files':{
        p:hashlib.sha256(data).hexdigest() for p,data in sorted(payload.items())}}
    payload['PUBLIC-PACKAGE-MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    archive=output/plan['filename']
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for relative,data in sorted(payload.items()):
            info=zipfile.ZipInfo(plan['folder']+'/'+relative,date_time=(2026,11,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'filename':archive.name,'sha256':digest,'files':len(payload)}))


if __name__=='__main__':main()
