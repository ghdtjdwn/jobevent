import json

import pytest

from jobevent.pipeline import Failure, check_channel, deliver, identity


def test_discovery_sees_only_public_query_and_ranking_has_no_tools(
    service, configured, settings, transport
):
    result = service.change("/api/preview", {"id": configured["id"]})
    assert result["items"][0]["url"] == transport.urls[0]
    discovery, ranking = transport.calls
    public = json.loads(discovery[1]["input"])
    assert configured["query"] in public.values()
    assert all(
        private not in discovery[1]["input"]
        for private in [settings["profile"], configured["preferences"]]
    )
    assert json.loads(ranking[1]["input"])["profile"] == settings["profile"]
    assert json.loads(ranking[1]["input"])["tone"] == configured["tone"]
    assert "tools" not in ranking[1]
    assert all(body.get("store") is False for _, body, _ in transport.calls)


def test_preview_does_not_consume_and_success_persists_per_room(
    service, configured, room_data, transport
):
    target = {"id": configured["id"]}
    assert len(service.change("/api/preview", target)["items"]) == 1
    assert len(service.change("/api/send", target)["items"]) == 1
    assert not service.change("/api/send", target)["items"]
    service.change("/api/room", {**room_data, "name": "다른 알림방"})
    other = service.state()["rooms"][-1]
    assert len(service.change("/api/send", {"id": other["id"]})["items"]) == 1
    webhook_calls = [call for call in transport.calls if call[2] is None]
    assert len(webhook_calls) == 2
    url, body, _ = webhook_calls[0]
    assert url.endswith("?wait=true")
    assert body["allowed_mentions"] == {"parse": []}
    assert transport.urls[0] in body["content"]


def test_failed_webhook_is_not_marked_delivered(service, configured, transport):
    transport.fail_hook = True
    with pytest.raises(Failure):
        service.change("/api/send", {"id": configured["id"]})
    assert "실패" in service.state()["history"][0]["message"]
    transport.fail_hook = False
    assert service.change("/api/send", {"id": configured["id"]})["items"]


def test_partial_batch_retry_sends_only_unconfirmed_item(
    service, configured, transport, monkeypatch
):
    transport.urls.append("https://opportunities.example/contest/2")
    transport.items.append({**transport.items[0], "index": 1})
    from jobevent import pipeline

    delivered = []

    def post(url, body, key=None):
        if key is None:
            delivered.append(body["content"])
            if len(delivered) == 2:
                raise Failure("일시 실패")
        return transport(url, body, key)

    monkeypatch.setattr(pipeline, "post", post)
    with pytest.raises(Failure):
        service.change("/api/send", {"id": configured["id"]})
    retry = service.change("/api/send", {"id": configured["id"]})["items"]
    assert [x["url"] for x in retry] == [transport.urls[1]]
    assert len(delivered) == 3


def test_failed_search_is_not_reported_as_zero_results(service, configured, transport):
    transport.search_status = "failed"
    with pytest.raises(Failure):
        service.change("/api/send", {"id": configured["id"]})
    assert len(transport.calls) == 1
    assert "0건" not in service.state()["history"][0]["message"]


def test_uncited_report_never_sends(service, configured, transport):
    transport.urls.clear()
    assert service.change("/api/send", {"id": configured["id"]})["items"] == []
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"index": -1},
        {"index": True},
        {"index": 99},
        {"deadline": "unknown"},
        {"title": ""},
    ],
)
def test_malformed_recommendation_never_sends(service, configured, transport, change):
    transport.items[0].update(change)
    with pytest.raises(Failure):
        service.change("/api/send", {"id": configured["id"]})
    assert all(key is not None for _, _, key in transport.calls)


def test_expired_recommendations_are_skipped(service, configured, transport):
    transport.items[0]["deadline"] = "2000-01-01"
    assert not service.change("/api/send", {"id": configured["id"]})["items"]


def test_long_recommendation_text_is_marked_when_clipped(
    service, configured, transport
):
    transport.items[0]["check"] = "가" * 200
    item = service.change("/api/preview", {"id": configured["id"]})["items"][0]
    assert len(item["check"]) == 140 and item["check"].endswith("…")
    assert not item["title"].endswith("…")


def test_identity_ignores_tracking_not_distinct_application_ids():
    base = "https://example.org/notice?id=12"
    assert identity(base) == identity(
        "https://EXAMPLE.org/notice/?utm_source=somewhere&id=12#top"
    )
    assert identity(base) != identity(base + "3")


def test_slack_structured_text_and_source_link(transport):
    item = {
        "title": "제목",
        "reason": "사용자 지정 말투",
        "deadline": None,
        "url": "https://example.org/a?k=1&x=2",
    }
    deliver("https://hooks.slack.com/services/test/test/test", item)
    _, body, key = transport.calls[0]
    assert key is None
    assert body["blocks"][0]["text"]["type"] == "plain_text"
    assert "&amp;" in body["blocks"][1]["text"]["text"]


def test_contacts_never_reach_ranking_or_the_channel(
    service, configured, settings, transport
):
    service.change(
        "/api/profile",
        {
            "profile": "백엔드 지망 · me@example.com · 010-1234-5678 · https://me.example"
        },
    )
    transport.urls.append("https://opportunities.example/contest/2")
    transport.items = [
        {**transport.items[0], "reason": "me@example.com 으로 연락하세요"},
        {**transport.items[0], "index": 1, "check": "마감 2026-12-31 확인"},
    ]
    items = service.change("/api/send", {"id": configured["id"]})["items"]
    assert [i["url"] for i in items] == [transport.urls[1]]
    ranking = json.loads(transport.calls[1][1]["input"])["profile"]
    assert all(s not in ranking for s in ("me@example.com", "010-1234", "me.example"))
    assert "백엔드 지망" in ranking


@pytest.mark.parametrize(
    "hook",
    [
        "https://hooks.slack.com/services/test/test/test",
        "https://discord.com/api/webhooks/1/test",
    ],
)
def test_opportunity_alert_is_labeled_ai_but_channel_check_is_not(hook, transport):
    item = {
        "title": "제목",
        "reason": "이유",
        "deadline": None,
        "url": "https://a.org/1",
    }
    deliver(hook, item)
    check_channel(hook)
    alert, check = (body for _, body, _ in transport.calls)
    shown = alert.get("content") or alert["blocks"][0]["text"]["text"]
    assert shown.startswith("[AI 추천] 제목\n")
    assert check.get("content", check.get("text")) == (
        "Jobevent 연결 확인 · 이 채널이 알림을 받을 준비가 되었습니다."
    )
