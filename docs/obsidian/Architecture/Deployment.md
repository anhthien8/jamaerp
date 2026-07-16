# Deployment Architecture — JAMA HOME CRM

## Infrastructure Overview

```mermaid
graph TB
    subgraph Vercel["Vercel — Frontend"]
        NextJS["Next.js 14<br/>Auto-deploy from main"]
        VercelEdge["Edge Network<br/>CDN + SSR"]
    end

    subgraph Railway["Railway — Backend"]
        FastAPI["FastAPI Service<br/>gunicorn + uvicorn workers"]
        Scheduler["APScheduler<br/>Embedded in FastAPI"]
        PostgreSQL[("PostgreSQL<br/>Railway managed")]
    end

    subgraph External["External Services"]
        TelegramAPI["Telegram Bot API"]
        OpenAIAPI["OpenAI API"]
        ZaloIngest["Zalo Ingest (optional)<br/>Node.js / zca-js"]
    end

    Users["200 Employees<br/>+ Customers"] -->|"HTTPS"| VercelEdge
    VercelEdge --> NextJS
    NextJS -->|"REST API<br/>BACKEND_URL"| FastAPI
    FastAPI --> PostgreSQL
    FastAPI -->|"Bot Token"| TelegramAPI
    FastAPI -->|"API Key"| OpenAIAPI
    ZaloIngest -->|"REST push"| FastAPI
    Scheduler -->|"Cron triggers"| FastAPI

    style Vercel fill:#000,color:#fff
    style Railway fill:#0a0a23,color:#fff
```

## Production URLs

| Service | URL | Platform |
|---------|-----|----------|
| Frontend | `https://jama-crm.vercel.app` | Vercel |
| Backend API | `https://jama-crm.up.railway.app` | Railway |
| API Docs | `https://jama-crm.up.railway.app/docs` | Railway (Swagger) |
| PostgreSQL | Internal Railway URL | Railway managed |

## Environment Variables

### Backend (Railway)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/jama_crm

# Auth
SECRET_KEY=<jwt-signing-key>
TELEGRAM_AUTH_SECRET=<shared-secret-for-telegram-auth>

# Telegram
TELEGRAM_BOT_TOKEN=<bot-token>
TELEGRAM_WEBHOOK_URL=<optional-webhook>

# AI
OPENAI_API_KEY=<sk-...>

# CORS
FRONTEND_URL=https://jama-crm.vercel.app
```

### Frontend (Vercel)

```bash
NEXT_PUBLIC_API_URL=https://jama-crm.up.railway.app
```

## Scheduled Jobs (APScheduler)

```mermaid
gantt
    title Cron Jobs — Lịch trình tự động
    dateFormat HH:mm
    axisFormat %H:%M

    section Daily (Asia/Ho_Chi_Minh)
    BOD Daily Report           :active, 07:00, 5m
    Follow-up Reminders        :active, 07:00, 5m
    Group Briefing (Telegram)  :active, 07:00, 5m
    Auto-close Attendance      :active, 00:00, 5m
    Approval Escalation        :active, 00:00, 5m
    Reassign Orphaned Approvals:active, 00:30, 5m
    Zalo Message Cleanup (>7d) :active, 00:00, 5m
    KPI Monthly Snapshot       :crit, 00:10, 10m
    Lead Recall Check          :active, 08:00, 5m
    Payment Reminder           :active, 09:00, 5m
```

## Database Migrations

- **ORM**: SQLAlchemy 2.0 (async) with declarative models
- **Migrations**: Alembic (if used) or `create_all()` for development
- **Seed data**: Admin user + salary grades + price items on first boot

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Auth | JWT with role + department claims, bcrypt password hashing |
| Rate limiting | In-memory limiter on login (5 attempts/60s per IP) |
| Telegram auth | Shared secret (`TELEGRAM_AUTH_SECRET`) via HMAC comparison |
| Sensitive data | Audit log for salary, role changes, approvals |
| Payslips | Sent via Telegram DM only (never group chat) |
| CORS | Restricted to `FRONTEND_URL` |
| SQL injection | SQLAlchemy ORM (parameterized queries) |
| Zalo consent | `consent_ref` field on ZaloGroup for compliance |

## Monitoring & Observability

- **Health check**: `GET /health` endpoint on FastAPI
- **Logging**: Python `logging` module, structured logs
- **Audit trail**: `audit_logs` table captures all sensitive operations
- **Telegram alerts**: BOD daily report, escalation notifications

## Scaling Considerations

| Component | Current | Scale Path |
|-----------|---------|-----------|
| Backend | Single Railway service | Horizontal (multiple workers via gunicorn) |
| Database | Railway PostgreSQL | Connection pooling, read replicas |
| Frontend | Vercel (auto-scale) | Already globally distributed |
| Scheduler | Embedded in FastAPI | Externalize to dedicated worker if needed |

## Tags

#deployment #infrastructure #devops #jama-home
