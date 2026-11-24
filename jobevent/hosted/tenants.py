"""One authenticated user -> one directory. Caller must hold the account lock."""

import hashlib
import hmac
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from cryptography.fernet import Fernet
from django.conf import settings
from filelock import FileLock

from jobevent.app import Service
from jobevent.store import Store

PRIVATE_FIELDS = ("name", "query", "preferences", "tone", "board")


def account_dir(uid: int) -> Path:
    if type(uid) is not int or uid <= 0:
        raise ValueError("계정 식별자가 올바르지 않습니다.")
    return settings.DATA_DIR / "users" / str(uid)


def mutex(name: str) -> FileLock:
    directory = settings.DATA_DIR / "locks"
    directory.mkdir(mode=0o700, exist_ok=True)
    return FileLock(directory / f"{name}.lock", timeout=0, mode=0o600)


class HostedStore(Store):
    def __init__(self, directory):
        super().__init__(directory)
        self.cipher = Fernet(settings.ENCRYPTION_KEY)

    def encode(self, value):
        return self.cipher.encrypt(value.encode()).decode() if value else ""

    def decode(self, value):
        return self.cipher.decrypt(value.encode()).decode() if value else ""

    def set(self, key, val):
        super().set(key, self.encode(val))

    def get(self, key, default=""):
        value = super().get(key, None)
        return default if value is None else self.decode(value)

    def save(self, i, r, kind):
        # Only timing metadata is needed in plaintext to compute the next deadline.
        stored = {**r, **{k: self.encode(r[k]) for k in PRIVATE_FIELDS if k in r}}
        super().save(i, stored, kind)

    def rooms(self):
        rows = super().rooms()
        for r in rows:
            for k in PRIVATE_FIELDS:
                if k in r:
                    r[k] = self.decode(r[k])
        return rows


class HostedVault:
    def __init__(self, store):
        self.store = store

    def get(self, key):
        return self.store.get("credential:" + key)

    def set(self, key, value):
        self.store.set("credential:" + key, value)


def service_for(uid):
    store = HostedStore(account_dir(uid))
    return Service(store, HostedVault(store))


def quota(scope, subject, maximum, window, hit=True):
    """Atomic fixed-window counter, shared by all web processes. No raw IP stored.

    hit=False only checks the window, so a caller can count failures alone."""
    current = int(time.time()) // window
    ident = hmac.new(
        settings.SECRET_KEY.encode(), f"{scope}:{subject}".encode(), hashlib.sha256
    ).hexdigest()
    with (
        closing(sqlite3.connect(settings.DATA_DIR / "limits.sqlite3", timeout=5)) as db,
        db,
    ):
        db.execute(
            "CREATE TABLE IF NOT EXISTS buckets (id TEXT PRIMARY KEY, slot INTEGER, expires INTEGER, count INTEGER)"
        )
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM buckets WHERE expires <= ?", (int(time.time()),))
        row = db.execute(
            "SELECT count FROM buckets WHERE id=? AND slot=?", (ident, current)
        ).fetchone()
        if row and row[0] >= maximum:
            return False
        if not hit:
            return True
        db.execute(
            "INSERT OR REPLACE INTO buckets VALUES(?,?,?,?)",
            (ident, current, (current + 1) * window, (row[0] if row else 0) + 1),
        )
        return True
