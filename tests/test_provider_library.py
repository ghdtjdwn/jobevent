import json

import pytest

from jobevent import pipeline
from jobevent.library import context
from jobevent.providers import MODELS


def test_reference_selection_is_room_local(service, room_data):
    for name in ("이력서", "포트폴리오"):
        service.change("/api/reference-save", {"title": name, "text": name + " 내용"})
    docs = service.state()["references"]
    for ids, expect in [
        (None, ["이력서", "포트폴리오"]),
        ([], []),
        ([docs[0]["id"]], ["이력서"]),
    ]:
        service.change("/api/room", {**room_data, "referenceIds": ids})
        text = context(service.store, service.store.rooms()[-1])
        assert [d["title"] for d in docs if d["title"] in text] == expect
    service.change("/api/reference-save", {**docs[0], "text": "새 내용"})
    assert "새 내용" in context(service.store, service.store.rooms()[-1])
    service.change("/api/reference-delete", {"id": docs[0]["id"]})
    assert service.store.rooms()[-1]["referenceIds"] == []
    assert "이력서" not in str(service.state()["references"])
    with pytest.raises(ValueError):
        service.change("/api/room", {**room_data, "referenceIds": [docs[0]["id"]]})


def test_switch_requires_matching_key_and_no_model_override(
    service, settings, room_data, transport
):
    service.change("/api/profile", settings)
    with pytest.raises(ValueError):
        service.change("/api/profile", {"profile": "A", "provider": "google"})
    assert service.state()["provider"] == "openai"
    service.change("/api/room", room_data)
    target = {"id": service.store.rooms()[0]["id"]}
    service.change("/api/preview", target)
    assert transport.calls[0][1]["model"] == MODELS["openai"]
    service.change(
        "/api/profile", {"profile": "A", "provider": "google", "key": "unit-google"}
    )
    assert (
        not service.vault.get("api")
        and service.vault.get("api:google") == "unit-google"
    )
    service.change("/api/forget", {})
    assert not service.vault.get("api:google")


@pytest.mark.parametrize("provider", ["google", "anthropic"])
def test_complete_provider_flow_and_privacy(service, room_data, provider, monkeypatch):
    service.change(
        "/api/profile", {"profile": "", "provider": provider, "key": "chosen-key"}
    )
    service.change(
        "/api/reference-save", {"title": "경험", "text": "private-profile-marker"}
    )
    service.change("/api/room", {**room_data, "enabled": True})
    url = "https://example.org/one"
    ranked = json.dumps(
        {
            "items": [
                {"index": 0, "title": "공고", "reason": "조건 일치", "deadline": None}
            ]
        }
    )
    calls = []

    def post(endpoint, body, *, auth_headers):
        calls.append(endpoint)
        assert (
            body["model"] == MODELS[provider] and "chosen-key" in auth_headers.values()
        )
        search = "tools" in body
        assert (
            "private-profile-marker" in json.dumps(body, ensure_ascii=False)
        ) != search
        assert ("개인 우선순위 표식" in json.dumps(body, ensure_ascii=False)) != search
        if provider == "google":
            assert (
                endpoint.startswith("https://generativelanguage.googleapis.com/")
                and not body["store"]
            )
            response = {
                "status": "completed",
                "steps": (
                    [{"type": "google_search_result", "result": []}] if search else []
                )
                + [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": "공고" if search else ranked,
                                "annotations": [{"type": "url_citation", "url": url}]
                                if search
                                else [],
                            }
                        ],
                    }
                ],
            }
        else:
            assert endpoint == "https://api.anthropic.com/v1/messages"
            response = {
                "stop_reason": "end_turn",
                "content": (
                    [{"type": "web_search_tool_result", "content": []}]
                    if search
                    else []
                )
                + [
                    {
                        "type": "text",
                        "text": "공고" if search else ranked,
                        "citations": [
                            {"type": "web_search_result_location", "url": url}
                        ]
                        if search
                        else [],
                    }
                ],
            }
        return json.dumps(response).encode()

    monkeypatch.setattr(pipeline, "post", post)
    got = service.change("/api/preview", {"id": service.store.rooms()[0]["id"]})
    assert len(calls) == 2 and got["items"][0]["url"] == url
