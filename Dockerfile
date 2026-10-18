FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PATH="/app/.venv/bin:$PATH" LANGGANIN_RUNTIME_DIR=/data
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && groupadd --system app && useradd --system --gid app app && mkdir /data && chown app:app /data
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "--threads=4", "config.wsgi:application"]
