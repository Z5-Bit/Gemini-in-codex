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
