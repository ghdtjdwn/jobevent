import ipaddress
import json
import re
import shutil
from importlib.resources import files
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import RequestDataTooBig
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from filelock import Timeout

from jobevent.pipeline import Failure, public_url

from .pdf import extract
from .tenants import account_dir, mutex, quota, service_for


class ResponsePolicy:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.get_host()  # enforce ALLOWED_HOSTS on every route
        if request.method == "POST":
            max_length = (
                5_400_000
                if request.path == "/api/pdf"
                else 100_000
                if request.path.startswith("/api/")
                else 16_384
            )
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                return error("요청 크기가 올바르지 않습니다.", 400)
            if length > max_length:
                return error("요청이 너무 큽니다.", 413)
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        )
        return response


def client_address(request):
    if settings.TRUST_PROXY:
        try:
            return str(ipaddress.ip_address(request.META.get("HTTP_X_REAL_IP", "")))
        except ValueError:
            pass
    return request.META.get("REMOTE_ADDR", "unknown")


def allowed_reference(url):
    if not public_url(url):
        return False
    if re.fullmatch(r"https://github\.com/[A-Za-z0-9-]+/?", url):
        return True
    return (
        urlsplit(url)
        .hostname.lower()
        .endswith((".github.io", ".vercel.app", ".notion.site"))
    )


def error(msg, status):
    return JsonResponse({"error": msg}, status=status)


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def home(request):
    return redirect("/app" if request.user.is_authenticated else "/signup")


MOBILE_ASSETS = {
    "manifest.webmanifest": "application/manifest+json",
    "install.js": "text/javascript",
    "sw.js": "text/javascript",
    **{f"icon-{size}.png": "image/png" for size in (180, 192, 512)},
}


@require_GET
def mobile_asset(request, name):
    return HttpResponse(
        files("jobevent.static").joinpath(name).read_bytes(),
        content_type=MOBILE_ASSETS[name],
    )


@require_GET
def asset(request, name):
    return HttpResponse(
        files("jobevent.static").joinpath(name).read_bytes(),
        content_type=("text/css" if name == "style.css" else "text/javascript")
        + "; charset=utf-8",
    )


@require_GET
@login_required
@ensure_csrf_cookie
def studio(request):
    return HttpResponse(
        files("jobevent.static")
        .joinpath("index.html")
        .read_bytes()
        .replace(
            b"<!-- mobile-head -->",
            files("jobevent.hosted")
            .joinpath("templates/hosted/mobile.html")
            .read_bytes(),
        ),
        content_type="text/html; charset=utf-8",
    )


@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def account_form(request, signup):
    if request.user.is_authenticated:
        return redirect("/app")
    message = ""
    status = 200
    if request.method == "POST":
        address = client_address(request)
        if not quota(
            "signup" if signup else "login", address, 8 if signup else 40, 3600
        ):
            return HttpResponse(
                "시도 횟수 제한에 도달했습니다. 잠시 후 다시 시도하세요.", status=429
            )
        if not signup and not quota(
            "login-name", request.POST.get("username", "").casefold(), 12, 900
        ):
            return HttpResponse(
                "시도 횟수 제한에 도달했습니다. 잠시 후 다시 시도하세요.", status=429
            )
    data = request.POST if request.method == "POST" else None
    form = UserCreationForm(data) if signup else AuthenticationForm(request, data=data)
    if request.method == "POST" and form.is_valid():
        if signup:
            try:
                with mutex("signup"):
                    if get_user_model().objects.count() >= settings.MAX_ACCOUNTS:
                        message = "현재 서버의 가입 한도에 도달했습니다."
                        status = 429
                    elif (
                        get_user_model()
                        .objects.filter(username=form.cleaned_data["username"])
                        .exists()
                    ):
                        message = "사용할 수 없는 아이디입니다."
                        status = 400
                    else:
                        user = form.save()
            except Timeout:
                return HttpResponse(
                    "다른 가입 처리 중입니다. 잠시 후 다시 시도하세요.", status=409
                )
        else:
            user = form.get_user()
        if not message:
            login(request, user)
            return redirect("/app")
    return render(
        request,
        "hosted/auth.html",
        {"signup": signup, "form": form, "message": message},
        status=status,
    )


