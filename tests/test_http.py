import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from jobevent.app import handler


@pytest.fixture
def http(service):
    with ThreadingHTTPServer(("127.0.0.1", 0), handler(service)) as server:
        thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01))
        thread.start()

        def request(method, path, body=None, headers=None):
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            try:
                conn.request(method, path, body, headers or {})
                resp = conn.getresponse()
                return resp.status, resp.headers, resp.read()
            finally:
                conn.close()

        try:
            yield (
                request,
                {
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                    "X-Jobevent": "1",
                    "Content-Type": "application/json",
                },
            )
        finally:
            server.shutdown()
            thread.join(timeout=3)


def test_local_http_can_edit_and_read_profile(http, settings):
    call, headers = http
    assert call("POST", "/api/profile", json.dumps(settings), headers)[0] == 200
    status, h, body = call("GET", "/api/state")
    assert status == 200 and json.loads(body)["profile"] == settings["profile"]
    assert h["Cache-Control"] == "no-store" and settings["key"].encode() not in body


@pytest.mark.parametrize(
    "overrides",
    [
        {"Origin": "https://example.org"},
        {"Host": "example.org"},
        {"X-Jobevent": ""},
        {"Content-Type": "text/plain"},
    ],
)
def test_foreign_or_simple_posts_cannot_write_profile(
    http, service, settings, overrides
):
    call, headers = http
    assert (
        call("POST", "/api/profile", json.dumps(settings), headers | overrides)[0]
        == 403
    )
    assert not service.state()["profile"]


def test_foreign_host_cannot_read_local_profile(http):
    call, _ = http
    assert call("GET", "/api/state", headers={"Host": "unknown.example"})[0] == 403


def test_served_page_is_not_embeddable_and_does_not_load_third_party_scripts(http):
    call, _ = http
    status, headers, body = call("GET", "/")
    assert status == 200 and b"Jobevent" in body
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "default-src 'self'" in headers["Content-Security-Policy"]
