"""Keep saved desktop chats consistent with the selected portable mode.

Use installed Codex's documented RPCs, never edit its databases or transcripts.
Only local, unarchived desktop chats on our two providers or native OpenAI are
eligible. No turn/start, inference, credential refresh or tool execution occurs.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

from mgc.vault import protect

PROVIDERS = ('openai', 'mgc_vertex_gateway', 'mgc_mixed_gateway')
TARGETS = {'original':'openai', 'gateway':'mgc_vertex_gateway', 'gateway_mixed':'mgc_mixed_gateway'}
GOOGLE = ('gemini-4-argon', 'gemini-3.8-flash')


def executable():
    folder = Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'OpenAI/Codex/bin'
    choices = list(folder.glob('*/codex.exe'))
    if choices:
        return max(choices, key=lambda p:p.stat().st_mtime)
    from mgc.codex_open import codex_app_executable
    path = codex_app_executable().parent/'resources/codex.exe'
    if path.is_file():
        return path
    raise RuntimeError('未找到 Codex 的本机客户端，未更新旧对话路由。')


class Client:
    def __init__(self, home, root, exe=None):
        self.seq = 0
        self.messages = queue.Queue()
        self.process = subprocess.Popen([str(exe or executable()), '--no-daemon', '--strict-config',
            'app-server', '--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', cwd=root,
            env={**os.environ, 'CODEX_HOME':str(home), 'TEMP':str(root/'runtime/temp'),
                 'TMP':str(root/'runtime/temp')}, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def read():
            for line in self.process.stdout:
                try:self.messages.put(json.loads(line))
                except ValueError:pass
            self.messages.put(None)
        threading.Thread(target=read,daemon=True).start()
        try:
            self.call('initialize', {'clientInfo':{'name':'mgc_mode_routes','version':'0.3.2'},
                                    'capabilities':{'experimentalApi':True}})
            self.process.stdin.write('{"method":"initialized","params":{}}\n')
            self.process.stdin.flush()
        except Exception:
            self.close()
            raise

    def call(self, method, params):
        self.seq += 1
        self.process.stdin.write(json.dumps({'id':self.seq,'method':method,'params':params})+'\n')
        self.process.stdin.flush()
        deadline = time.monotonic()+90
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Codex 会话设置接口超时，未启动桌面应用。')
            try:item = self.messages.get(timeout=remaining)
            except queue.Empty:raise RuntimeError('Codex 会话设置接口超时，未启动桌面应用。') from None
            if item is None:
                raise RuntimeError('Codex 会话设置接口提前退出。')
            if item.get('id') == self.seq:
                if 'error' in item:
                    raise RuntimeError(f'Codex {method} 接口拒绝更新；未显示私有会话信息。')
                return item['result']
            if 'id' in item and 'method' in item:
                # Resuming is metadata work; never approve any interactive action.
                self.process.stdin.write(json.dumps({'id':item['id'],'error':{
                    'code':-32601,'message':'Mode switch does not execute tools or approvals'}})+'\n')
                self.process.stdin.flush()

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        for pipe in (self.process.stdin,self.process.stdout):
            if pipe:pipe.close()


def selection(target, current):
    model, effort = current['model'], current.get('reasoningEffort')
    if target == 'gateway' and model not in GOOGLE:
        model = GOOGLE[0]
    elif target == 'original' and model in GOOGLE:
        model = 'gpt-6-astra'
    if model in GOOGLE and effort not in (None,'low','medium','high'):
        effort = 'medium'
    return model, effort


def sync_routes(target, root, home=None, factory=Client, crypt=protect, source_kinds=None):
    home = home or Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))
    scope = hashlib.sha256(str(home.resolve()).casefold().encode()).hexdigest()
    client = None
    before, changed, planned = [], [], []
    folder = root/'gateway/backups';folder.mkdir(parents=True,exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    journal = folder/f'routes-before-{stamp}.dpapi'
    def save(status):
        body = {'version':1,'scope':scope,'target':target,'status':status,'before':before,'changed':changed}
        tmp=journal.with_suffix('.tmp');tmp.write_bytes(crypt(json.dumps(body).encode()));tmp.replace(journal)
    def fresh():
        nonlocal client
        if client:client.close()
        client=factory(home,root)
    def update(entry, provider, model, effort):
        reply=client.call('thread/resume',{'threadId':entry['id'],'modelProvider':provider,
                                         'model':model,'excludeTurns':True})
        if reply['modelProvider'] != provider:
            raise RuntimeError('Codex did not apply the requested provider')
        args={'threadId':entry['id'],'model':model}
        if effort is not None:args['effort']=effort
        client.call('thread/settings/update',args)
    try:
        # Recover an interrupted prior transaction through the same official API.
        for pending in sorted(folder.glob('routes-before-*.dpapi')):
            previous=json.loads(crypt(pending.read_bytes(),decrypt=True))
            if previous.get('status') not in ('updating','recovery_required'):continue
            if previous.get('scope') != scope:continue
            fresh()
            for entry in previous['before']:
                if entry['id'] in previous['changed']:
                    update(entry,entry['provider'],entry['model'],entry['effort'])
            previous['status']='rolled_back'
            tmp=pending.with_suffix('.tmp');tmp.write_bytes(crypt(json.dumps(previous).encode()));tmp.replace(pending)
        fresh()
        entries, cursor = [], None
        while True:
            page=client.call('thread/list',{'cursor':cursor,'limit':100,'archived':False,
                'modelProviders':list(PROVIDERS),'sourceKinds':source_kinds or ['vscode','appServer']})
            entries.extend(page['data']);cursor=page.get('nextCursor')
            if not cursor:break
        for entry in entries:
            current=client.call('thread/resume',{'threadId':entry['id'],'excludeTurns':True})
            if current['modelProvider'] not in PROVIDERS:continue
            model,effort=selection(target,current)
            if (current['modelProvider'],current['model'],current.get('reasoningEffort')) == (TARGETS[target],model,effort):continue
            before.append({'id':entry['id'],'provider':current['modelProvider'],
                'model':current['model'],'effort':current.get('reasoningEffort')})
            planned.append({'id':entry['id'],'model':model,'effort':effort})
        if not before:return {'updated_chats':0,'inference_performed':False}
        save('updating')
        # A loaded thread ignores provider overrides. A fresh, private App Server
        # is mandatory between read, write and verification; never use the app's daemon.
        fresh()
        for entry in planned:
            changed.append(entry['id']);save('updating')
            update(entry,TARGETS[target],entry['model'],entry['effort'])
        fresh()
        for entry in planned:
            actual=client.call('thread/resume',{'threadId':entry['id'],'excludeTurns':True})
            if actual['modelProvider']!=TARGETS[target] or actual['model']!=entry['model']:
                raise RuntimeError('Saved conversation routing failed verification')
        save('complete')
        return {'updated_chats':len(changed),'inference_performed':False}
    except Exception:
        failed=False
        if changed:
            try:fresh()
            except Exception:failed=True
            if not failed:
                for entry in reversed(before):
                    if entry['id'] not in changed:continue
                    try:update(entry,entry['provider'],entry['model'],entry['effort'])
                    except Exception:failed=True
        if before:save('recovery_required' if failed else 'rolled_back')
        raise RuntimeError('旧对话路由未全部更新，桌面应用未启动；'+
            ('部分设置未能恢复，已保留加密恢复记录。' if failed else '已恢复本次修改的会话设置。')) from None
    finally:
        if client:client.close()
