"""Credentials only enter through a local file chooser, never model tool arguments."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import re
import threading
import os
from .paths import ROOT

_picker_lock = threading.Lock()

class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

def protect(data: bytes, decrypt=False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("凭证保险箱需要 Windows DPAPI")
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = Blob(len(data), buf), Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), "MultiGoogleCloud", None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise RuntimeError("Windows 凭证加密操作失败")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)

def read_account(path: Path):
    try:
        if path.stat().st_size > 256 * 1024:
            raise ValueError()
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) and value.get("type") == "service_account" else None
    except (OSError, ValueError, UnicodeError):
        return None


def parse_credentials(path: Path) -> dict:
    if path.stat().st_size > 256 * 1024:
        raise ValueError("登录文件过大，请选择 Google Cloud 配置 TXT")
    text = path.read_text(encoding="utf-8-sig")
    try:
        config = json.loads(text)
    except json.JSONDecodeError:
        config = {}
        lines=[line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if len(lines) in (2,3) and not any("=" in line for line in lines):
            config={"project_id":lines[0],"bucket":lines[1]}
            if len(lines)==3:
                if not lines[2].lower().endswith(".json"):
                    raise ValueError("第三行只能填写服务账号 JSON 路径；也可只保留项目和存储桶两行")
                config["service_account_file"]=lines[2]
            lines=[]
        for line in lines:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                raise ValueError("TXT 请填写项目和存储桶两行，或使用 JSON / KEY=VALUE 配置")
            config[key.strip()] = value.strip().strip('"').strip("'")
    if not isinstance(config, dict):
        raise ValueError("登录文件格式不正确")
    account = config if config.get("type") == "service_account" else config.get("service_account")
    if isinstance(account, str):
        account = json.loads(account)
    if not account and config.get("SERVICE_ACCOUNT_JSON"):
        account = json.loads(config["SERVICE_ACCOUNT_JSON"])
    if not account:
        filename = config.get("service_account_file") or config.get("GOOGLE_APPLICATION_CREDENTIALS")
        if filename:
            linked = (path.parent / filename).resolve()
            account = read_account(linked)
        else:
            candidates = [value for candidate in path.parent.glob("*.json") if (value := read_account(candidate))]
            if len(candidates) > 1:
                raise ValueError("同目录有多个服务账号，请在 TXT 第三行填写要使用的 JSON 文件名")
            account = candidates[0] if candidates else None
    if not isinstance(account, dict) or account.get("type") != "service_account":
        raise ValueError("文件中缺少 Google 服务账号凭证")
    if account.get("token_uri") not in ("https://oauth2.googleapis.com/token", "https://accounts.google.com/o/oauth2/token"):
        raise ValueError("凭证中的认证地址不是受支持的 Google 地址")
    project = config.get("project_id") or config.get("GOOGLE_CLOUD_PROJECT") or account.get("project_id")
    location = config.get("location") or config.get("GOOGLE_CLOUD_LOCATION") or "global"
    bucket = config.get("bucket") or config.get("GCS_BUCKET") or ""
    if isinstance(bucket,str):
        bucket=bucket.removeprefix("gs://").rstrip("/")
    if not isinstance(project, str) or not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise ValueError("登录文件的项目配置无效")
    if not re.fullmatch(r"[a-z0-9-]+", location) or (bucket and not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", bucket)):
        raise ValueError("登录文件的区域或存储配置无效")
    from google.oauth2 import service_account
    try:
        service_account.Credentials.from_service_account_info(account)
    except Exception:
        raise ValueError("服务账号密钥格式无效") from None
    return {"backend":"vertex","project": project, "location": location, "bucket": bucket, "account": account}

class Vault:
    def __init__(self, root=ROOT):
        self.path = root / "secrets" / "credentials.dpapi"

    def status(self):
        configured=self.path.is_file()
        if configured:
            try:self.load()
            except ValueError:configured=False
        return {"configured":configured,"backend":"vertex","label":"Vertex AI · 服务账号","storage":"Windows 用户加密"}

    def import_file(self, path):
        value = parse_credentials(Path(path))
        encrypted = protect(json.dumps(value).encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        os.replace(temporary, self.path)
        return self.status()

    def load(self):
        if not self.path.is_file():
            raise ValueError("请先选择登录 TXT 文件")
        try:
            value=json.loads(protect(self.path.read_bytes(), decrypt=True))
            if value.get("backend") != "vertex" or not isinstance(value.get("account"),dict):
                raise ValueError()
            return value
        except Exception:
            raise ValueError("无法解锁登录资料，请重新导入 TXT") from None

    def forget(self):
        self.path.unlink(missing_ok=True)
        return self.status()

def choose_files(credentials=False):
    # A genuine user-controlled Windows file dialog. No file body crosses MCP.
    with _picker_lock:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            if credentials:
                path = filedialog.askopenfilename(parent=root, title="选择 Google Cloud 登录 TXT", filetypes=[("登录 TXT", "*.txt"), ("JSON 配置", "*.json")])
                return [path] if path else []
            return list(filedialog.askopenfilenames(parent=root, title="选择要发送给 Google Cloud 的文件", filetypes=[("文件", "*.*")]))
        finally:
            root.destroy()


def choose_directory(initial):
    with _picker_lock:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        try:
            return filedialog.askdirectory(parent=root, title='选择空文件夹保存工作数据', initialdir=str(initial), mustexist=True)
        finally:
            root.destroy()
