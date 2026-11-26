"""User-initiated, credential-free import. Pin a public IP and verify TLS for the original host."""

import http.client
import ipaddress
import json
import socket
import ssl
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import quote, urlsplit

from .pipeline import public_url


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.chunks.append(data.strip())


def fetch(url):
    if not public_url(url):
        raise ValueError("공개 HTTPS 주소만 지원합니다.")
    u = urlsplit(url)
    host = u.hostname.encode("idna").decode()
    addresses = [
        i[4][0] for i in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ]
    if not addresses or not all(
        ipaddress.ip_address(a).is_global and not ipaddress.ip_address(a).is_multicast
        for a in addresses
    ):
        raise ValueError("공개 인터넷 주소만 지원합니다.")
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    conn = http.client.HTTPSConnection(host, timeout=10, context=context)
    try:
        with socket.create_connection((addresses[0], 443), timeout=10) as sock:
            conn.sock = context.wrap_socket(sock, server_hostname=host)
            path = quote(u.path or "/", safe="/%:@-._~") + (
                "?" + quote(u.query, safe="=&%+-._~") if u.query else ""
            )
            conn.request(
                "GET",
                path,
                headers={"User-Agent": "Jobevent/0.2.0", "Accept-Encoding": "identity"},
            )
            resp = conn.getresponse()
            if resp.status != 200:
                raise ValueError(
                    "페이지를 읽을 수 없습니다. 이동 후 최종 공개 주소 또는 텍스트를 사용하세요."
                )
            data = resp.read(1_000_001)
            if len(data) > 1_000_000:
                raise ValueError("페이지가 너무 큽니다.")
            return data.decode("utf-8", errors="replace")
    finally:
        conn.close()


def reference(url):
    import re

    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9-]+)/?", url)
    if match:
        base = "https://api.github.com/users/" + match[1]
        profile = json.loads(fetch(base))
        repos = json.loads(fetch(base + "/repos?sort=pushed&per_page=12"))
        return "\n".join(
            [profile.get("bio") or "GitHub 공개 저장소"]
            + [
                f"{r['name']} ({r.get('language') or '언어 미표시'}) · {r.get('description') or ''}"
                for r in repos
            ]
        )[:6000]
    parser = Text()
    parser.feed(fetch(url))
    result = " ".join(parser.chunks)[:6000]
    if not result:
        raise ValueError("본문이 없습니다. 직접 붙여넣으세요.")
    return result


def pdf_text(data):
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted or len(reader.pages) > 40:
        raise ValueError("암호 없는 40쪽 이하 PDF를 사용하세요.")
    text = "\n".join((p.extract_text() or "")[:12000] for p in reader.pages)[
        :12000
    ].strip()
    if not text:
        raise ValueError("텍스트가 없는 PDF입니다. 직접 붙여넣으세요.")
    return text
