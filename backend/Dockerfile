FROM python:3.12-slim

WORKDIR /app

# Support both root-level and backend-level build contexts
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Non-root user
RUN groupadd -r app && useradd -r -g app app
USER app

# Railway injects PORT env var
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  SHELL ["/bin/sh", "-c"] \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
