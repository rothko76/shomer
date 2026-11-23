#build
FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

#runtime
FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS runtime
WORKDIR /app
# TODO: remove once python:3.12-slim-trixie ships zlib1g >= 1:1.3.dfsg+really1.3.1-1+deb13u1 (CVE-2026-85091)
RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade zlib1g \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
RUN groupadd  --gid 10001 shomer \
 && useradd  --uid 10001 --gid shomer --no-create-home --shell /usr/sbin/nologin shomer
USER 10001:10001
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "--factory", "shomer.api:app", "--host", "0.0.0.0", "--port", "8000"]
