"""Persist exact Google parts (including thought signatures) with Windows DPAPI."""
import hashlib
import json
import sqlite3
import threading

from mgc.vault import protect


class ReplayStore:
    def __init__(self, path, crypt=protect):
        self.path, self.crypt = path, crypt
        self.lock = threading.Lock()
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, body BLOB NOT NULL)")

    def connection(self):
        return sqlite3.connect(self.path, timeout=15)

    def put(self, key, value):
        encrypted = self.crypt(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        with self.lock, self.connection() as db:
            db.execute("INSERT OR REPLACE INTO items VALUES (?, ?)", (key, encrypted))

    def get(self, key):
        if not key:
            return None
        with self.connection() as db:
            row = db.execute("SELECT body FROM items WHERE id = ?", (key,)).fetchone()
        return json.loads(self.crypt(row[0], decrypt=True)) if row else None


def principal(config):
    value = config["project"] + "|" + config["account"]["client_email"]
    return hashlib.sha256(value.encode()).hexdigest()


class ReadOnlyReplayStore(ReplayStore):
    def __init__(self, path, crypt=protect):
        self.path, self.crypt = path, crypt

    def connection(self):
        return sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=15)

    def get(self, key):
        return super().get(key) if self.path.is_file() else None

    def put(self, key, value):
        raise RuntimeError('Read-only replay store')


class CompatibleReplayStore:
    """Both modes can read existing signatures; each writes only its own state."""
    def __init__(self, primary, legacy=None):
        self.primary, self.legacy = primary, legacy

    def get(self, key):
        return self.primary.get(key) or (self.legacy.get(key) if self.legacy else None)

    def put(self, key, value):
        self.primary.put(key, value)


def mode_replay_store(directory):
    other = 'gateway_mixed' if directory.name == 'gateway' else 'gateway'
    return CompatibleReplayStore(ReplayStore(directory / 'state/replay.sqlite'),
        ReadOnlyReplayStore(directory.parent / other / 'state/replay.sqlite'))
