import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jobevent.model import channel, next_due, validate_room


@pytest.mark.parametrize(
    "field,value",
    [
        ("days", []),
        ("days", [True]),
        ("days", [7]),
        ("time", "24:00"),
        ("limit", 0),
        ("limit", 9),
        ("zone", "not/a-timezone"),
        ("template", "unknown"),
    ],
)
def test_invalid_room_not_saved(service, room_data, field, value):
    with pytest.raises(ValueError):
        service.change("/api/room", {**room_data, field: value})
    assert not service.store.rooms()


def test_edit_preserves_webhook_and_delete_removes_history_and_key(
    service, configured, room_data
):
    i = configured["id"]
    service.store.log(i, "이력")
    service.change("/api/room", {**room_data, "id": i, "name": "수정됨", "hook": ""})
    assert service.state()["rooms"][0]["name"] == "수정됨"
    assert service.vault.get(i) == room_data["hook"]
    service.change("/api/delete", {"id": i})
    assert service.vault.get(i) is None
    assert not service.state()["rooms"] and not service.state()["history"]


def test_secret_values_not_in_database_or_client_state(
    service, configured, settings, room_data
):
    payload = json.dumps(service.state()).encode() + service.store.path.read_bytes()
    assert room_data["hook"].encode() not in payload
    assert settings["key"].encode() not in payload


def test_schedule_requires_profile_and_key(service, room_data):
    with pytest.raises(ValueError):
        service.change("/api/room", {**room_data, "enabled": True})
    assert not service.store.rooms()


def test_forget_disables_all_schedules_and_erases_profile(
    service, configured, room_data
):
    service.change("/api/room", {**room_data, "enabled": True, "id": configured["id"]})
    service.change("/api/forget", {})
    state = service.state()
    assert not state["profile"] and not state["hasKey"] and not service.vault.get("api")
    assert not state["rooms"][0]["enabled"]


def test_due_in_local_zone_skips_current_slot(room_data):
    r = validate_room(room_data)
    zone = ZoneInfo(r["zone"])
    monday = datetime(2026, 1, 5, 10, tzinfo=zone)
    assert next_due(r, monday.timestamp() - 1) == monday.timestamp()
    assert datetime.fromtimestamp(next_due(r, monday.timestamp()), zone) == datetime(
        2026, 1, 9, 10, tzinfo=zone
    )


def test_overdue_schedule_runs_once_and_advances(
    service, configured, room_data, transport, monkeypatch
):
    import time

    service.change("/api/room", {**room_data, "enabled": True, "id": configured["id"]})
    old_due = service.room(configured["id"])["due"]
    monkeypatch.setattr(time, "time", lambda: old_due + 3600)
    service.tick()
    service.tick()
    assert sum(key is None for _, _, key in transport.calls) == 1
    assert service.room(configured["id"])["due"] > old_due + 3600


@pytest.mark.parametrize(
    "url",
    [
        "https://discord.com.example/webhooks/1/test",
        "https://user@discord.com/api/webhooks/1/test",
        "http://hooks.slack.com/services/a/b/c",
        "https://hooks.slack.com/services/a/b/c?redirect=1",
    ],
)
def test_webhook_requires_canonical_provider_url(url):
    with pytest.raises(ValueError):
        channel(url)
