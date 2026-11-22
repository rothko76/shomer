#build
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

#runtime
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS runtime
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
