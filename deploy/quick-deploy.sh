#!/bin/bash
# ============================================================
# JAMA HOME CRM — Quick Deploy (Update existing installation)
# Usage: bash quick-deploy.sh
# ============================================================

set -e

APP_DIR="/opt/jama-crm"

echo "🔄 Updating JAMA CRM..."

# Check if app is installed
if [ ! -d "$APP_DIR" ]; then
    echo "❌ JAMA CRM not found at $APP_DIR"
    echo "Run setup.sh first: bash setup.sh your-domain.com"
    exit 1
fi

cd "$APP_DIR"

# Pull latest changes
echo "📥 Pulling latest changes..."
git pull origin main

# Rebuild and restart
echo "🔨 Rebuilding containers..."
docker compose -f docker-compose.prod.yml up -d --build

# Wait for health check
echo "⏳ Waiting for services..."
sleep 10

# Check health
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy!"
else
    echo "⚠️  Backend not yet healthy — check logs: ./logs.sh backend"
fi

echo ""
echo "✅ Update complete!"
echo ""
echo "📋 Quick commands:"
echo "  Status:  ./status.sh"
echo "  Logs:    ./logs.sh backend"
echo "  Restart: ./restart.sh"
