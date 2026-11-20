import json
import os
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path

from .model import next_due


class Store:
    def __init__(self, directory):
        root = Path(directory)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = root / "jobevent.sqlite3"
        self.path.touch(mode=0o600, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, config TEXT NOT NULL, kind TEXT NOT NULL, due REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sent (room TEXT, url TEXT, PRIMARY KEY(room,url), FOREIGN KEY(room) REFERENCES rooms(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, room TEXT, stamp REAL, message TEXT, FOREIGN KEY(room) REFERENCES rooms(id) ON DELETE CASCADE);
            """)

    @contextmanager
    def db(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            yield db

    def get(self, key, default=""):
        with self.db() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row[0] if row else default

    def set(self, key, val):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, val))

    def rooms(self):
        with self.db() as db:
            return [
                dict(json.loads(cfg), id=i, kind=k, due=d)
                for i, cfg, k, d in db.execute(
                    "SELECT id,config,kind,due FROM rooms ORDER BY rowid"
                )
            ]

    def save(self, i, r, kind):
        with self.db() as db:
            db.execute(
                "INSERT INTO rooms VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config,kind=excluded.kind,due=excluded.due",
                (i, json.dumps(r), kind, next_due(r, time.time())),
            )

    def delete(self, i):
        with self.db() as db:
            db.execute("DELETE FROM rooms WHERE id=?", (i,))

    def advance(self, r):
        with self.db() as db:
            db.execute(
                "UPDATE rooms SET due=? WHERE id=?", (next_due(r, time.time()), r["id"])
            )

    def seen(self, i, url):
        with self.db() as db:
            return (
                db.execute(
                    "SELECT 1 FROM sent WHERE room=? AND url=?", (i, url)
                ).fetchone()
                is not None
            )

    def delivered(self, i, url):
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO sent VALUES(?,?)", (i, url))

    def log(self, i, msg):
        with self.db() as db:
            db.execute(
                "INSERT INTO history(room,stamp,message) VALUES(?,?,?)",
                (i, time.time(), msg),
            )
            db.execute(
                "DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT 100)"
            )

    def history(self):
        with self.db() as db:
            return [
                dict(room=i, stamp=t, message=m)
                for i, t, m in db.execute(
                    "SELECT room,stamp,message FROM history ORDER BY id DESC LIMIT 30"
                )
            ]


class Vault:
    """Only native credential backends; never silently use a plaintext alternative."""

    def __init__(self, path):
        import hashlib

        self.service = (
            "jobevent-" + hashlib.sha256(os.fsencode(path.resolve())).hexdigest()[:16]
        )

    def backend(self):
        import sys

        from keyring.backends import SecretService, Windows, macOS

        backend = (
            macOS.Keyring
            if sys.platform == "darwin"
            else Windows.WinVaultKeyring
            if sys.platform == "win32"
            else SecretService.Keyring
        )()
        try:
            backend.priority
        except Exception:
            raise ValueError("운영체제 자격 증명 저장소를 열 수 없습니다.") from None
        return backend

    def get(self, key):
        return self.backend().get_password(self.service, key) or ""

    def set(self, key, value):
        b = self.backend()
        if value:
            b.set_password(self.service, key, value)
        elif b.get_password(self.service, key):
            b.delete_password(self.service, key)
