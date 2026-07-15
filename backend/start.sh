#!/bin/sh
# Migrate schema (stamp baseline cho DB cũ, upgrade head cho mọi trường hợp)
python -m scripts.db_upgrade || echo "[WARN] db_upgrade failed — app se van khoi dong (create_all fallback)"

# Start the main app (uvicorn handles /health directly — no separate health server needed)
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
