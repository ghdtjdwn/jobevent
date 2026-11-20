"""Loopback-only UI and scheduler share the same room execution lock."""

import argparse
import base64
import json
import os
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from filelock import FileLock, Timeout

from . import library
from .imports import pdf_text, reference
from .model import TEMPLATE_CHECKS, TEMPLATES, channel, clean, validate_room
from .pipeline import Failure, check_channel, run, send_items
from .providers import MODELS
from .store import Store, Vault


class Service:
    def __init__(self, store, vault):
        self.store = store
        self.vault = vault
        self.lock = threading.Lock()

    def room(self, i):
        for r in self.store.rooms():
            if r["id"] == i:
                return r
        raise ValueError("알림방을 찾을 수 없습니다.")

    def execute(self, r, preview):
        try:
            items = run(self.store, self.vault, r, preview)
        except Exception as e:
            msg = (
                str(e)
                if isinstance(e, Failure)
                else "실행 실패 · 자격 증명 저장소 또는 외부 서비스 응답을 확인하세요."
            )
            self.store.log(r["id"], msg)
            raise Failure(msg) from None
        self.store.log(
            r["id"], f"{'미리보기' if preview else '발송'} · 신규 {len(items)}건"
        )
        result = {"items": items}
        if preview:
            token = uuid.uuid4().hex
            self.store.set(
                "preview:" + r["id"],
                json.dumps({"token": token, "until": time.time() + 900, "items": items})
                if items
                else "",
            )
            if items:
                result["previewToken"] = token
        return result

    def tick(self):
        if not self.lock.acquire(blocking=False):
            return
        try:
            for r in self.store.rooms():
                if r["enabled"] and r["due"] <= time.time():
                    self.store.advance(r)
                    try:
                        self.execute(r, False)
                    except Failure:
                        pass
        finally:
            self.lock.release()

    def state(self):
        return dict(
            profile=self.store.get("profile"),
            provider=self.store.get("provider", "openai"),
            references=library.references(self.store),
            profileLinks=library.profile_links(self.store),
            hasKey=self.store.get("configured") == "yes",
            rooms=self.store.rooms(),
            templates=TEMPLATES,
            templateChecks=TEMPLATE_CHECKS,
            history=self.store.history(),
        )

    def change(self, path, d):
        if not isinstance(d, dict):
            raise ValueError("입력 형식 오류")
        if path == "/api/reference":
            try:
                return {"text": reference(clean(d.get("url"), 1000, True))}
            except (OSError, UnicodeError, KeyError):
                raise ValueError("공개 페이지를 읽을 수 없습니다.") from None
        if path == "/api/pdf":
            try:
                return {"text": pdf_text(base64.b64decode(d["data"], validate=True))}
            except Exception:
                raise ValueError(
                    "PDF를 읽지 못했습니다. 텍스트 PDF(40쪽 이하) 또는 직접 입력을 사용하세요."
                ) from None
        if not self.lock.acquire(blocking=False):
            raise Failure("다른 작업이 진행 중입니다. 잠시 후 다시 시도하세요.")
        try:
            if path == "/api/profile":
                profile = clean(d["profile"], 20000) if "profile" in d else None
                old_provider = self.store.get("provider", "openai")
                provider = d.get("provider", old_provider)
                if not isinstance(provider, str) or provider not in MODELS:
                    raise ValueError("AI 제공 회사를 선택하세요.")
                key = clean(d.get("key", ""), 500)
                if (
                    old_provider != provider
                    and self.store.get("configured")
                    and not key
                ):
                    raise ValueError(
                        "회사를 변경하려면 해당 회사의 새 API 키를 입력하세요."
                    )
                if key:
                    self.vault.set(
                        "api" if provider == "openai" else "api:" + provider, key
                    )
                    self.store.set("configured", "yes")
                self.store.set("provider", provider)
                if old_provider != provider and self.store.get("configured"):
                    self.vault.set(
                        "api" if old_provider == "openai" else "api:" + old_provider, ""
                    )
                for room in self.store.rooms():
                    self.store.set("preview:" + room["id"], "")
                if profile is not None:
                    self.store.set("profile", profile)
            elif path in ("/api/reference-save", "/api/reference-delete"):
                delete = path.endswith("-delete")
                library.update(self.store, d, delete)
                for room in self.store.rooms():
                    self.store.set("preview:" + room["id"], "")
                    ids = room.get("referenceIds")
                    if delete and ids and d["id"] in ids:
                        room["referenceIds"] = [i for i in ids if i != d["id"]]
                        self.store.save(room["id"], validate_room(room), room["kind"])

            elif path in ("/api/profile-link-save", "/api/profile-link-delete"):
                library.update_profile_link(self.store, d, path.endswith("-delete"))
                for room in self.store.rooms():
                    if room.get("includeProfileLinks", True):
                        self.store.set("preview:" + room["id"], "")
            elif path == "/api/forget":
                provider = self.store.get("provider", "openai")
                self.vault.set("api" if provider == "openai" else "api:" + provider, "")
                self.store.set("references", "[]")
                self.store.set("profileLinks", "[]")
                self.store.set("configured", "")
                self.store.set("profile", "")
                for r in self.store.rooms():
                    self.store.set("preview:" + r["id"], "")
                    r["referenceIds"] = None
                    r["enabled"] = False
                    self.store.save(r["id"], validate_room(r), r["kind"])
            elif path == "/api/room":
                i = d.get("id") or uuid.uuid4().hex
                old = self.room(i) if d.get("id") else None
                if old and "includeProfileLinks" not in d:
                    d = {
                        **d,
                        "includeProfileLinks": old.get("includeProfileLinks", True),
                    }
                r = validate_room(d)
                hook = clean(d.get("hook", ""), 600)
                kind = channel(hook) if hook else old and old["kind"]
                if not kind:
                    raise ValueError("웹훅이 필요합니다.")
                if set(r["referenceIds"] or []) - {
                    doc["id"] for doc in library.references(self.store)
                }:
                    raise ValueError("존재하지 않는 참고 자료입니다.")
                if r["enabled"] and not self.store.get("configured"):
                    raise ValueError(
                        "예약을 켜려면 프로필 관리 → AI 연결에서 키를 등록하세요."
                    )
                if r["enabled"] and not library.context(self.store, r):
                    raise ValueError(
                        "이 방에서 참고할 자료를 고르거나 등록한 공개 링크를 포함하세요."
                    )
                if hook:
                    self.vault.set(i, hook)
                self.store.set("preview:" + i, "")
                self.store.save(i, r, kind)
            elif path in (
                "/api/preview",
                "/api/send",
                "/api/delete",
                "/api/channel-test",
                "/api/send-preview",
            ):
                r = self.room(d.get("id"))
                if path == "/api/delete":
                    self.vault.set(r["id"], "")
                    self.store.set("preview:" + r["id"], "")
                    self.store.delete(r["id"])
                elif path == "/api/channel-test":
                    try:
                        check_channel(self.vault.get(r["id"]))
                    except Failure as e:
                        self.store.log(r["id"], str(e))
                        raise
                    self.store.log(r["id"], "연결 확인 메시지 전송 성공")
                elif path == "/api/send-preview":
                    snapshot = json.loads(self.store.get("preview:" + r["id"]) or "{}")
                    if (
                        not snapshot
                        or snapshot["token"] != d.get("token")
                        or snapshot["until"] <= time.time()
                    ):
                        raise Failure(
                            "미리보기가 만료되었거나 설정이 변경됐습니다. 다시 미리보기 하세요."
                        )
                    try:
                        sent = send_items(self.store, self.vault, r, snapshot["items"])
                    except Failure as e:
                        self.store.log(r["id"], str(e))
                        raise
                    self.store.set("preview:" + r["id"], "")
                    self.store.log(r["id"], f"확인한 추천 발송 · {len(sent)}건")
                    return {"items": sent}
                else:
                    return self.execute(r, path == "/api/preview")
            else:
                raise ValueError("알 수 없는 작업입니다.")
            return {"ok": True}
        finally:
            self.lock.release()


