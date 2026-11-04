"""Loopback mixed router. OpenAI credentials never reach Google."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import hmac
import json
import time
import sqlite3
import httpx
from starlette.responses import JSONResponse, StreamingResponse
from starlette.requests import Request, ClientDisconnect
from request_body import BodyTooLarge, read_body
from mgc.paths import configure_network
from state import ReplayStore
from vertex_server import create_app as create_vertex_app, VertexBackend, token, RECOVERY_PATCH, GOOGLE_RETRY_DELAYS

HERE=bootstrap.HERE


class CompatibleReplayStore:
    """Read native signed Google history from either version; write only here."""
    def __init__(self, primary, legacy=None):
        self.primary,self.legacy=primary,legacy
    def get(self,key):
        return self.primary.get(key) or (self.legacy.get(key) if self.legacy else None)
    def put(self,key,value):
        self.primary.put(key,value)


class LegacyReplayStore(ReplayStore):
    def __init__(self,path):
        from mgc.vault import protect
        self.path,self.crypt=path,protect
    def connection(self):
        return sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=15)


def openai_history(payload):
    """Remove Google-owned opaque item IDs; retain visible messages and tool IDs.

    OpenAI-native requests pass through unchanged, including encrypted reasoning.
    Google public summary items are not valid OpenAI-private reasoning state.
    """
    if not isinstance(payload.get('input'),list):return payload
    changed=False;items=[]
    for item in payload['input']:
        ident=item.get('id','')
        if ident.startswith(('rs_mgc_','msg_mgc_','fc_mgc_')):
            changed=True
            if item.get('type')=='reasoning':continue
            item={k:v for k,v in item.items() if k not in ('id','status')}
        items.append(item)
    return {**payload,'input':items} if changed else payload


class MixedRouter:
    def __init__(self, cfg, credential, google_app, catalog, transport=None, record=None):
        self.cfg,self.credential,self.google_app,self.catalog=cfg,credential,google_app,catalog
        self.transport,self.record=transport,record
        self.server=None
        self.google=set(cfg['models'])
        self.openai={m['slug'] for m in catalog['models'] if m['slug'].startswith('gpt-')}

    def log(self, model, route, status, **details):
        event={'time':time.time(),'model':model,'route':route,'status':status, **details}
        if self.record is not None:self.record(event)
        else:
            with (HERE/'logs/routes.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')

    async def __call__(self, scope, receive, send):
        if scope['type']=='lifespan':
            while True:
                message=await receive()
                if message['type']=='lifespan.startup':await send({'type':'lifespan.startup.complete'})
                elif message['type']=='lifespan.shutdown':
                    await send({'type':'lifespan.shutdown.complete'});return
        if scope['type']!='http':return
        headers={k.decode().lower():v.decode() for k,v in scope['headers']}
        path=scope['path']
        provided=headers.get('x-mgc-local-token','')
        if path in ('/health','/admin/stop'):
            provided=headers.get('authorization','').removeprefix('Bearer ')
        if headers.get('origin') or not hmac.compare_digest(provided.encode(),self.credential.encode()):
            return await JSONResponse({'error':{'message':'Unauthorized'}},401)(scope,receive,send)
        if path=='/health':
            return await JSONResponse({'ok':True,'service':'mgc-vertex-responses','version':'0.2.3-mixed','root':str(HERE),
                'recovery_patch':RECOVERY_PATCH, 'google_retry_delays_seconds':list(GOOGLE_RETRY_DELAYS),
                'max_request_bytes':self.cfg['max_request_bytes']})(scope,receive,send)
        if path=='/admin/stop':
            if self.server:self.server.should_exit=True
            return await JSONResponse({'ok':True})(scope,receive,send)
        if path in ('/backend-api/codex/models','/v1/models'):
            return await JSONResponse(self.catalog)(scope,receive,send)
        if scope['method']!='POST' or path not in ('/backend-api/codex/responses','/backend-api/codex/responses/compact'):
            return await JSONResponse({'error':{'message':'Unsupported endpoint'}},404)(scope,receive,send)
        try:
            body=await read_body(Request(scope, receive), self.cfg['max_request_bytes'])
        except ClientDisconnect:
            return
        except BodyTooLarge as error:
            self.log(None, 'local', 'rejected_before_inference', **error.metrics)
            return await JSONResponse(error.response(),413)(scope,receive,send)
        try:
            payload=json.loads(body); model=payload.get('model','')
        except Exception:
            return await JSONResponse({'error':{'message':'Expected JSON Responses request'}},400)(scope,receive,send)
        if model in self.google:
            if path.endswith('/compact'):
                return await JSONResponse({'error':{'message':'Gemini uses local text compaction, not remote compact'}},400)(scope,receive,send)
            # Codex may retain hosted OpenAI tools when switching a saved conversation.
            # Gemini can use local/MCP function tools, not those hosted endpoints.
            omitted=[t.get('type') for t in payload.get('tools',[]) if t.get('type') not in ('function','custom','namespace')]
            if omitted:
                choice=payload.get('tool_choice','auto')
                if isinstance(choice,dict) and choice.get('type') in omitted:
                    return await JSONResponse({'error':{'message':'Requested OpenAI hosted tool is unavailable on Gemini'}},400)(scope,receive,send)
                payload['tools']=[t for t in payload['tools'] if t.get('type') in ('function','custom','namespace')]
                note='On this Gemini route, OpenAI hosted tools ('+', '.join(sorted(set(omitted)))+') are unavailable. Use only the provided local/MCP tools. Do not claim hosted search or generation was performed.'
                payload['instructions']=(payload.get('instructions') or '')+'\n\n'+note
                body=bytearray(json.dumps(payload,ensure_ascii=False).encode())
            # Forward only our local credential. Do not forward OpenAI account/token/headers.
            gscope=dict(scope,path='/v1/responses',raw_path=b'/v1/responses',query_string=b'',
                headers=[(b'authorization',('Bearer '+self.credential).encode()),(b'content-type',b'application/json')])
            sent=False
            async def replay():
                nonlocal sent
                if not sent:
                    sent=True;return {'type':'http.request','body':bytes(body),'more_body':False}
                return await receive()
            self.log(model,'vertex','submitted')
            return await self.google_app(gscope,replay,send)
        if model not in self.openai:
            self.log(model if isinstance(model,str) and len(model)<100 else None,'local','unknown_model')
            return await JSONResponse({'error':{'message':'Model not in mixed catalog; no fallback'}},400)(scope,receive,send)
        if not headers.get('authorization','').startswith('Bearer '):
            return await JSONResponse({'error':{'message':'Please sign in to ChatGPT in Codex'}},401)(scope,receive,send)
        upstream='https://chatgpt.com/backend-api/codex'
        if self.cfg.get('openai_route')=='api':upstream='https://api.openai.com/v1'
        suffix='/responses/compact' if path.endswith('/compact') else '/responses'
        translated=openai_history(payload)
        if translated is not payload:body=bytearray(json.dumps(translated,ensure_ascii=False).encode())
        # Do not relay hop-by-hop/local credentials or cookies to the upstream.
        forward={k:v for k,v in headers.items() if k in ('authorization','chatgpt-account-id','content-type','accept','openai-beta','user-agent','originator') or k.startswith(('x-codex-','x-openai-'))}
        if self.cfg.get('openai_route')=='api':forward.pop('chatgpt-account-id',None)
        configure_network()
        client=httpx.AsyncClient(timeout=httpx.Timeout(max(240, self.cfg.get('timeout_seconds',180)+60),connect=30),follow_redirects=False,transport=self.transport,
                                 trust_env=self.transport is None)
        self.log(model,'openai','submitted')
        try:
            response=await client.send(client.build_request('POST',upstream+suffix,headers=forward,content=bytes(body)),stream=True)
        except Exception:
            await client.aclose();self.log(model,'openai','connection_failed')
            return await JSONResponse({'error':{'message':'OpenAI connection failed; not retried'}},502)(scope,receive,send)
        async def relay():
            try:
                async for part in response.aiter_bytes():yield part
            finally:
                await response.aclose();await client.aclose()
                self.log(model,'openai',response.status_code)
        return await StreamingResponse(relay(),status_code=response.status_code,
            headers={'content-type':response.headers.get('content-type','application/json'),'cache-control':'no-cache'})(scope,receive,send)


def main():
    import uvicorn
    cfg=json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
    catalog=json.loads((HERE/'models.json').read_text(encoding='utf-8'))
    credential=token()
    legacy=bootstrap.ROOT/'gateway/state/replay.sqlite'
    replay=CompatibleReplayStore(ReplayStore(HERE/'state/replay.sqlite'),LegacyReplayStore(legacy) if legacy.exists() else None)
    google=create_vertex_app(cfg,credential,replay)
    app=MixedRouter(cfg,credential,google,catalog)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=cfg['port'],access_log=False,log_level='warning'))
    app.server=server;server.run()

if __name__=='__main__':main()
