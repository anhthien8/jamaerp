FROM python:3.12-slim

ARG SERVICE=backend

WORKDIR /app

# PostgreSQL client 17 từ kho PGDG (apt.postgresql.org, bookworm-pgdg) — chỉ backend cần
# để pg_dump khớp server 16/17 (bản mặc định Debian là v15, không dump được).
RUN if [ "$SERVICE" = "backend" ]; then \
      apt-get update && \
      apt-get install -y --no-install-recommends curl ca-certificates && \
      install -d /usr/share/postgresql-common/pgdg && \
      curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc && \
      echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list && \
      apt-get update && \
      apt-get install -y --no-install-recommends postgresql-client-17 && \
      apt-get purge -y --auto-remove curl && \
      rm -rf /var/lib/apt/lists/* ; \
    fi

# Backend service
RUN if [ "$SERVICE" = "backend" ]; then \
      cp backend/requirements.txt ./requirements.txt && \
      pip install --no-cache-dir -r requirements.txt && \
      cp -r backend/. . ; \
    fi

# Telegram-bot service
RUN if [ "$SERVICE" = "telegram-bot" ]; then \
      cp telegram-bot/requirements.txt ./requirements.txt && \
      pip install --no-cache-dir -r requirements.txt && \
      cp -r telegram-bot/. . ; \
    fi

RUN groupadd -r app && useradd -r -g app app
# /app thuộc root (0755) — user app cần thư mục backups ghi được để pg_dump xuất file
RUN if [ "$SERVICE" = "backend" ]; then chmod +x start.sh && mkdir -p /app/backups && chown -R app:app /app/backups; fi
USER app

# Start command varies by service
CMD if [ "$SERVICE" = "backend" ]; then \
      exec ./start.sh; \
    else \
      exec python -m bot.main; \
    fi
