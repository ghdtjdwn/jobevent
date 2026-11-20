"""Upgrade contracts for existing encrypted settings and web/worker exclusion."""

import base64
import subprocess
import sys
from types import SimpleNamespace

from jobevent.hosted import tenants
from jobevent.store import Store


def test_hosted_store_reads_profile_written_with_cryptography_49(tmp_path, monkeypatch):
    # Test vector generated with cryptography 49.0.0 and non-secret bytes 0..31.
    monkeypatch.setattr(
        tenants,
        "settings",
        SimpleNamespace(ENCRYPTION_KEY=base64.urlsafe_b64encode(bytes(range(32)))),
    )
    Store(tmp_path).set(
        "profile",
        "gAAAAABq_5mGUzXgAW5RwiFoIf50CqokrS1cgugwAtF-IPueo2lw9Mqk2uj75Zn1t4pPOKr6Luq7sJpToYi9xewAmoE35d9Yb6YUz29jVPs6uWKB1pB8DMM=",
    )
    assert tenants.HostedStore(tmp_path).get("profile") == "synthetic profile"


def test_account_lock_excludes_another_process_until_release(tmp_path, monkeypatch):
    monkeypatch.setattr(tenants, "settings", SimpleNamespace(DATA_DIR=tmp_path))

    def contender():
        # A fresh interpreter cannot share an in-memory lock or inherit our fd.
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
from pathlib import Path
from types import SimpleNamespace
import sys
from filelock import Timeout
from jobevent.hosted import tenants
tenants.settings = SimpleNamespace(DATA_DIR=Path(sys.argv[1]))
try:
    with tenants.mutex("user-17"):
        print("acquired")
except Timeout:
    print("busy")
""",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()

    with tenants.mutex("user-17"):
        assert contender() == "busy"
    assert contender() == "acquired"
