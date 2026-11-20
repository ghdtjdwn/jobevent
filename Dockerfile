FROM ghcr.io/astral-sh/uv:0.11.25 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/jobevent-venv UV_LINK_MODE=copy PATH="/opt/jobevent-venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=jobevent.hosted.settings JOBEVENT_DATA_DIR=/var/lib/jobevent
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY jobevent ./jobevent
RUN uv sync --locked --no-dev --no-editable && groupadd --gid 10001 jobevent && useradd --uid 10001 --gid 10001 --no-create-home jobevent && install -d -m 700 -o jobevent -g jobevent /var/lib/jobevent
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn","jobevent.hosted.wsgi:application","--bind","0.0.0.0:8000","--workers","2","--threads","2","--timeout","300"]
