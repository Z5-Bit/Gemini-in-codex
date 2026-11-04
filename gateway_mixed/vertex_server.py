"""Authenticated loopback Responses endpoint for the two configured Gemini models."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap
import hmac
import json
import logging
import threading
import time
import anyio
import httpx
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from google import genai
from google.genai import types
from google.oauth2 import service_account
from mgc.paths import configure_network
from mgc.vault import Vault, protect

from adapter import Prepared, RequestError, ResponseStream, compact
from state import ReplayStore, principal
from request_body import BodyTooLarge, read_body

HERE = bootstrap.HERE
GOOGLE_RETRY_DELAYS = (3, 6)
RECOVERY_PATCH = "429-retry-3-6"


class RequestCancelled(Exception):
    """The caller disconnected; do not submit another inference request."""


class CancellableStreamingResponse(StreamingResponse):
    def __init__(self, *args, cancelled, **kwargs):
        self.cancelled = cancelled
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        # Listen even on ASGI >= 2.4: waiting for the next send would otherwise
        # miss disconnects during a backoff and submit an unwanted paid request.
        try:
            async with anyio.create_task_group() as group:
                async def stream():
                    try:
                        await self.stream_response(send)
                    finally:
                        self.cancelled.set()
                        group.cancel_scope.cancel()

                async def watch_disconnect():
                    await self.listen_for_disconnect(receive)
                    self.cancelled.set()
                    group.cancel_scope.cancel()

                group.start_soon(stream)
                await watch_disconnect()
        finally:
            self.cancelled.set()
        if self.background is not None:
            await self.background()


def retry_google_chunks(backend, prepared, cancelled, progress, record):
    """Retry only Google 429 before the first upstream chunk, at most twice.

    SDK retries stay disabled. A data/usage/signature chunk ends eligibility,
    even if the adapter has not displayed it yet. Never replay partial output.
    """
    for attempt in range(1, len(GOOGLE_RETRY_DELAYS) + 2):
        if cancelled.is_set():
            raise RequestCancelled()
        progress["attempts"] = attempt
        source = None
        retry = False
        try:
            source = iter(backend.chunks(prepared))
            for chunk in source:
                if cancelled.is_set():
                    raise RequestCancelled()
                progress["upstream_chunks"] += 1
                yield chunk
            return
        except Exception as error:
            if cancelled.is_set():
                raise RequestCancelled() from None
            if (getattr(error, "code", None) != 429 or progress["upstream_chunks"]
                    or attempt > len(GOOGLE_RETRY_DELAYS)):
                raise
            retry = True
        finally:
            if source is not None and hasattr(source, "close"):
                try:
                    source.close()
                except Exception:
                    pass  # Cleanup must not mask the original, sanitized error.
        if retry:
            delay = GOOGLE_RETRY_DELAYS[attempt - 1]
            record({"status": "retry_scheduled", "http_status": 429,
                    "attempt": attempt, "next_attempt": attempt + 1,
                    "retry_delay_seconds": delay, "upstream_chunks": 0})
            if cancelled.wait(delay):
                raise RequestCancelled()


def diagnostic(error):
    text = str(getattr(error, 'message', '') or error).lower()
    groups = {
        'chat_sequence': ('requests ending with a model turn', 'prefilled model turn'),
        'payload_size': ('request too large', 'payload too large', 'request payload size'),
        'context_limit': ('context length', 'token limit', 'too many tokens', 'input token count', 'maximum number of tokens'),
        'tool_history': ('function call', 'functioncall', 'function response', 'functionresponse'),
        'thought_signature': ('thought_signature', 'thoughtsignature', 'thought signature'),
        'schema': ('schema', 'parameters', 'unknown field', 'invalid json'),
        'deadline': ('deadline_exceeded', 'deadline expired', 'deadline exceeded'),
        'rate_limit': ('resource_exhausted', 'resource exhausted', 'quota exceeded'),
        'stream_protocol': ('incomplete chunked read', 'peer closed connection'),
    }
    code = getattr(error, 'code', None)
    return {'http_status':code if isinstance(code,int) else None, 'exception_type':type(error).__name__,
            'categories':[key for key, terms in groups.items() if any(t in text for t in terms)]}


def save_failure(request_id, prepared, error, context=None):
    # Exact evidence stays encrypted; public logs contain only allowlisted categories.
    target = HERE / 'state/diagnostics'
    target.mkdir(exist_ok=True)
    body = {'request_id': request_id, 'request':prepared.request, 'contents':prepared.contents,
            'config':prepared.config, 'upstream_error':str(error), 'diagnostic':diagnostic(error),
            'transport': context or {}}
    (target / (request_id + '.dpapi')).write_bytes(protect(json.dumps(body, ensure_ascii=False, default=str).encode()))


def settings():
    value = json.loads((HERE / "settings.json").read_text(encoding="utf-8"))
    if value["host"] != "127.0.0.1" or set(value["models"]) != {"gemini-4-argon", "gemini-3.8-flash"}:
        raise ValueError("本版只允许回环监听和两个已适配的 Gemini 模型")
    return value


def token():
    return protect((HERE / "state/token.dpapi").read_bytes(), decrypt=True).decode()


def safe_error(error, attempts=1, chunks_received=0):
    if isinstance(error, RequestError):
        return str(error)
    code = getattr(error, "code", None)
    message = {400: "Google 参数校验失败", 401: "Google 凭证无效或过期", 403: "Google 权限不足或模型未开通",
               404: "Google 模型或区域不可用", 413: "Google 上游请求体超过大小限制", 429: "Google 资源暂不足、配额不足或限速（HTTP 429）",
               500: "Google 服务错误", 502: "Google 上游网关错误", 503: "Google 服务暂不可用",
               504: "Google 生成超时（HTTP 504 / DEADLINE_EXCEEDED）"}.get(code, "网络、凭证或上游调用失败")
    if isinstance(error, httpx.TimeoutException):
        message = "等待 Google 网络响应超时"
    elif isinstance(error, httpx.RemoteProtocolError):
        message = "Google 流式连接提前关闭"
    categories = diagnostic(error)['categories']
    if 'chat_sequence' in categories:
        message = 'Google 历史消息轮次格式校验失败'
    hint = '（分类：' + ', '.join(categories) + '）' if categories else ''
    if code == 429 and chunks_received:
        recovery = "已收到上游数据，为避免重复输出或工具调用未继续重试"
        if attempts > 1:
            recovery += f"（此前因 429 自动重试 {attempts - 1} 次）"
    elif code == 429 and attempts == len(GOOGLE_RETRY_DELAYS) + 1:
        recovery = "已按 3 秒、6 秒间隔自动重试 2 次，共 3 次请求仍失败"
    elif attempts > 1:
        recovery = f"此前因 429 自动重试 {attempts - 1} 次，本次错误未继续重试"
    else:
        recovery = "未自动重试"
    return message + hint + "；" + recovery + "。详细诊断保存在本机加密文件。"


def vertex_http_options(cfg):
    # The SDK converts its timeout to X-Server-Timeout. Give Google the full
    # generation budget, with a little extra socket time to receive its result.
    deadline = int(cfg["timeout_seconds"])
    return types.HttpOptions(api_version="v1", timeout=(deadline + 30) * 1000,
        headers={"X-Server-Timeout": str(deadline)},
        retry_options=types.HttpRetryOptions(attempts=1))


class VertexBackend:
    def __init__(self, cfg):
        configure_network()
        value = Vault().load()
        self.identity = principal(value)
        self.cfg = cfg
        self.client = genai.Client(vertexai=True, project=value["project"], location=cfg["location"],
            credentials=service_account.Credentials.from_service_account_info(value["account"],
                scopes=["https://www.googleapis.com/auth/cloud-platform"]),
            http_options=vertex_http_options(cfg))

    def chunks(self, prepared):
        chunks = self.client.models.generate_content_stream(model=prepared.model,
                contents=prepared.contents, config=prepared.config)
        try:
            for chunk in chunks:
                yield chunk.model_dump(mode="json", exclude_none=True)
        finally:
            chunks.close()

    def close(self):
        self.client.close()


def create_app(cfg, access_token, store, backend_factory=VertexBackend, record=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    write_lock = threading.Lock()

    def ledger(event):
        event = {"time": datetime.now(timezone.utc).isoformat(), **event}
        if record is not None:
            record(event)
            return
        with write_lock, (HERE / "logs/requests.jsonl").open("a", encoding="utf-8") as f:
            f.write(compact(event) + "\n")

    @app.middleware("http")
    async def authorization(request, call_next):
        # No browser origins/CORS: only authenticated native Codex/provider requests.
        if request.headers.get("origin") or not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + access_token):
            return JSONResponse({"error": {"message": "Unauthorized", "type": "authentication_error"}}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"ok": True, "service": "mgc-vertex-responses", "version": "0.1.3", "root": str(HERE),
                "recovery_patch": RECOVERY_PATCH, "google_retry_delays_seconds": list(GOOGLE_RETRY_DELAYS),
                "max_request_bytes": cfg['max_request_bytes'], "thought_summaries": cfg.get('thought_summaries', True)}

    @app.get("/v1/models")
    def models():
        return json.loads((HERE / "models.json").read_text(encoding="utf-8"))

    @app.post("/admin/stop")
    def stop():
        app.state.stop_requested = True
        if hasattr(app.state, "server"):
            app.state.server.should_exit = True
        return {"ok": True}

    @app.post("/v1/responses")
    async def responses(request: Request):
        try:
            body = await read_body(request, cfg['max_request_bytes'])
        except BodyTooLarge as error:
            ledger({'status': 'rejected_before_inference', 'error_type': 'BodyTooLarge', **error.metrics})
            return JSONResponse(error.response(), status_code=413)
        input_bytes = len(body)
        backend = None
        try:
            payload = json.loads(body)
            del body
            if not isinstance(payload, dict):
                raise RequestError("请求体必须是 JSON 对象")
            # The factory loads local credentials only; no Google request until stream iteration.
            backend = backend_factory(cfg)
            prepared = Prepared(payload, cfg, store, backend.identity)
        except Exception as error:
            if backend:
                backend.close()
            message = safe_error(error)
            ledger({"status": "rejected_before_inference", "error_type": type(error).__name__})
            return JSONResponse({"error": {"message": message, "type": "invalid_request_error", "code": "gateway_request_error"}}, status_code=400)
        stream = ResponseStream(prepared)
        cancelled = threading.Event()

        def events():
            status = "disconnected"
            started = time.monotonic()
            progress = {"attempts": 0, "upstream_chunks": 0}
            def retry_record(event):
                ledger({"request_id": stream.response["id"], "model": prepared.model, **event})

            ledger({"request_id": stream.response["id"], "model": prepared.model, "route": "vertex-generateContentStream", "status": "submitted",
                    'tools':len(prepared.tools.declarations), 'history_mode':prepared.history_mode,
                    'turns':len(prepared.contents), 'input_bytes':input_bytes,
                    'deadline_seconds':cfg['timeout_seconds']})
            try:
                chunks = retry_google_chunks(backend, prepared, cancelled, progress, retry_record)
                for event in stream.run(chunks):
                    if event["type"] in ("response.completed", "response.incomplete"):
                        status = stream.response["status"]
                    yield event
            except RequestCancelled:
                status = "disconnected"
            except Exception as error:
                status = "failed"
                context = {'elapsed_ms':round((time.monotonic()-started)*1000),
                           **progress, 'deadline_seconds':cfg['timeout_seconds']}
                if record is None:
                    try:save_failure(stream.response['id'], prepared, error, context)
                    except Exception:pass
                ledger({'request_id':stream.response['id'], 'status':'upstream_error', **diagnostic(error), **context})
                yield stream.failed(safe_error(error, progress['attempts'], progress['upstream_chunks']))
            finally:
                backend.close()
                ledger({"request_id": stream.response["id"], "model": prepared.model, "status": status,
                        "usage": stream.response.get("usage"), **progress,
                        'elapsed_ms':round((time.monotonic()-started)*1000)})

        if payload.get("stream", False):
            def sse():
                for event in events():
                    yield "event: " + event["type"] + "\ndata: " + compact(event) + "\n\n"
            return CancellableStreamingResponse(sse(), cancelled=cancelled, media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        # The actual Codex path uses SSE; non-stream is provided for manual diagnostics.
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(lambda: list(events()))
        return JSONResponse(stream.response, status_code=400 if stream.response["status"] == "failed" else 200)

    return app


def main():
    import uvicorn
    logging.basicConfig(level=logging.WARNING, filename=str(HERE / "logs/server.log"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # HTTP client debug logging is deliberately off: tokens/prompts must not enter logs.
    for name in ("httpx", "httpcore", "google.auth", "google.genai"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    cfg = settings()
    app = create_app(cfg, token(), ReplayStore(HERE / "state/replay.sqlite"))
    server = uvicorn.Server(uvicorn.Config(app, host=cfg["host"], port=cfg["port"],
                           access_log=False, log_config=None, timeout_graceful_shutdown=5))
    app.state.server = server
    server.run()


if __name__ == "__main__":
    main()
