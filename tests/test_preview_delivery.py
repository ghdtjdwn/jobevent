import json
import time

import pytest

from jobevent.pipeline import Failure


def preview(service, room):
    return service.change("/api/preview", {"id": room["id"]})


def test_preview_is_server_owned_and_no_new_ai_calls(service, configured, transport):
    saved = preview(service, configured)
    transport.calls.clear()
    sent = service.change(
        "/api/send-preview",
        {
            "id": configured["id"],
            "token": saved["previewToken"],
            "items": [{"title": "무시할 입력"}],
        },
    )
    assert sent["items"] == saved["items"]
    assert len(transport.calls) == 1 and transport.calls[0][2] is None
    with pytest.raises(Failure):
        service.change(
            "/api/send-preview",
            {"id": configured["id"], "token": saved["previewToken"]},
        )


@pytest.mark.parametrize(
    "mutation", ["edit", "forget", "other-room", "expired", "replaced", "profile"]
)
def test_stale_preview_never_sends(
    service, configured, room_data, settings, transport, mutation
):
    r = configured
    token = preview(service, r)["previewToken"]
    if mutation == "edit":
        service.change("/api/room", {**room_data, "id": r["id"]})
    if mutation == "profile":
        service.change("/api/profile", settings)
    if mutation == "forget":
        service.change("/api/forget", {})
    if mutation == "expired":
        k = "preview:" + r["id"]
        d = json.loads(service.store.get(k))
        d["until"] = time.time() - 1
        service.store.set(k, json.dumps(d))
    if mutation == "other-room":
        service.change("/api/room", room_data)
        r = service.store.rooms()[-1]
    if mutation == "replaced":
        preview(service, r)
    transport.calls.clear()
    with pytest.raises(Failure):
        service.change("/api/send-preview", {"id": r["id"], "token": token})
    assert not transport.calls


def test_preview_skips_already_sent_items(service, configured, transport):
    data = preview(service, configured)
    service.change("/api/send", {"id": configured["id"]})
    transport.calls.clear()
    assert service.change(
        "/api/send-preview", {"id": configured["id"], "token": data["previewToken"]}
    ) == {"items": []}
    assert not transport.calls


@pytest.mark.parametrize(
    "hook",
    [
        "https://hooks.slack.com/services/test/test/test",
        "https://discord.com/api/webhooks/1/test",
    ],
)
def test_channel_check_without_profile_or_key(service, room_data, transport, hook):
    service.change("/api/room", {**room_data, "hook": hook})
    r = service.store.rooms()[0]
    service.change(
        "/api/channel-test", {"id": r["id"], "text": "메시지에 들어가면 안 됨"}
    )
    assert len(transport.calls) == 1
    _, payload, key = transport.calls[0]
    assert key is None
    assert "연결 확인" in str(payload) and "들어가면" not in str(payload)
    assert r["preferences"] not in str(payload)
