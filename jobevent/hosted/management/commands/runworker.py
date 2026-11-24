import time
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection
from filelock import Timeout

from jobevent.hosted.tenants import account_dir, mutex, service_for

# Accounts run in parallel up to this bound; one account never runs twice at once.
WORKERS = 4


class Command(BaseCommand):
    help = "가입자가 브라우저를 닫아도 예약된 알림방을 처리합니다."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="한 번만 확인 후 종료")

    def handle(self, *args, **opts):
        users = get_user_model().objects.filter(is_active=True)
        last_cleanup = 0
        running = {}
        with ThreadPoolExecutor(WORKERS) as pool:
            while True:
                close_old_connections()
                if time.monotonic() - last_cleanup > 3600 or not last_cleanup:
                    SessionStore.clear_expired()
                    last_cleanup = time.monotonic()
                running = {u: f for u, f in running.items() if not f.done()}
                for uid in users.values_list("pk", flat=True):
                    if uid not in running:
                        running[uid] = pool.submit(self.run_account, users, uid)
                if opts["once"]:
                    for f in running.values():
                        f.result()
                    return
                time.sleep(5)

    def run_account(self, users, uid):
        try:
            with mutex(f"user-{uid}"):
                if account_dir(uid).is_dir() and users.filter(pk=uid).exists():
                    service_for(uid).tick()
        except Timeout:
            pass  # concurrent edit, run, deletion, or another worker
        except Exception as e:
            # Never echo profile, webhook or provider exception. Other accounts still run.
            self.stderr.write(
                f"계정 예약 처리 실패 · user={uid} error={type(e).__name__} · 데이터 볼륨과 암호화 키를 확인하세요."
            )
        finally:
            connection.close()  # each pool thread owns its own connection
