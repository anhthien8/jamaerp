#!/bin/sh
# Start health server in background
python health_server.py 8080 &
HEALTH_PID=$!

# Wait for health server to be ready
sleep 2

# Start the main app
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
