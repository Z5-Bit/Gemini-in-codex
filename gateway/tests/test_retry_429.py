"""Offline recovery tests. Run each gateway directory in a separate pytest process."""
import asyncio, contextlib, inspect, json, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
import httpx, pytest
from fastapi.testclient import TestClient
from google import genai
from google.auth.credentials import AnonymousCredentials
from google.genai import errors

HOME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HOME))
import bootstrap
MIXED=HOME.name=='gateway_mixed'
if MIXED:
    import vertex_server as google
    import server as router
else:
    import server as google

def failure(code):
    return errors.APIError(code,{'error':{'code':code,'message':'private-fixture-must-not-leak'}})

OK={'candidates':[{'content':{'role':'model','parts':[{'text':'OK'}]},'finish_reason':'STOP'}]}

class FakeCancel:
    def __init__(self): self.delays=[]; self.stopped=False
    def is_set(self):return self.stopped
    def set(self):self.stopped=True
    def wait(self,delay):self.delays.append(delay);return self.stopped

class Store:
    def get(self,k):return None
    def put(self,k,v):pass

def backend_for(outcomes):
    calls=[];closed=[]
    class Backend:
        identity='offline-fixture'
        def __init__(self,cfg):pass
        def close(self):closed.append(True)
        def chunks(self,prepared):
            index=len(calls);calls.append(prepared)
            try:
                for value in outcomes[min(index,len(outcomes)-1)]:
                    if isinstance(value,Exception):raise value
                    yield value
            finally:closed.append(index)
    return Backend,calls,closed

@pytest.mark.parametrize('failures',[0,1,2,3])
@pytest.mark.parametrize('stream',[False,True])
def test_boundaries_and_per_request_delays(monkeypatch,failures,stream):
    Backend,calls,closed=backend_for([[failure(429)]]*failures+[[OK]])
    events=[];cancelled=[]
    def event():x=FakeCancel();cancelled.append(x);return x
    monkeypatch.setattr(google,'threading',SimpleNamespace(Event=event,Lock=threading.Lock))
    app=google.create_app(google.settings(),'fixture-local',Store(),Backend,events.append)
    if MIXED:
        app=router.MixedRouter(google.settings(),'fixture-local',app,
            {'models':[{'slug':'gpt-offline-fixture'}]},record=events.append)
        url='/backend-api/codex/responses';headers={'x-mgc-local-token':'fixture-local'}
    else:url='/v1/responses';headers={'authorization':'Bearer fixture-local'}
    response=TestClient(app).post(url,headers=headers,json={'model':'gemini-4-argon','input':'fixture','stream':stream})
    expected=min(failures+1,3)
    assert len(calls)==expected
    assert all(p is calls[0] for p in calls)
    assert cancelled[0].delays==[3,6][:expected-1]
    assert [e['retry_delay_seconds'] for e in events if e['status']=='retry_scheduled']==[3,6][:expected-1]
    assert closed.count(True)>=1
    assert 'private-fixture-must-not-leak' not in response.text+json.dumps(events)
    if failures==3:
        assert '共 3 次请求仍失败' in response.text
        assert ('event: response.failed\n' in response.text) if stream else response.status_code==400
        assert 'event: response.completed\n' not in response.text
    else:
        assert response.status_code==200 and 'OK' in response.text
        assert response.text.count('event: response.created\n')==int(stream)
        assert response.text.count('event: response.completed\n')==int(stream)
    final=[e for e in events if e['status'] in ('completed','failed')][-1]
    assert final['attempts']==expected and final['upstream_chunks']==(failures<3)

@pytest.mark.parametrize('error',[failure(400),failure(401),failure(403),failure(413),failure(500),failure(503),failure(504),httpx.ReadTimeout('fixture'),httpx.RemoteProtocolError('fixture')])
def test_non429_never_replayed(error):
    Backend,calls,closed=backend_for([[error]]);cancel=FakeCancel();progress={'attempts':0,'upstream_chunks':0}
    with pytest.raises(type(error)):
        list(google.retry_google_chunks(Backend({}),object(),cancel,progress,lambda e:None))
    assert len(calls)==1 and cancel.delays==[]

