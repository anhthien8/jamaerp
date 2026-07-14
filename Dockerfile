FROM node:20-alpine AS builder

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN apk add --no-cache python3 py3-pip && \
    pip3 install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/backend/

WORKDIR /app/backend

ENV PYTHONPATH=/app/backend
ENV APP_ENV=production
ENV DEBUG=false

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
