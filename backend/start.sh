#!/bin/sh
# Start health server in background
python health_server.py 8080 &
HEALTH_PID=$!

# Wait for health server to be ready
sleep 2

# Migrate schema (stamp baseline cho DB cũ, upgrade head cho mọi trường hợp)
python -m scripts.db_upgrade || echo "[WARN] db_upgrade failed — app se van khoi dong (create_all fallback)"

# Start the main app
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
