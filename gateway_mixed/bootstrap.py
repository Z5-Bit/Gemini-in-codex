"""Paths shared by the gateway, its credential helper and local tests."""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "src"))
os.environ["MGC_ROOT"] = str(ROOT)
for folder in ("state", "logs", "temp", "backups", "generated", "tests/results"):
    (HERE / folder).mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = os.environ["TMP"] = str(HERE / "temp")

