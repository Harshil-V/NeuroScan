FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

WORKDIR /app
COPY services/api-service/pyproject.toml services/api-service/uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY services/api-service/app ./app
COPY services/api-service/alembic.ini ./
# PHI rule list read by app/deid/rules.py; placed at /app/data/deid-rules.json
COPY data/deid-rules.json ./data/deid-rules.json

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
