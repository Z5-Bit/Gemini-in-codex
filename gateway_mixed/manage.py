"""Local launcher and token resolver. Never sends an inference request."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap
import contextlib
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

from mgc.paths import local_urlopen, python_executable
from mgc.vault import Vault, protect

HERE = bootstrap.HERE
RECOVERY_PATCH = "429-retry-3-6"


@contextlib.contextmanager
def startup_lock():
    name = "Local\\MGCVertexGateway_" + hashlib.sha256(str(HERE).encode()).hexdigest()[:20]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise RuntimeError("无法建立启动锁")
    acquired = kernel.WaitForSingleObject(handle, 25000) in (0, 0x80)
    try:
        if not acquired:
            raise RuntimeError("网关启动繁忙，请稍后重试")
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def load_token():
    path = HERE / "state/token.dpapi"
    if not path.exists():
        data = protect(secrets.token_urlsafe(48).encode())
        path.write_bytes(data)
    return protect(path.read_bytes(), decrypt=True).decode()


def local_request(route, credential, method="GET"):
    cfg = json.loads((HERE / "settings.json").read_text(encoding="utf-8"))
    req = urllib.request.Request(f"http://127.0.0.1:{cfg['port']}{route}", method=method,
                                 headers={"Authorization": "Bearer " + credential})
    with local_urlopen(req, timeout=2) as response:
        return json.load(response)


def healthy(credential):
    try:
        value = local_request("/health", credential)
        return value.get("service") == "mgc-vertex-responses" and value.get("root") == str(HERE)
    except Exception:
        return False


def ensure_started():
    with startup_lock():
        credential = load_token()
        if healthy(credential):
            if local_request('/health',credential).get('recovery_patch') == RECOVERY_PATCH:
                return credential
            # Only an authenticated service at this exact installation is stopped.
            local_request('/admin/stop',credential,'POST')
            for _ in range(50):
                if not healthy(credential):break
                time.sleep(.1)
            else:
                raise RuntimeError('旧版网关仍在退出，请稍后重开；没有结束未知进程。')
        # Decode only, no token refresh and no network call.
        Vault().load()
        python = python_executable(windowed=True)
        if not python.exists():
            python = python_executable()
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        with (HERE / "logs/startup.log").open("ab") as log:
            proc = subprocess.Popen([str(python), "-B", str(HERE / "server.py")], cwd=HERE,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags)
        for _ in range(80):
            if healthy(credential):
                return credential
            if proc.poll() is not None:
                raise RuntimeError("网关未能启动。可能端口被占用，请查看 gateway/logs/startup.log")
            time.sleep(.2)
        # Do not kill an unknown process or change to another port silently.
        raise RuntimeError("网关启动超时，请查看 gateway/logs/startup.log")


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "token":
        # Contract: credential only on stdout, all diagnostics on stderr.
        print(ensure_started())
    elif command == "start":
        ensure_started()
        print("本机网关已启动。启动过程没有调用 Google 模型。")
    elif command == 'open':
        import mode
        mode.main()
    elif command == "stop":
        if not (HERE / "state/token.dpapi").exists():
            print("网关没有运行。")
        else:
            credential = load_token()
            if healthy(credential):
                local_request("/admin/stop", credential, "POST")
            print("已请求停止网关。")
    elif command == "status":
        path = HERE / "state/token.dpapi"
        configured = Vault().status()["configured"]
        running = healthy(load_token()) if path.exists() else False
        print(json.dumps({"credentials_readable": configured, "gateway_running": running,
                          "inference_performed": False}, ensure_ascii=False, indent=2))
    else:
        raise ValueError("Unknown command")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Credential parsing/network exceptions never dump their raw bodies here.
        message = str(error) if isinstance(error, (RuntimeError, ValueError)) else "本机操作失败，请检查路径和权限"
        print(message, file=sys.stderr)
        sys.exit(1)
