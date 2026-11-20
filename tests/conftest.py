import json
from urllib.parse import urlsplit

import pytest

from jobevent import pipeline
from jobevent.app import Service
from jobevent.store import Store


class MemoryVault(dict):
    """Tests must never access the user's credential store."""

    def set(self, key, value):
        if value:
            self[key] = value
        else:
            self.pop(key, None)


@pytest.fixture
def service(tmp_path):
    return Service(Store(tmp_path), MemoryVault())


@pytest.fixture
def settings():
    return {"key": "unit-test-only", "profile": "개인 기준 표식", "model": "test-model"}


@pytest.fixture
def room_data():
    return {
        "name": "테스트 방",
        "template": "공모전",
        "query": "대학생 소프트웨어 경진대회",
        "tone": "짧은 존댓말",
        "preferences": "개인 우선순위 표식",
        "days": [0, 4],
        "zone": "Asia/Seoul",
        "time": "10:00",
        "limit": 3,
        "enabled": False,
        "hook": "https://discord.com/api/webhooks/1/test",
    }


@pytest.fixture
def configured(service, settings, room_data):
    service.change("/api/profile", settings)
    service.change("/api/room", room_data)
    return service.state()["rooms"][0]


def message(text, annotations=()):
    return {
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "output_text", "text": text, "annotations": list(annotations)}
        ],
    }


class Transport:
    """Script the external boundary; exercise actual response parsing and SQLite."""

    def __init__(self):
        self.calls = []
        self.urls = ["https://opportunities.example/contest/1"]
        self.items = [
            {
                "index": 0,
                "title": "공모전",
                "reason": "기술 분야 일치",
                "deadline": None,
            }
        ]
        self.search_status = "completed"
        self.fail_hook = False

    def __call__(self, url, body, key=None):
        self.calls.append((url, body, key))
        if url == "https://api.openai.com/v1/responses":
            if "tools" in body:
                annotations = [
                    {
                        "type": "url_citation",
                        "url": u,
                        "start_index": 0,
                        "end_index": 2,
                        "title": "공고",
                    }
                    for u in self.urls
                ]
                output = [
                    {"type": "web_search_call", "status": self.search_status},
                    message("공고: 모집 중", annotations),
                ]
            else:
                output = [message(json.dumps({"items": self.items}))]
            return json.dumps({"status": "completed", "output": output}).encode()
        if self.fail_hook:
            raise pipeline.Failure("외부 서비스 연결 실패")
        return (
            b"ok" if urlsplit(url).hostname == "hooks.slack.com" else b'{"id":"12345"}'
        )


@pytest.fixture
def transport(monkeypatch):
    fake = Transport()
    monkeypatch.setattr(pipeline, "post", fake)
    return fake