@pytest.mark.parametrize('partial',[
    {'candidates':[{'content':{'parts':[{'text':'partial'}]}}]},
    {'usage_metadata':{'prompt_token_count':1}},
    {'candidates':[{'content':{'parts':[{'thought':True,'text':'public summary'}]}}]},
    {'candidates':[{'content':{'parts':[{'thought_signature':'fixture'}]}}]},
    {'candidates':[{'content':{'parts':[{'function_call':{'name':'fixture','args':{}}}]}}]},
    {},
])
def test_even_invisible_chunk_disables_replay(partial):
    Backend,calls,closed=backend_for([[partial,failure(429)]]);cancel=FakeCancel();progress={'attempts':0,'upstream_chunks':0}
    iterator=google.retry_google_chunks(Backend({}),object(),cancel,progress,lambda e:None)
    assert next(iterator)==partial
    with pytest.raises(errors.APIError):next(iterator)
    assert len(calls)==1 and cancel.delays==[] and progress['upstream_chunks']==1
    assert '避免重复' in google.safe_error(failure(429),1,1)

def test_retry_then_other_failure_stops():
    Backend,calls,_=backend_for([[failure(429)],[failure(504)],[OK]])
    cancel=FakeCancel();progress={'attempts':0,'upstream_chunks':0}
    with pytest.raises(errors.APIError):list(google.retry_google_chunks(Backend({}),None,cancel,progress,lambda e:None))
    assert len(calls)==2 and cancel.delays==[3]
    assert '本次错误未继续重试' in google.safe_error(failure(504),2,0)

def test_cancel_before_or_during_wait():
    for initially in (True,False):
        Backend,calls,_=backend_for([[failure(429)],[OK]]);cancel=FakeCancel();cancel.stopped=initially
        def record(event):cancel.set()
        with pytest.raises(google.RequestCancelled):
            list(google.retry_google_chunks(Backend({}),None,cancel,{'attempts':0,'upstream_chunks':0},record))
        assert len(calls)==int(not initially)

@pytest.mark.parametrize('spec',['2.3','2.4'])
def test_real_event_disconnect_during_backoff_is_prompt(spec):
    async def run():
        cancel=threading.Event();scheduled=threading.Event();calls=[]
        class Backend:
            def chunks(self,_):
                calls.append(True)
                raise failure(429)
                yield
        def content():
            try:
                yield from google.retry_google_chunks(Backend(),None,cancel,
                    {'attempts':0,'upstream_chunks':0},lambda _:scheduled.set())
            except google.RequestCancelled:pass
        async def receive():
            while not scheduled.is_set():await asyncio.sleep(.005)
            return {'type':'http.disconnect'}
        async def send(message):pass
        response=google.CancellableStreamingResponse(content(),cancelled=cancel)
        start=time.monotonic()
        await asyncio.wait_for(response({'type':'http','asgi':{'spec_version':spec}},receive,send),2)
        assert time.monotonic()-start<2 and len(calls)==1 and cancel.is_set()
    asyncio.run(run())

def test_retry_budget_resets_and_error_redaction():
    for _ in range(2):
        Backend,calls,_=backend_for([[failure(429)],[failure(429)],[OK]])
        cancel=FakeCancel();progress={'attempts':0,'upstream_chunks':0}
        assert list(google.retry_google_chunks(Backend({}),None,cancel,progress,lambda e:None))==[OK]
        assert len(calls)==3 and cancel.delays==[3,6]
    for error in (failure(429),failure(504),httpx.ReadTimeout('private-fixture-must-not-leak'),httpx.RemoteProtocolError('private-fixture-must-not-leak')):
        assert 'private-fixture-must-not-leak' not in google.safe_error(error)
    assert '生成超时' in google.safe_error(failure(504))
    assert '网络响应超时' in google.safe_error(httpx.ReadTimeout('fixture'))
    assert '流式连接提前关闭' in google.safe_error(httpx.RemoteProtocolError('fixture'))

