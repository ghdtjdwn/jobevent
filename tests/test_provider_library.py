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


def test_shared_profile_links_and_room_opt_out(
    service, configured, room_data, transport
):
    url = "https://github.com/Example"
    shared = {"url": url, "text": "공통 경력 표식"}
    service.change("/api/reference-save", {"title": "지원서", "text": "개별 표식"})
    doc = service.state()["references"][0]
    service.change(
        "/api/room",
        {**room_data, "includeProfileLinks": False, "referenceIds": [doc["id"]]},
    )
    separate = service.store.rooms()[-1]
    for room in (configured, separate):
        service.store.set("preview:" + room["id"], "old")
    service.change("/api/profile-link-save", shared)
    row = service.state()["profileLinks"][0]
    assert row["url"] == url.lower()
    assert not service.store.get("preview:" + configured["id"])
    assert service.store.get("preview:" + separate["id"]) == "old"
    assert shared["text"] in context(service.store, {"referenceIds": []})  # legacy
    assert shared["text"] not in context(service.store, separate)
    assert "개별 표식" in context(service.store, separate)
    for expected, room in ((True, configured), (False, separate)):
        transport.calls.clear()
        service.change("/api/preview", {"id": room["id"]})
        search, rank = [call[1]["input"] for call in transport.calls]
        assert shared["text"] not in search
        assert (shared["text"] in rank) is expected
        assert url.lower() not in rank  # only the reviewed content is necessary
    service.change("/api/room", {**room_data, "id": separate["id"]})
    assert service.room(separate["id"])["includeProfileLinks"] is False
    service.change("/api/profile-link-save", {**row, "text": "새 내용"})
    assert service.state()["profileLinks"] == [{**row, "text": "새 내용"}]
    service.change("/api/profile-link-delete", {"id": row["id"]})
    assert service.state()["profileLinks"] == []
    assert service.state()["references"] == [doc]
    service.change("/api/profile-link-save", shared)
    service.change("/api/forget", {})
    assert service.state()["profileLinks"] == []


def test_link_constraints_and_duplicate_identity(service):
    data = {
        "url": "https://ME.vercel.app:443/work/?b=one&a=two#page",
        "text": "portfolio",
    }

    def save(d):
        return service.change("/api/profile-link-save", d)

    save(data)
    original = service.state()["profileLinks"]
    for extra in [
        {"url": "https://me.vercel.app/work?a=two&utm_source=test&b=one"},
        {"url": "https://other.example"},
        {"url": "https://vercel.app"},
        {"url": "https://-name.vercel.app"},
        {"url": "https://team..vercel.app"},
        {"url": "https://" + "a" * 64 + ".github.io"},
        {"url": "https://github.com/user/repo"},
        {"url": "https://user@me.vercel.app"},
        {"url": "https://me.vercel.app:8443/"},
        {"url": "https://me.vercel.app.attacker.example"},
        {"text": "x" * 6001},
        {"text": ""},
        {"id": "missing"},
    ]:
        with pytest.raises(ValueError):
            save({**data, **extra})
    assert service.state()["profileLinks"] == original
    for n in range(4):
        save({**data, "url": f"https://github.com/person-{n}"})
    with pytest.raises(ValueError, match="최대 5개"):
        save({**data, "url": "https://github.com/another"})
    with pytest.raises(ValueError, match="이미 등록"):
        save({**original[0], "url": "https://GITHUB.COM/PERSON-1/?tab=repositories"})


def test_link_content_counts_toward_context_limit(service):
    for n in range(5):
        service.change("/api/reference-save", {"title": str(n), "text": "a" * 11000})
    service.change(
        "/api/profile-link-save",
        {"url": "https://example.github.io", "text": "b" * 6000},
    )
    with pytest.raises(ValueError, match="60,000"):
        context(service.store, {})
    assert len(context(service.store, {"includeProfileLinks": False})) < 60000


def test_profile_and_ai_settings_can_be_saved_independently(service):
    service.change("/api/profile", {"profile": "원래 소개"})
    service.change("/api/profile", {"provider": "google", "key": "test-google"})
    assert service.state()["profile"] == "원래 소개"
    service.change("/api/profile", {"profile": "새 소개"})
    assert service.state()["provider"] == "google"
    assert service.vault.get("api:google") == "test-google"
    service.change("/api/profile", {"profile": ""})
    assert service.state()["profile"] == ""
    assert service.state()["hasKey"]
