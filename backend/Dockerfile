FROM python:3.12-slim

WORKDIR /app

# PostgreSQL client 17 từ kho PGDG (apt.postgresql.org, bookworm-pgdg).
# KHÔNG dùng postgresql-client mặc định Debian (v15) — không dump được server 16/17.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
         -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
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