@require_POST
def signout(request):
    logout(request)
    return redirect("/signin")


@require_POST
@sensitive_post_parameters("password")
def delete_account(request):
    if not request.user.is_authenticated:
        return error("로그인이 필요합니다.", 401)
    uid = request.user.pk
    if not quota("delete", uid, 8, 900):
        return error("잠시 후 다시 시도하세요.", 429)
    if not request.user.check_password(request.POST.get("password", "")):
        return error("비밀번호가 일치하지 않습니다.", 400)
    try:
        with mutex(f"user-{uid}"):
            directory = account_dir(uid)
            if directory.exists():
                shutil.rmtree(directory)
            request.user.delete()
            logout(request)
            return redirect("/signup")
    except Timeout:
        return error("실행 중입니다. 완료 후 다시 시도하세요.", 409)


@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def api(request, operation):
    if not request.user.is_authenticated:
        return error("로그인이 필요합니다.", 401)
    uid = request.user.pk
    if operation == "state" and request.method == "GET":
        try:
            with mutex(f"user-{uid}"):
                if not get_user_model().objects.filter(pk=uid, is_active=True).exists():
                    return error("로그인이 필요합니다.", 401)
                return JsonResponse(
                    {
                        **service_for(uid).state(),
                        "hosted": True,
                        "username": request.user.get_username(),
                    }
                )
        except Timeout:
            return error("다른 작업이 진행 중입니다. 잠시 후 다시 시도하세요.", 409)
    if request.method != "POST" or operation not in (
        "profile",
        "room",
        "forget",
        "delete",
        "send",
        "preview",
        "reference",
        "pdf",
    ):
        return error("지원하지 않는 작업입니다.", 404)
    if request.content_type != "application/json":
        return error("JSON 요청이 필요합니다.", 415)
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
        if not 0 < length <= (5_400_000 if operation == "pdf" else 100_000):
            return error("요청 크기를 확인하세요.", 413)
        data = json.loads(request.body)
    except RequestDataTooBig:
        return error("요청이 너무 큽니다.", 413)
    except (ValueError, RecursionError):
        return error("올바른 JSON이 아닙니다.", 400)
    if not isinstance(data, dict):
        return error("입력 형식 오류", 400)
    if operation in ("send", "preview", "reference", "pdf") and not quota(
        "work", uid, 12, 3600
    ):
        return error("시간당 수동 작업 한도(12회)에 도달했습니다.", 429)
    try:
        with mutex(f"user-{uid}"):
            # An authenticated request might have waited behind account deletion.
            if not get_user_model().objects.filter(pk=uid, is_active=True).exists():
                return error("로그인이 필요합니다.", 401)
            service = service_for(uid)
            if (
                operation == "room"
                and not data.get("id")
                and len(service.store.rooms()) >= 12
            ):
                return error("계정당 알림방은 최대 12개입니다.", 400)
            if operation == "reference" and not allowed_reference(data.get("url")):
                return error(
                    "공개 GitHub 사용자 링크, GitHub Pages·Vercel·Notion의 기본 도메인 페이지만 읽습니다. 다른 포트폴리오는 파일이나 텍스트로 추가하세요.",
                    400,
                )
            if operation == "pdf":
                return JsonResponse({"text": extract(data.get("data"))})
            return JsonResponse(service.change("/api/" + operation, data))
    except Timeout:
        return error("다른 작업이 진행 중입니다. 잠시 후 다시 시도하세요.", 409)
    except (ValueError, Failure) as exc:
        return error(str(exc)[:180], 400)
    except Exception:
        return error("처리하지 못했습니다. 설정 또는 서버 상태를 확인하세요.", 500)
