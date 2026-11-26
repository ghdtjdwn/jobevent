"""Real browser regression. Only disposable local data; never call paid APIs."""

import argparse
import re
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from playwright.sync_api import expect, sync_playwright

from jobevent.app import Service, handler
from jobevent.store import Store


class MemoryVault(dict):
    """The check must never touch the OS credential store."""

    def set(self, key, value):
        if value:
            self[key] = value
        else:
            self.pop(key, None)


def check(base, shots):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1280, "height": 860}, locale="ko-KR")
        page.set_default_timeout(6000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())
        page.goto(base)
        expect(page.locator("#rooms")).to_be_visible()

        def nav(name):
            page.locator(f'nav a[href="#{name}"]').click()

        nav("profile")
        expect(
            page.get_by_role("heading", name="프로필 관리", exact=True)
        ).to_be_visible()
        expect(page.locator("#legacyProfile")).to_be_hidden()
        assert page.locator('nav a[href="#library"]').count() == 0
        page.get_by_role("link", name="AI 연결", exact=True).click()
        page.locator("[name=provider]").select_option("google")
        expect(page.locator("#keyLink")).to_have_attribute(
            "href", "https://aistudio.google.com/apikey"
        )
        assert not page.locator("[name=model]").count()
        page.locator("#settings .primary").click()
        expect(page.locator("#status")).to_contain_text("저장")
        page.get_by_role("link", name="내 공개 링크", exact=True).click()
        page.locator("#newLink").click()
        link_form = page.locator("#profileLinkForm")
        url = "https://github.com/workspace-example"
        link_form.locator("[name=url]").fill(url)
        link_form.locator("[name=text]").fill("공개 프로젝트 활동")
        link_form.get_by_role("button", name="링크 저장").click()
        expect(page.locator("#profileLinkList")).to_contain_text(url)
        page.locator("#newLink").click()
        link_form.locator("[name=url]").fill(url + "/")
        link_form.locator("[name=text]").fill("편집 중")
        link_form.get_by_role("button", name="링크 저장").click()
        expect(page.locator("#status")).to_contain_text("이미 등록한 주소")
        expect(link_form.locator("[name=text]")).to_have_value("편집 중")
        page.locator("#cancelLink").click()
        # Old bookmarks go directly to documents within the single profile page.
        page.goto(base + "/#library")
        expect(page).to_have_url(re.compile(r"#profile/docs$"))
        page.locator("#newRef").click()
        assert not page.locator("#refForm input[type=url]").count()
        page.locator("#file").set_input_files(
            {
                "name": "활동 이력서.txt",
                "mimeType": "text/plain",
                "buffer": "활동 내역".encode(),
            }
        )
        expect(page.locator("#refForm [name=title]")).to_have_value("활동 이력서")
        page.locator("#refForm .primary").click()
        expect(page.locator("#refs")).to_contain_text("활동 이력서")
        page.locator("#newRef").click()
        page.locator("#refForm [name=title]").fill("기술 포트폴리오")
        page.locator("#refForm [name=text]").fill("공개 데이터 시각화 프로젝트")
        page.locator("#refForm .primary").click()
        expect(page.locator("#refs")).to_contain_text("기술 포트폴리오")
        expect(page.locator("#profileLinkList article")).to_have_count(1)
        nav("rooms")
        page.locator('a[href="#new"]').first.click()
        page.locator("#room [name=name]").fill("주말 해커톤")
        page.locator("#room [name=template]").select_option("해커톤")
        page.locator("#room [name=refMode]").select_option("selected")
        page.get_by_label("기술 포트폴리오", exact=True).check()
        expect(page.get_by_label("내 공개 링크도 참고")).to_be_checked()
        page.get_by_label("내 공개 링크도 참고").uncheck()
        page.locator("#room [name=hook]").fill(
            "https://discord.com/api/webhooks/123/fixture"
        )
        page.locator("#room .primary").click()
        expect(page.locator("#cards")).to_contain_text("주말 해커톤")
        page.reload()
        expect(page.locator("#cards")).to_contain_text("주말 해커톤")
        if shots:
            shots.mkdir(parents=True, exist_ok=True)
            page.emulate_media(reduced_motion="reduce")
            page.screenshot(path=shots / "studio.png", animations="disabled")
        page.locator("#cards details summary").click()
        page.get_by_role("button", name="새 방으로 복제").click()
        assert not page.locator("#room [name=hook]").input_value()
        assert page.get_by_label("기술 포트폴리오", exact=True).is_checked()
        expect(page.get_by_label("내 공개 링크도 참고")).not_to_be_checked()
        page.set_viewport_size({"width": 390, "height": 844})
        for panel in ("rooms", "profile", "history"):
            nav(panel)
            expect(page.locator("#" + panel)).to_be_visible()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), panel
            if shots and panel == "profile":
                page.screenshot(
                    path=shots / "profile-mobile.png", animations="disabled"
                )
            if shots and panel == "rooms":
                page.screenshot(path=shots / "mobile.png")
        nav("profile")
        page.locator("#profileLinkList").get_by_role("button", name="편집").click()
        link_form.locator("[name=text]").fill("변경한 공통 본문")
        link_form.get_by_role("button", name="링크 저장").click()
        expect(page.locator("#profileLinkList")).to_contain_text("변경한 공통 본문")
        page.locator("#refs article").filter(has_text="기술 포트폴리오").get_by_role(
            "button", name="삭제"
        ).click()
        expect(page.locator("#refs")).not_to_contain_text("기술 포트폴리오")
        expect(page.locator("#profileLinkList")).to_contain_text(url)
        page.locator("#profileLinkList").get_by_role("button", name="삭제").click()
        expect(page.locator("#profileLinkList article")).to_have_count(0)
        expect(page.locator("#refs")).to_contain_text("활동 이력서")
        assert not errors, errors
        browser.close()
        print(
            "실제 브라우저: 프로필 통합·파일/링크 독립 관리·중복 차단·방 저장/복제·모바일 3화면 통과"
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--screenshots", type=Path)
    args = p.parse_args()
    with TemporaryDirectory() as data:
        service = Service(Store(data), MemoryVault())
        with ThreadingHTTPServer(("127.0.0.1", 0), handler(service)) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                check(f"http://127.0.0.1:{server.server_port}", args.screenshots)
            finally:
                server.shutdown()
                thread.join()


if __name__ == "__main__":
    main()
