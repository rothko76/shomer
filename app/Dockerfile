#build
FROM python:3.12.16-slim-trixie@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

#runtime
FROM python:3.12.16-slim-trixie@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
RUN groupadd  --gid 10001 shomer \
 && useradd  --uid 10001 --gid shomer --no-create-home --shell /usr/sbin/nologin shomer
USER 10001:10001
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "--factory", "shomer.api:app", "--host", "0.0.0.0", "--port", "8000"]
