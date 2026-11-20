"""Bound hosted PDF parsing in a short-lived process without service credentials."""

import base64
import subprocess
import sys


def extract(encoded):
    try:
        if not isinstance(encoded, str) or len(encoded) > 5_333_336:
            raise ValueError
        data = base64.b64decode(encoded, validate=True)
        if (
            len(data) > 4_000_000
            or not data.startswith(b"%PDF-")
            or sys.platform not in ("linux", "darwin")
        ):
            raise ValueError
        result = subprocess.run(
            [sys.executable, "-I", "-m", "jobevent.hosted.pdf"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=12,
            check=True,
            env={},
        )
        return result.stdout.decode()
    except (ValueError, subprocess.SubprocessError, UnicodeError, OSError) as e:
        raise ValueError(
            "PDF를 읽지 못했습니다. 텍스트 PDF(4MB·40쪽 이하)나 직접 입력을 사용하세요."
        ) from e


def main():
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (6, 6))
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024**2, 384 * 1024**2))
    from jobevent.imports import pdf_text

    sys.stdout.buffer.write(pdf_text(sys.stdin.buffer.read(4_000_001)).encode())


if __name__ == "__main__":
    main()
