FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN groupadd -r app && useradd -r -g app app
USER app

# Health server on port 8080 — responds instantly to Railway healthcheck
# App on port $PORT (8000 default) — starts after health server is up
ENTRYPOINT ["sh", "-c", "python health_server.py 8080 & sleep 3 && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
