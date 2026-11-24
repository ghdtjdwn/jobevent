"""Hosted contracts use Django's real middleware/auth, files and management command."""

import json
import secrets
import uuid
from urllib.parse import urlsplit

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    import django
    from django.core.management import call_command
    from django.db import connections

    root = tmp_path_factory.mktemp("hosted")
    with pytest.MonkeyPatch.context() as env:
        for k, v in {
            "DJANGO_SETTINGS_MODULE": "jobevent.hosted.settings",
            "JOBEVENT_ORIGIN": "http://127.0.0.1:8000",
            "JOBEVENT_DEV": "1",
            "JOBEVENT_SECRET_KEY": secrets.token_urlsafe(64),
            "JOBEVENT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "JOBEVENT_DATA_DIR": str(root),
        }.items():
            env.setenv(k, v)
        django.setup()
        call_command("migrate", interactive=False, verbosity=0)
        yield root
        connections.close_all()


@pytest.fixture
def client(host):
    from django.test import Client

    return Client(
        enforce_csrf_checks=True,
        HTTP_HOST="127.0.0.1:8000",
        REMOTE_ADDR=uuid.uuid4().hex,
    )


def post(client, path, body):
    return client.post(
        path,
        json.dumps(body),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
    )


def signup(client):
    name = "account-" + uuid.uuid4().hex[:12]
    password = secrets.token_urlsafe(20)
    assert client.get("/signup").status_code == 200
    r = client.post(
        "/signup",
        {
            "username": name,
            "password1": password,
            "password2": password,
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        },
    )
    assert (r.status_code, r["Location"]) == (302, "/app")
    assert client.get("/app").status_code == 200
    return name, password


