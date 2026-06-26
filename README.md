# JAMA HOME CRM System
# Telegram-First AI Agents CRM for Interior Design Company

## Quick Start

```bash
# Copy env
cp .env.example .env
# Edit .env with your values

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Access
# - CRM Web: http://localhost:3000
# - API Docs: http://localhost:8000/docs
# - Telegram Bot: configured via BOT_TOKEN
```

## Architecture
- **Backend:** FastAPI (Python 3.12)
- **Database:** PostgreSQL 16
- **Cache:** Redis 7
- **Telegram Bot:** aiogram 3.x
- **Frontend:** Next.js 14
- **AI:** CrewAI + LiteLLM

## Project Structure
```
jama-crm/
├── backend/          # FastAPI API server
├── telegram-bot/     # Telegram Bot
├── frontend/         # Next.js CRM Dashboard
├── docker-compose.yml
└── .env.example
```
