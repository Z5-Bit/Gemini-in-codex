from pathlib import Path
import os
import re
import json
import uuid
import urllib.request

ROOT = Path(os.environ.get("MGC_ROOT", Path(__file__).resolve().parents[2])).resolve()
DEFAULT_MODEL = "gemini-4-argon"


def python_executable(windowed=False):
    name = "pythonw.exe" if windowed else "python.exe"
    portable = ROOT / "runtime/python" / name
    return portable if portable.is_file() else ROOT / "runtime/venv/Scripts" / name

def initialize():
    for name in ("data", "data/uploads", "outputs", "secrets", "runtime", "runtime/temp", "logs", "config"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    os.environ["TMP"] = os.environ["TEMP"] = str(ROOT / "runtime/temp")

def configure_network():
    """Fill missing outbound proxies from Windows even with NO_PROXY present.

    getproxies() treats a NO_PROXY-only environment as a complete proxy setup,
    suppressing Windows registry discovery. Read the registry independently.
    Explicit outbound proxy variables and user bypass rules remain intact.
    """
    environment=urllib.request.getproxies_environment()
    registry_reader=getattr(urllib.request,"getproxies_registry",None)
    proxies=registry_reader() if registry_reader else urllib.request.getproxies()
    for protocol in ("http","https"):
        name=protocol.upper()+"_PROXY"
        value=environment.get(protocol) or environment.get("all") or proxies.get(protocol)
        if not environment.get(protocol) and value:
            os.environ[name]=value
    bypass=",".join(os.environ.get(key,"") for key in ("NO_PROXY","no_proxy"))
    values=list(dict.fromkeys([x.strip() for x in bypass.split(",") if x.strip()]+["localhost","127.0.0.1","::1"]))
    os.environ["NO_PROXY"]=os.environ["no_proxy"]=",".join(values)


def local_urlopen(request, timeout):
    """Bypass proxies for the loopback broker only, without altering the process."""
    from urllib.parse import urlsplit
    url=request.full_url if isinstance(request,urllib.request.Request) else request
    parsed=urlsplit(url)
    if parsed.scheme!="http" or parsed.hostname!="127.0.0.1":
        raise ValueError("本机入口只允许回环地址")
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=timeout)

def contained(base: Path, relative: str) -> Path:
    # Resolve junctions/symlinks as well as ..; disallow Windows ADS and devices.
    if not relative or ":" in relative or "\\" in relative or Path(relative).is_absolute():
        raise ValueError("请使用工作目录内的相对文件名")
    if any(p in ("", ".", "..") or p.endswith((".", " ")) or re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", p, re.I) for p in relative.split("/")):
        raise ValueError("文件名不合法")
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()) or target == base.resolve():
        raise ValueError("文件必须位于当前任务目录")
    return target

def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)

def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("无效的记录编号")
    return value