def test_sdk_wire_no_multiplied_retries_and_deadline_unchanged():
    requests=[]
    def upstream(request):
        requests.append(request)
        if len(requests)<3:return httpx.Response(429,json={'error':{'code':429,'status':'RESOURCE_EXHAUSTED','message':'fixture'}})
        return httpx.Response(200,headers={'content-type':'text/event-stream'},text='data: '+json.dumps(OK)+'\n\n')
    options=google.vertex_http_options({'timeout_seconds':600})
    assert options.retry_options.attempts==1
    options.client_args={'transport':httpx.MockTransport(upstream),'trust_env':False}
    credentials=AnonymousCredentials();credentials.token='offline-fixture'
    with genai.Client(vertexai=True,project='offline-fixture',location='global',credentials=credentials,http_options=options) as client:
        backend=google.VertexBackend.__new__(google.VertexBackend);backend.client=client
        cancel=FakeCancel();progress={'attempts':0,'upstream_chunks':0}
        prepared=SimpleNamespace(model='gemini-4-argon',contents='fixture',config={})
        result=list(google.retry_google_chunks(backend,prepared,cancel,progress,lambda e:None))
    assert len(requests)==3 and cancel.delays==[3,6] and result
    assert len({r.content for r in requests})==1
    assert all(r.headers['x-server-timeout']=='600' and r.extensions['timeout']['read']==630 for r in requests)

@pytest.mark.skipif(not MIXED,reason='mixed route only')
def test_gpt_429_unchanged_and_no_auth_leak(monkeypatch):
    captured=[]
    def upstream(request):captured.append(request);return httpx.Response(429,json={'error':{'message':'fixture'}})
    async def google_app(*args):raise AssertionError('GPT must never fall back to Google')
    class Auth:
        def __call__(self):return {'authorization':'Bearer offline-native','chatgpt-account-id':'fixture-account'}
    kwargs={}
    if 'openai_auth' in inspect.signature(router.MixedRouter).parameters:kwargs['openai_auth']=Auth()
    app=router.MixedRouter(google.settings(),'fixture-local',google_app,{'models':[{'slug':'gpt-offline-fixture'}]},
        httpx.MockTransport(upstream),lambda e:None,**kwargs)
    body={'model':'gpt-offline-fixture','input':'fixture','stream':True,'reasoning':{'effort':'max'}}
    r=TestClient(app).post('/backend-api/codex/responses',headers={'x-mgc-local-token':'fixture-local','authorization':'Bearer offline-native'},json=body)
    assert r.status_code==429 and len(captured)==1 and json.loads(captured[0].content)==body
    assert 'x-mgc-local-token' not in captured[0].headers
    assert captured[0].extensions['timeout']['read']==660

@pytest.mark.parametrize('already_patched',[False,True])
def test_launcher_upgrades_only_owned_service(monkeypatch,tmp_path,already_patched):
    import manage
    (tmp_path/'logs').mkdir();state={'running':True};actions=[]
    monkeypatch.setattr(manage,'HERE',tmp_path)
    monkeypatch.setattr(manage,'startup_lock',contextlib.nullcontext)
    monkeypatch.setattr(manage,'load_token',lambda:'offline-token')
    monkeypatch.setattr(manage,'healthy',lambda _:state['running'])
    current={'version':getattr(manage,'SERVICE_VERSION','legacy'),'recovery_patch':manage.RECOVERY_PATCH if already_patched else None}
    if MIXED and hasattr(router,'native_auth_scope'):
        import openai_auth
        monkeypatch.setattr(openai_auth,'native_auth_scope',lambda:'fixture-scope')
        current['openai_auth_scope']='fixture-scope'
    def request(route,token,method='GET'):
        assert token=='offline-token';actions.append((route,method))
        if route=='/admin/stop':state['running']=False
        return current
    monkeypatch.setattr(manage,'local_request',request)
    monkeypatch.setattr(manage.Vault,'load',lambda _:None)
    def launch(*args,**kwargs):state['running']=True;actions.append(('launch','own'));return SimpleNamespace(poll=lambda:None)
    monkeypatch.setattr(manage.subprocess,'Popen',launch)
    assert manage.ensure_started()=='offline-token'
    assert (('/admin/stop','POST') in actions)==(not already_patched)
    assert (('launch','own') in actions)==(not already_patched)
