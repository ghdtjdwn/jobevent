"""Optional company board sources. No AI search, auth or application submission."""

import json

from .imports import fetch
from .pipeline import Failure, public_url


def board(room):
    kind, slug = room["source"], room["board"]
    try:
        if kind == "greenhouse":
            rows = json.loads(
                fetch(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
            )["jobs"]
            rows = sorted(rows, key=lambda x: x.get("updated_at", ""), reverse=True)
            entries = [
                (r["absolute_url"], r["title"], r.get("location", {}).get("name", ""))
                for r in rows
            ]
        else:
            host = "api.eu.lever.co" if kind == "lever-eu" else "api.lever.co"
            rows = json.loads(
                fetch(f"https://{host}/v0/postings/{slug}?mode=json&limit=50")
            )
            entries = [
                (
                    r["hostedUrl"],
                    r["text"],
                    str(r.get("categories", {}))
                    + " "
                    + r.get("descriptionPlain", "")[:500],
                )
                for r in rows
            ]
        entries = [e for e in entries if public_url(e[0])][:50]
        return json.dumps(
            [
                {"index": i, "title": t, "details": d[:550]}
                for i, (_, t, d) in enumerate(entries)
            ],
            ensure_ascii=False,
        ), [e[0] for e in entries]
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise Failure(
            "회사 채용 보드를 읽지 못했습니다. 공개 보드 식별자와 리전을 확인하세요."
        ) from exc