def test_account_authentication_and_csrf(client):
    assert client.get("/api/state").status_code == 401
    assert client.get("/app").status_code == 302
    assert client.post("/signup", {"username": "x"}).status_code == 403
    username, password = signup(client)
    assert client.get("/api/state").json()["username"] == username
    assert (
        client.post("/api/profile", {}, content_type="application/json").status_code
        == 403
    )
    assert client.get("/logout").status_code == 405
    assert (
        client.post(
            "/logout", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
        ).status_code
        == 302
    )
    assert client.get("/api/state").status_code == 401
    client.get("/signin")
    assert (
        client.post(
            "/signin",
            {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        ).status_code
        == 302
    )
    assert client.get("/api/state").json()["hosted"] is True


def test_hosted_separates_accounts_and_encrypts_sensitive_fields(
    client, host, settings, room_data
):
    from django.test import Client

    from jobevent.hosted.tenants import account_dir

    signup(client)
    assert post(client, "/api/profile", settings).status_code == 200
    assert post(client, "/api/room", room_data).status_code == 200
    link = {"url": "https://github.com/example-profile", "text": "비공개 검토 메모"}
    assert post(client, "/api/profile-link-save", link).status_code == 200
    state = client.get("/api/state").json()
    room = state["rooms"][0]
    assert state["profile"] == settings["profile"] and state["hasKey"]
    assert settings["key"] not in json.dumps(state)
    db = (
        account_dir(int(client.session["_auth_user_id"])) / "jobevent.sqlite3"
    ).read_bytes()
    assert state["profileLinks"][0]["text"] == link["text"]
    for value in [
        *link.values(),
        settings["key"],
        settings["profile"],
        room_data["preferences"],
        room_data["hook"],
        room_data["query"],
    ]:
        assert value.encode() not in db
    stranger = Client(
        enforce_csrf_checks=True,
        HTTP_HOST="127.0.0.1:8000",
        REMOTE_ADDR=uuid.uuid4().hex,
    )
    signup(stranger)
    other = stranger.get("/api/state").json()
    assert (other["rooms"], other["profile"], other["hasKey"]) == ([], "", False)
    assert other["profileLinks"] == []
    ident = state["profileLinks"][0]["id"]
    assert post(stranger, "/api/profile-link-delete", {"id": ident}).status_code == 400
    assert (
        post(stranger, "/api/profile-link-save", {**link, "id": ident}).status_code
        == 400
    )
    assert client.get("/api/state").json()["profileLinks"] == state["profileLinks"]
    assert post(stranger, "/api/delete", {"id": room["id"]}).status_code == 400
    assert len(client.get("/api/state").json()["rooms"]) == 1


def test_browser_closed_worker_and_shared_lock(client, room_data, settings, transport):
    from django.core.management import call_command

    from jobevent.hosted.tenants import mutex, service_for

    signup(client)
    uid = int(client.session["_auth_user_id"])
    assert post(client, "/api/profile", settings).status_code == 200
    assert post(client, "/api/room", {**room_data, "enabled": True}).status_code == 200
    service = service_for(uid)
    with service.store.db() as db:
        db.execute("UPDATE rooms SET due=0")
    with mutex(f"user-{uid}"):
        assert (
            post(
                client, "/api/send", {"id": service.store.rooms()[0]["id"]}
            ).status_code
            == 409
        )
        call_command("runworker", once=True)
        assert transport.calls == []
    client.post("/logout", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
    call_command("runworker", once=True)
    assert sum(urlsplit(u).hostname == "discord.com" for u, *_ in transport.calls) == 1
    call_command("runworker", once=True)
    assert sum(urlsplit(u).hostname == "discord.com" for u, *_ in transport.calls) == 1
    assert service.store.history()[0]["message"] == "발송 · 신규 1건"


def test_account_deletion_erases_tenant_not_another_account(client, settings):
    from django.contrib.auth import get_user_model

    from jobevent.hosted.tenants import account_dir

    username, pw = signup(client)
    uid = int(client.session["_auth_user_id"])
    post(client, "/api/profile", settings)

    def delete(p):
        return client.post(
            "/account/delete",
            {"password": p, "csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )

    assert delete("wrong").status_code == 400 and account_dir(uid).exists()
    assert delete(pw).status_code == 302
    assert (
        not account_dir(uid).exists()
        and not get_user_model().objects.filter(username=username).exists()
    )
    assert client.get("/api/state").status_code == 401


def test_hosted_errors_do_not_return_internal_exception_details(client, monkeypatch):
    from jobevent.app import Service
    from jobevent.pipeline import Failure

    signup(client)
    for error in (ValueError, Failure):

        def fail(*_):
            raise error("internal diagnostic marker")

        monkeypatch.setattr(Service, "change", fail)
        res = post(client, "/api/profile", {})
        assert res.status_code == 400
        assert "API 키" in res.json()["error"]
        assert "internal diagnostic marker" not in res.json()["error"]


def test_hosted_manual_quota_and_import_boundary(client):
    signup(client)
    for _ in range(12):
        res = post(
            client, "/api/reference", {"url": "https://portfolio.example/account"}
        )
        assert res.status_code == 400 and "GitHub" in res.json()["error"]
    assert post(client, "/api/preview", {}).status_code == 429


def test_hosted_health_host_and_signup_limit(client, monkeypatch):
    from django.test import override_settings

    monkeypatch.setenv("JOBEVENT_REVISION", "unit-release")
    assert client.get("/healthz").json() == {"status": "ok", "revision": "unit-release"}
    assert client.get("/healthz", HTTP_HOST="external.invalid").status_code == 400
    client.get("/signup")
    with override_settings(MAX_ACCOUNTS=0):
        pw = secrets.token_urlsafe(24)
        r = client.post(
            "/signup",
            {
                "username": uuid.uuid4().hex,
                "password1": pw,
                "password2": pw,
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )
        assert r.status_code == 429


def test_pdf_subprocess_extracts_without_keeping_file(tmp_path):
    import base64
    import sys
    from io import BytesIO

    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    from jobevent.hosted.pdf import extract

    if sys.platform not in ("linux", "darwin"):
        pytest.skip("호스팅 PDF는 POSIX 프로세스 제한을 사용")
    writer = PdfWriter()
    page = writer.add_blank_page(100, 100)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 0 80 Td (Test Profile) Tj ET")
    page[NameObject("/Contents")] = stream
    data = BytesIO()
    writer.write(data)
    assert extract(base64.b64encode(data.getvalue()).decode()) == "Test Profile"
    with pytest.raises(ValueError):
        extract("not a PDF")


@pytest.mark.parametrize(
    "url",
    [
        "https://demo.github.io/projects",
        "https://demo.vercel.app/home",
        "https://demo.notion.site/notes",
    ],
)
def test_hosted_public_portfolio_routes_through_limited_fetch(client, monkeypatch, url):
    from jobevent import imports

    def fetch(value):
        assert value == url
        return "<html><body><p>portfolio skills</p></body></html>"

    monkeypatch.setattr(imports, "fetch", fetch)
    signup(client)
    result = post(client, "/api/reference", {"url": url})
    assert result.status_code == 200 and result.json() == {"text": "portfolio skills"}


def test_proxy_address_requires_operator_trust(host):
    from django.test import RequestFactory, override_settings

    from jobevent.hosted.views import client_address

    req = RequestFactory().get("/", REMOTE_ADDR="10.0.0.7", HTTP_X_REAL_IP="192.0.2.1")
    with override_settings(TRUST_PROXY=False):
        assert client_address(req) == "10.0.0.7"
    with override_settings(TRUST_PROXY=True):
        assert client_address(req) == "192.0.2.1"
        req.META["HTTP_X_REAL_IP"] = "not an IP address"
        assert client_address(req) == "10.0.0.7"


def test_failed_logins_elsewhere_cannot_lock_out_the_owner(host):
    from django.test import Client

    def attempt(address, username, password):
        c = Client(HTTP_HOST="127.0.0.1:8000", REMOTE_ADDR=address)
        c.get("/signin")
        return c.post("/signin", {"username": username, "password": password})

    owner = Client(HTTP_HOST="127.0.0.1:8000", REMOTE_ADDR=uuid.uuid4().hex)
    username, password = signup(owner)
    attacker = uuid.uuid4().hex
    assert [attempt(attacker, username, "wrong").status_code for _ in range(12)] == [
        200
    ] * 12
    assert attempt(attacker, username, password).status_code == 429
    assert attempt(uuid.uuid4().hex, username, password).status_code == 302
    # Successful logins never use up the failure budget.
    home = uuid.uuid4().hex
    assert {attempt(home, username, password).status_code for _ in range(13)} == {302}
