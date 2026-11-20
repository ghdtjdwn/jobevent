"""Named, editable references. None = all, [] = summary only, IDs = explicit selection."""

import json
import uuid

from .model import clean, identity, profile_link_url


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


class DuplicateProfileLink(ValueError):
    def __init__(self):
        super().__init__("이미 등록한 주소입니다. 기존 링크를 편집하세요.")


def profile_links(store):
    return json.loads(store.get("profileLinks", "[]"))


def update_profile_link(store, data, delete=False):
    links = profile_links(store)
    ident = data.get("id")
    row = next((link for link in links if link["id"] == ident), None)
    if (delete or ident) and not row:
        raise ValueError("공통 프로필 링크를 찾을 수 없습니다.")
    if delete:
        links.remove(row)
    else:
        url = profile_link_url(data.get("url"))
        body = clean(data.get("text"), 6000, True)
        marker = identity(url)
        if any(link is not row and identity(link["url"]) == marker for link in links):
            raise DuplicateProfileLink()
        if row is None:
            if len(links) >= 5:
                raise ValueError("공통 프로필 링크는 최대 5개입니다.")
            row = {"id": uuid.uuid4().hex}
            links.append(row)
        row.update(url=url, text=body)
    store.set("profileLinks", json.dumps(links, ensure_ascii=False))


def context(store, room):
    ids = room.get("referenceIds")
    chunks = [store.get("profile")]
    if room.get("includeProfileLinks", True):
        chunks.extend(link["text"] for link in profile_links(store))
    chunks.extend(
        doc["title"] + "\n" + doc["text"]
        for doc in references(store)
        if ids is None or doc["id"] in ids
    )
    text = "\n\n".join(c for c in chunks if c)
    if len(text) > 60000:
        raise ValueError(
            "방에서 사용하는 프로필·공통 링크 본문·참고 자료의 합계는 60,000자까지입니다. 포함할 내용을 줄여주세요."
        )
    return text
