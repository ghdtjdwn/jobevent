"""Single-node hosted deployment. Both web and worker mount the same private volume."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.environ["JOBEVENT_SECRET_KEY"]
ENCRYPTION_KEY = os.environ["JOBEVENT_ENCRYPTION_KEY"]
if len(SECRET_KEY) < 50 or SECRET_KEY == ENCRYPTION_KEY:
    raise ImproperlyConfigured("서명용 키와 암호화 키를 각각 안전하게 생성하세요.")
Fernet(ENCRYPTION_KEY)  # Fail before starting either process with an invalid key.
DEV = os.environ.get("JOBEVENT_DEV") == "1"
origin = urlsplit(os.environ["JOBEVENT_ORIGIN"])
if (
    not origin.hostname
    or origin.path not in ("", "/")
    or origin.query
    or origin.fragment
    or origin.username
    or origin.password
    or "*" in origin.netloc
    or (
        origin.scheme != "https"
        and not (
            DEV
            and origin.scheme == "http"
            and origin.hostname in ("localhost", "127.0.0.1")
        )
    )
):
    raise ImproperlyConfigured(
        "JOBEVENT_ORIGIN에는 서비스의 HTTPS origin을 지정하세요."
    )
ALLOWED_HOSTS = [origin.hostname]
DATA_DIR = Path(os.environ["JOBEVENT_DATA_DIR"]).resolve()
DATA_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "accounts.sqlite3",
        "OPTIONS": {"timeout": 10},
    }
}
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "jobevent.hosted",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "jobevent.hosted.views.ResponsePolicy",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [
    {"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}
]
ROOT_URLCONF = "jobevent.hosted.urls"
WSGI_APPLICATION = "jobevent.hosted.wsgi.application"
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "ko-kr"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/signin"
DEBUG = False
SECURE_SSL_REDIRECT = not DEV
TRUST_PROXY = os.environ.get("JOBEVENT_TRUST_PROXY") == "1"
if TRUST_PROXY:
    # Only behind a trusted proxy that overwrites the client's header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEV
SECURE_HSTS_SECONDS = 0 if DEV else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEV
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
DATA_UPLOAD_MAX_MEMORY_SIZE = 5_400_000
DATA_UPLOAD_MAX_NUMBER_FIELDS = 12
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{name}"}
    for name in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]
MAX_ACCOUNTS = int(os.environ.get("JOBEVENT_MAX_ACCOUNTS", "100"))
