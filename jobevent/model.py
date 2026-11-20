"""Room policy: validate at the boundary, store only normalized values."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TEMPLATES = {
    "채용": "기업 신입·경력 채용",
    "인턴": "체험형·채용연계형 인턴십",
    "동아리·연합": "개발·기획·디자인 동아리와 대학생 연합 모집",
    "공모전": "아이디어·기술·콘텐츠 공모전",
    "해커톤": "팀 또는 개인 참가 해커톤",
    "교육": "부트캠프·멘토링·교육생 모집",
    "장학·펠로십": "장학금·연구 펠로십",
    "오픈소스": "오픈소스 멘티·기여 프로그램",
    "직접 정의": "",
}


def clean(value, maxlen, required=False):
    if (
        not isinstance(value, str)
        or len(value) > maxlen
        or (required and not value.strip())
    ):
        raise ValueError("필수 항목 또는 입력 길이를 확인하세요.")
    return value.strip()


def validate_room(data):
    r = {
        k: clean(
            data.get(k, ""),
            n,
            k in ("name", "template", "tone", "query", "zone", "time"),
        )
        for k, n in (
            ("name", 60),
            ("template", 30),
            ("query", 500),
            ("tone", 120),
            ("preferences", 600),
            ("zone", 80),
            ("time", 5),
        )
    }
    if r["template"] not in TEMPLATES or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", r["time"]
    ):
        raise ValueError("분류와 시간을 확인하세요.")
    try:
        ZoneInfo(r["zone"])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("유효한 IANA 시간대가 아닙니다.") from None
    days = data.get("days")
    if (
        not isinstance(days, list)
        or not days
        or any(type(x) is not int or not 0 <= x <= 6 for x in days)
    ):
        raise ValueError("실행 요일을 선택하세요.")
    r["days"] = sorted(set(days))
    r["limit"] = data.get("limit")
    if type(r["limit"]) is not int or not 1 <= r["limit"] <= 8:
        raise ValueError("알림 수는 1~8건입니다.")
    r["source"] = data.get("source", "web")
    if r["source"] not in ("web", "greenhouse", "lever", "lever-eu"):
        raise ValueError("지원하지 않는 소스입니다.")
    r["board"] = clean(data.get("board", ""), 100)
    if r["source"] != "web" and not re.fullmatch(r"[A-Za-z0-9_-]+", r["board"]):
        raise ValueError("회사 보드 주소에서 식별자만 입력하세요.")
    r["enabled"] = data.get("enabled") is True
    return r


def next_due(room, now):
    zone = ZoneInfo(room["zone"])
    local = datetime.fromtimestamp(now, zone)
    hour, minute = map(int, room["time"].split(":"))
    for delta in range(8):
        day = local.date() + timedelta(days=delta)
        when = datetime(
            day.year, day.month, day.day, hour, minute, tzinfo=zone
        ).timestamp()
        if day.weekday() in room["days"] and when > now:
            return when
    raise ValueError("다음 실행 시간을 계산할 수 없습니다.")


def channel(url):
    for kind, pattern in (
        ("Discord", r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+"),
        (
            "Slack",
            r"https://hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+",
        ),
    ):
        if re.fullmatch(pattern, url):
            return kind
    raise ValueError("Discord 또는 Slack 공식 수신 웹훅 주소를 입력하세요.")
