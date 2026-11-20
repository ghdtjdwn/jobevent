"""One credential, one provider. Do not substitute a different vendor on failure."""

import json

MODELS = {
    "openai": "gpt-6.1-sol",
    "google": "gemini-4-hydrogen",
    "anthropic": "claude-sonnet-5-5",
}


def normalized(blocks, searched):
    content = []
    for text, urls in blocks:
        content.append(
            {
                "type": "output_text",
                "text": text,
                "annotations": [{"type": "url_citation", "url": url} for url in urls],
            }
        )
    output = [{"type": "message", "content": content}]
    if searched:
        output.insert(0, {"type": "web_search_call", "status": "completed"})
    return output


def request_alternative(post, key, model, instructions, payload, options):
    from .pipeline import Failure

    query = json.dumps(payload, ensure_ascii=False)
    search = bool(options.get("tools"))
    if not search:
        instructions += " Return only the JSON object without Markdown fences."
    limit = options["max_output_tokens"]
    if model == MODELS["anthropic"]:
        body = {
            "model": model,
            "system": instructions,
            "max_tokens": limit,
            "messages": [{"role": "user", "content": query}],
        }
        if search:
            body["tools"] = [
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}
            ]
        data = json.loads(
            post(
                "https://api.anthropic.com/v1/messages",
                body,
                auth_headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            )
        )
        if data.get("stop_reason") != "end_turn":
            raise Failure("Claude 응답이 완료되지 않았습니다.")
        parts = data["content"]
        results = [p for p in parts if p["type"] == "web_search_tool_result"]
        if any(not isinstance(p.get("content"), list) for p in results):
            raise Failure("Claude 웹 검색 실패 · 검색 권한과 사용 한도를 확인하세요.")
        return normalized(
            [
                (
                    p["text"],
                    [
                        a["url"]
                        for a in p.get("citations", [])
                        if a.get("type") == "web_search_result_location"
                    ],
                )
                for p in parts
                if p["type"] == "text"
            ],
            bool(results),
        )
    if model != MODELS["google"]:
        raise Failure("지원하지 않는 AI 제공 회사입니다.")
    body = {
        "model": model,
        "system_instruction": instructions,
        "input": query,
        "store": False,
        "generation_config": {"max_output_tokens": limit},
    }
    if search:
        body["tools"] = [{"type": "google_search"}]
    data = json.loads(
        post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            body,
            auth_headers={"x-goog-api-key": key, "Api-Revision": "2026-05-20"},
        )
    )
    if data.get("status") != "completed":
        raise Failure("Gemini 응답이 완료되지 않았습니다.")
    steps = data["steps"]
    return normalized(
        [
            (
                p["text"],
                [
                    a["url"]
                    for a in p.get("annotations", [])
                    if a.get("type") == "url_citation"
                ],
            )
            for step in steps
            if step["type"] == "model_output"
            for p in step["content"]
            if p["type"] == "text"
        ],
        any(s["type"] == "google_search_result" for s in steps),
    )
