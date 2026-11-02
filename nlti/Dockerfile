FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
COPY nlti ./nlti
COPY migrations ./migrations

RUN pip install --no-cache-dir .

RUN groupadd --system nlti && useradd --system --gid nlti nlti
USER nlti

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m nlti.seed && uvicorn nlti.api.main:app --host 0.0.0.0 --port 8000"]
