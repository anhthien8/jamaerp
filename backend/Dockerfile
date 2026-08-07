FROM python:3.12-slim

WORKDIR /app

# PostgreSQL client 18 từ kho PGDG (apt.postgresql.org) — codename lấy ĐỘNG từ os-release
# (python:3.12-slim hiện là trixie/Debian 13; hardcode bookworm từng làm build fail).
# Server Railway là PostgreSQL 18 → pg_dump phải >= 18 (client 17 từ chối server 18).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
         -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN groupadd -r app && useradd -r -g app app
RUN chmod +x start.sh
# /app thuộc root (0755) — user app cần thư mục backups ghi được để pg_dump xuất file
RUN mkdir -p /app/backups && chown -R app:app /app/backups
USER app

# Health server on 8080 + app on $PORT (8000 default)
CMD ["./start.sh"]
