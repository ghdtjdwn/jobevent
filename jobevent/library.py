"""Named, editable references. None = all, [] = summary only, IDs = explicit selection."""

import json
import uuid

from .model import clean


def references(store):
    return json.loads(store.get("references", "[]"))


def update(store, data, delete=False):
    docs = references(store)
    ident = data.get("id")
    row = next((doc for doc in docs if doc["id"] == ident), None)
    if (delete or ident) and not row:
        raise ValueError("자료를 찾을 수 없습니다.")
    if delete:
        docs.remove(row)
    else:
        title = clean(data.get("title"), 100, True)
        body = clean(data.get("text"), 12000, True)
        if not row:
            if len(docs) >= 30:
                raise ValueError("참고 자료는 최대 30개입니다.")
            row = {"id": uuid.uuid4().hex}
            docs.append(row)
        row.update(title=title, text=body)
    store.set("references", json.dumps(docs, ensure_ascii=False))


def context(store, room):
    ids = room.get("referenceIds")
    chunks = [store.get("profile")]
    chunks.extend(
        doc["title"] + "\n" + doc["text"]
        for doc in references(store)
        if ids is None or doc["id"] in ids
    )
    text = "\n\n".join(c for c in chunks if c)
    if len(text) > 60000:
        raise ValueError(
            "한 방의 참고 자료는 합계 60,000자까지입니다. 사용할 자료를 줄여주세요."
        )
    return text
