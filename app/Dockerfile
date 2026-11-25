#build
FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

#runtime
FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS runtime
WORKDIR /app
# TODO: remove once python:3.12-slim-trixie ships libzstd1 >= 1.5.7+dfsg-1+deb13u1 (CVE-2026-124851)
RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade libzstd1 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
RUN groupadd  --gid 10001 shomer \
 && useradd  --uid 10001 --gid shomer --no-create-home --shell /usr/sbin/nologin shomer
USER 10001:10001
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "--factory", "shomer.api:app", "--host", "0.0.0.0", "--port", "8000"]
