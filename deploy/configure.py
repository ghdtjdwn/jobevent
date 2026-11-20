"""Create a deployment env file locally; never print keys or overwrite config."""

import argparse
import base64
import os
import re
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Jobevent 배포 설정 생성")
    parser.add_argument("domain", help="HTTPS로 서비스할 공개 도메인")
    args = parser.parse_args()
    if not re.fullmatch(
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}",
        args.domain,
    ):
        parser.error("포트·경로 없이 도메인만 입력하세요.")
    path = Path(".env")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        parser.exit(1, "기존 .env를 유지했습니다. 덮어쓰지 않습니다.\n")
    with os.fdopen(fd, "w") as stream:
        stream.write(
            f"JOBEVENT_DOMAIN={args.domain}\nJOBEVENT_ORIGIN=https://{args.domain}\nJOBEVENT_SECRET_KEY={secrets.token_urlsafe(64)}\nJOBEVENT_ENCRYPTION_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}\n"
        )
    print(".env를 생성했습니다. Git에 추가하지 말고 안전한 곳에 별도 백업하세요.")


if __name__ == "__main__":
    main()