def handler(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body, mime="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def guard(self, write=False):
            host = f"127.0.0.1:{self.server.server_port}"
            return self.headers.get("Host") == host and (
                not write
                or (
                    self.headers.get("Origin") == f"http://{host}"
                    and self.headers.get("X-Jobevent") == "1"
                    and self.headers.get_content_type() == "application/json"
                )
            )

        def do_GET(self):
            if not self.guard():
                return self.reply(403, {})
            if self.path == "/api/state":
                return self.reply(200, service.state())
            assets = {
                "/": ("index.html", "text/html"),
                "/app.js": ("app.js", "text/javascript"),
                "/style.css": ("style.css", "text/css"),
            }
            if self.path not in assets:
                return self.reply(404, {})
            name, mime = assets[self.path]
            self.reply(
                200,
                files("jobevent.static").joinpath(name).read_bytes(),
                mime + "; charset=utf-8",
            )

        def do_POST(self):
            if not self.guard(True):
                return self.reply(403, {})
            try:
                n = int(self.headers.get("Content-Length", 0))
                if not 0 < n <= 6_000_000:
                    return self.reply(413, {})
                result = service.change(self.path, json.loads(self.rfile.read(n)))
            except (ValueError, Failure) as e:
                return self.reply(400, {"error": str(e)[:200]})
            except Exception:
                return self.reply(
                    500,
                    {
                        "error": "저장소를 열지 못했거나 내부 오류가 발생했습니다. OS 자격 증명 저장소를 확인하세요."
                    },
                )
            self.reply(200, result)

    return Handler


def main():
    p = argparse.ArgumentParser(description="Jobevent 로컬 알림 스튜디오")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    os.umask(0o077)
    store = Store(Path.home() / ".jobevent")
    service = Service(store, Vault(store.path))
    instance = FileLock(str(store.path) + ".lock", timeout=0)
    try:
        lease = instance.acquire()
    except Timeout:
        p.exit(1, "이미 이 기기에서 Jobevent가 실행 중입니다.\n")
    with (
        lease,
        ThreadingHTTPServer(("127.0.0.1", args.port), handler(service)) as server,
    ):
        url = f"http://127.0.0.1:{server.server_port}"
        stop = threading.Event()

        def worker():
            while not stop.wait(5):
                service.tick()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        print(
            f"Jobevent: {url} · 예약을 사용하려면 이 프로세스를 유지하세요.", flush=True
        )
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()


if __name__ == "__main__":
    main()
