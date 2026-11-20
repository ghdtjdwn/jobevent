"""Start the multi-user web app and scheduler together, on loopback only."""

import os
import secrets
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def main():
    root = Path(".jobevent-dev").resolve()
    root.mkdir(mode=0o700, exist_ok=True)
    keyfile = root / "dev-keys"
    if not keyfile.exists():
        with os.fdopen(
            os.open(keyfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w"
        ) as f:
            f.write(
                secrets.token_urlsafe(64) + "\n" + Fernet.generate_key().decode() + "\n"
            )
    sign, cipher = keyfile.read_text().splitlines()
    env = dict(
        os.environ,
        JOBEVENT_DEV="1",
        JOBEVENT_ORIGIN="http://127.0.0.1:8000",
        JOBEVENT_DATA_DIR=str(root),
        JOBEVENT_SECRET_KEY=sign,
        JOBEVENT_ENCRYPTION_KEY=cipher,
        DJANGO_SETTINGS_MODULE="jobevent.hosted.settings",
    )
    cmd = [sys.executable, "-m", "django"]
    subprocess.run([*cmd, "migrate", "--noinput"], env=env, check=True)
    worker = subprocess.Popen([*cmd, "runworker"], env=env)
    try:
        print("개발용 회원가입: http://127.0.0.1:8000/signup", flush=True)
        subprocess.run(
            [*cmd, "runserver", "127.0.0.1:8000", "--noreload"], env=env, check=True
        )
    except KeyboardInterrupt:
        pass
    finally:
        worker.terminate()
        worker.wait()


if __name__ == "__main__":
    main()
