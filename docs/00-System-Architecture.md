# System Architecture

> **Status**: Production  
> **Last Updated**: 2026-07-16  
> **Owner**: Product Team  
> **System**: JAMA HOME CRM v2.0

---

## 1. Executive Summary

JAMA HOME CRM is a full-stack, multi-channel business management platform built for Vietnamese construction and interior design companies. It manages the entire business lifecycle from lead acquisition through project delivery, with integrated HR, payroll, inventory, financial reporting, and field operations -- all accessible through both a web dashboard and a Telegram bot optimized for on-site workers.

**Key design principles:**
- **Telegram-first for field staff** -- sales and site workers operate primarily through Telegram; the web interface serves as the deep-work tool for office roles
- **Role-based everything** -- 8 distinct roles with scoped data visibility, from admin (full access) to data_entry (own leads only)
- **Audit everything** -- every sensitive mutation logged with before/after snapshots
- **Async-native** -- FastAPI + SQLAlchemy async for high-concurrency webhook processing

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React + Next.js 14 (TypeScript) | SPA with SSR, role-based navigation, dark theme |
| Backend | FastAPI (Python 3.11+) | Async REST API, webhook handlers, background tasks |
| Database | PostgreSQL 15 (prod) / SQLite (dev) | Relational storage via SQLAlchemy 2.0 async |
| ORM | SQLAlchemy 2.0 (mapped columns) | Models, migrations, optimized aggregate queries |
| Auth | JWT (HS256, 480min expiry) + RBAC | 8 roles, team-scoped access, delegation |
| Cache | Redis (Upstash, optional) / in-memory | Dashboard, P&L, accounting summaries |
| AI/LLM | Groq (Llama 3.3) / Ollama fallback | Lead scoring, instant quoting, AI suggestions |
| Bot | Telegram Bot API (aiogram 3.x) | Field reports, check-in/out, approvals, lead intake |
| Zalo Listener | Node.js (zca-js) ingest service | Listen-only Zalo group monitoring |
| Deployment | Railway (backend + bot) + Vercel (frontend) | CI/CD, auto-deploy, edge CDN |
| Backup | pg_dump + optional Google Drive | Daily automated backups with retention |

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Client Channels"
        FE["Next.js Frontend<br/>Vercel CDN"]
        TG["Telegram Bot<br/>aiogram 3.x<br/>Railway"]
        ZALO_INGEST["Zalo Ingest Service<br/>Node.js (zca-js)<br/>Listen-only"]
    end

    subgraph "API Layer - Railway"
        BE["FastAPI Backend"]
        JWT["JWT Middleware<br/>480min expiry"]
        RBAC["RBAC Guard<br/>8 roles"]
    end

    subgraph "Business Modules"
        MOD_LEADS["Leads Pipeline<br/>7 stages + kanban"]
        MOD_PROJ["Projects<br/>6 stages, 19 tasks"]
        MOD_ACCT["Accounting<br/>Transactions + P&L"]
        MOD_HR["HR + Payroll<br/>Attendance, Leave, Salary"]
        MOD_INV["Inventory<br/>Materials + Usage"]
        MOD_KPI["KPI Engine<br/>Scoring + Leaderboard"]
        MOD_APPROVAL["Approval Engine<br/>Multi-step + delegation"]
        MOD_AI["AI Services<br/>LLM integration"]
        MOD_AUTO["Automation<br/>Reminders + BOD reports"]
        MOD_QUOTE["Instant Quote<br/>3-tier pricing"]
        MOD_ZALO["Zalo Listener<br/>Signal analysis"]
    end

    subgraph "Data Layer"
        DB[("PostgreSQL<br/>Railway")]
        REDIS[("Redis<br/>Upstash")]
    end

    subgraph "External Services"
        GROQ["Groq API<br/>Llama 3.3"]
        TGBOT_API["Telegram Bot API"]
        ZALO_OA["Zalo OA"]
    end

    FE -->|"HTTPS + JWT"| BE
    TG -->|"Bot webhook + JWT"| BE
    ZALO_INGEST -->|"X-Zalo-Secret header"| BE
    BE --> JWT --> RBAC
    RBAC --> MOD_LEADS & MOD_PROJ & MOD_ACCT & MOD_HR & MOD_INV & MOD_KPI & MOD_APPROVAL & MOD_QUOTE & MOD_ZALO
    MOD_AI --> GROQ
    MOD_AUTO --> TGBOT_API
    MOD_LEADS & MOD_PROJ & MOD_ACCT & MOD_HR & MOD_INV & MOD_KPI & MOD_APPROVAL --> DB
    DB --> REDIS
    ZALO_OA -.->|"webhook"| ZALO_INGEST
```

---

## 4. Component Deep Dive

### 4.1 Frontend (React + Next.js)

| Aspect | Detail |
|--------|--------|
| Hosting | Vercel (edge CDN, automatic deploys from `main`) |
| Framework | Next.js 14 App Router, React 18 |
| State | Server components + client hooks (`useAuth`, `api` singleton) |
| Theming | CSS variables, dark theme default + "Outdoor" high-contrast mode for sunlight readability |
| Search | Global `Cmd+K` search modal across all entities |
| Demo Mode | Full offline demo with mock data (`demo-data.ts`), toggle in sidebar |
| Role Nav | `Sidebar.tsx` -- max 5 essential items per role, expandable "Xem them" for the rest |

**Role-Based Navigation (Sidebar Essentials):**

| Role | Essential Nav Items | Main Route (prefetch) |
|------|--------------------|-----------------------|
| admin | Dashboard, Approvals, Leads, Projects, P&L | `/leads` |
| executive | Dashboard, P&L, Projects, Reports | `/pl` |
| leader | Dashboard, Approvals, Leads, KPI, Attendance | `/leads` |
| data_entry | Dashboard, Leads, Instant Quote, Attendance, KPI | `/leads` |
| designer | Dashboard, Projects, Quotations, Attendance | `/projects` |
| pm | Dashboard, Projects, Approvals, Inventory, Attendance | `/projects` |
| accountant | Dashboard, Accounting, Attendance, Approvals, P&L | `/accounting` |
| purchasing | Dashboard, Inventory, Projects, Attendance | `/inventory` |

### 4.2 Backend (FastAPI)

| Aspect | Detail |
|--------|--------|
| Hosting | Railway (auto-deploy from `main`) |
| Database | PostgreSQL 15 via `asyncpg` driver |
| ORM | SQLAlchemy 2.0 with `Mapped` type annotations |
| Auth | JWT tokens (HS256), 480-minute expiry, `get_current_user` dependency |
| Caching | Redis (Upstash) with prefix-based invalidation; in-memory fallback |
| API prefix | `/api/v1/` -- 27+ routers |

**Key Backend Patterns:**
- **Aggregate queries over N+1**: Team attendance, project progress, pipeline stats all use single aggregate SQL instead of per-entity queries
- **Cache invalidation**: Dashboard, P&L, and accounting caches cleared on write operations via `cache.clear_prefix()`
- **Audit logging**: `log_action()` called on every sensitive mutation with before/after snapshots
- **Rate limiting**: Public instant-quote endpoint uses in-memory IP-based rate limiting (5 req/hour)

### 4.3 Telegram Bot

| Aspect | Detail |
|--------|--------|
| Hosting | Railway (separate service, same backend) |
| Framework | aiogram 3.x with FSM (finite state machines) |
| Auth | Telegram user ID mapped to CRM user via `telegram_user_id` field |
| Health check | Built-in HTTP server on `PORT` for Railway healthcheck |

**Available Telegram Commands:**

| Command | Description | Primary Users |
|---------|-------------|---------------|
| `/start` | Login/authenticate with CRM | All |
| `/briefing` | Personal daily briefing (leads, overdue, AI suggestions) | Sales, Leaders |
| `/pipeline` | Visual pipeline kanban + stats | Sales, Leaders |
| `/lead` | Intake new lead from Zalo text (AI-parsed) | Data entry |
| `/duan` | Project lookup by code | PM, Designer, Purchasing |
| `/baocao` | Site report with photo upload | PM, Designer |
| `/vatlieu` | Material purchase request | PM, Purchasing |
| `/suco` | Incident report with photo evidence | PM, Designer |
| `/checkin` | GPS check-in (office or project site) | All |
| `/checkout` | GPS check-out | All |
| `/feedback` | Submit feedback/suggestion | All |
| `/approve` | Inline approve/reject callbacks | Leaders, Admin |
| `/id` | Show group chat ID | Admin |

### 4.4 Zalo Listener

| Aspect | Detail |
|--------|--------|
| Architecture | Separate Node.js service (zca-js), listen-only |
| Communication | Pushes QR codes, heartbeats, and messages to FastAPI backend |
| Auth | Shared secret via `X-Zalo-Secret` header |
| Privacy | Consent reference stored per group; no outbound messages to Zalo |
| Signal types | `lead_candidate`, `commitment`, `quote_request`, `unanswered`, `deal_risk`, `faq` |

---

## 5. Data Flow Diagrams

### 5.1 Lead-to-Invoice Pipeline

```mermaid
sequenceDiagram
    participant Client as Client (Zalo/Web)
    participant DE as Data Entry
    participant Bot as Telegram Bot
    participant CRM as FastAPI Backend
    participant AI as AI Engine (Groq)
    participant Leader as Team Leader
    participant PM as Project Manager
    participant Acct as Accountant

    Client->>DE: Inquiry via Zalo/FB/website
    DE->>Bot: /lead [paste Zalo text]
    Bot->>CRM: POST /ai/parse-lead
    CRM->>AI: Extract name, phone, needs
    AI-->>CRM: Parsed lead data
    CRM-->>Bot: Confirmation card
    DE->>Bot: Confirm lead creation
    Bot->>CRM: POST /leads (stage: new)

    loop Lead nurturing (3-5 day SLA)
        CRM->>CRM: /briefing shows overdue leads
        DE->>CRM: Log activity (call/meeting)
        CRM->>CRM: Follow-up reminder (auto)
    end

    Note over CRM: Stage progression:<br/>new -> interested -> survey_scheduled -> potential

    CRM->>CRM: Lead stage: signed_design
    Note over CRM: AUTO-CREATE: Customer + Project<br/>+ 19 Tasks + Contract

    CRM->>Leader: Notification: New signed project
    CRM->>PM: Notification: Project assigned

    PM->>Bot: /baocao [progress update + photos]
    Bot->>CRM: TaskActivity logged

    PM->>Bot: /vatlieu [material request]
    Bot->>CRM: MaterialRequest (pending approval)
    CRM->>Acct: Approval notification

    Acct->>CRM: Approve via web or Telegram

    Note over CRM: Project: design -> quotation -> procurement<br/>-> construction -> acceptance -> completed

    Acct->>CRM: Record payment transaction
    CRM->>CRM: P&L recalculated automatically
```

### 5.2 Approval Workflow

```mermaid
stateDiagram-v2
    [*] --> Pending: Create Request

    Pending --> Approved: Approve (final step)
    Pending --> Rejected: Reject (with reason)
    Pending --> ChangesRequested: Request Changes
    Pending --> Cancelled: Cancel by requester

    ChangesRequested --> Pending: Resubmit (after fixes)

    Approved --> [*]
    Rejected --> [*]
    Cancelled --> [*]

    note right of Pending
        Multi-step chain support
        (Step 1 -> Step 2 -> ... -> Approved)

        Delegation when approver absent
        (delegate_to + delegate_until)

        Actions via Web OR Telegram
        (inline buttons + JWT auth)

        SLA-based escalation
        (due_at field)
    end note
```

### 5.3 Attendance + Payroll Lifecycle

```mermaid
sequenceDiagram
    participant User as Employee
    participant TG as Telegram Bot
    participant CRM as Backend
    participant Leader as Team Leader
    participant Acct as Accountant
    participant Admin as Admin

    User->>TG: /checkin (office) or /checkin [PRJ] (site GPS)
    TG->>CRM: POST /attendance/checkin
    CRM->>CRM: Create AttendanceRecord (source: telegram)

    User->>TG: /checkout
    TG->>CRM: POST /attendance/checkout
    CRM->>CRM: Calculate work_hours, ot_hours

    Note over CRM: Monthly payroll cycle

    Acct->>CRM: POST /payroll/generate?period=2026-07
    CRM->>CRM: Compute: base salary + OT + commission + BHXH + PIT
    CRM-->>Acct: Draft payroll (200 rows)

    Acct->>CRM: POST /payroll/2026-07/submit
    CRM->>CRM: Create ApprovalRequest (step 1: admin)
    CRM->>Admin: Notification: Payroll ready for approval

    Admin->>CRM: POST /approvals/{id}/approve
    CRM->>CRM: Lock period (no more attendance edits)

    Acct->>CRM: POST /payroll/2026-07/pay
    CRM->>CRM: Mark paid + send payslips via Telegram DM
    CRM-->>User: Private payslip via Telegram
```

---

## 6. Database Architecture

### 6.1 Entity Relationship Overview

```mermaid
erDiagram
    USER ||--o{ LEAD : "assigned"
    USER ||--o{ TEAM : "leads"
    TEAM ||--o{ USER : "members"
    USER ||--o{ TASK : "assigned"
    USER ||--o{ ATTENDANCE_RECORD : "daily"
    USER ||--o{ PAYROLL : "monthly"
    USER ||--o{ KPI_SNAPSHOT : "monthly"
    USER ||--o{ LEAVE_REQUEST : "requests"
    USER ||--o{ COACHING_NOTE : "receives"
    USER ||--o{ NOTIFICATION : "receives"
    USER ||--o{ AUDIT_LOG : "actions"

    LEAD ||--o{ ACTIVITY : "history"
    LEAD ||--o| PROJECT : "converts"
    LEAD ||--o{ QUOTATION : "quotes"

    PROJECT ||--o{ TASK : "tasks"
    PROJECT ||--o{ TASK_ACTIVITY : "updates"
    PROJECT ||--o{ CONTRACT : "contracts"
    PROJECT ||--o{ MATERIAL_USAGE : "materials"
    PROJECT ||--o{ TRANSACTION : "expenses"

    CONTRACT ||--o{ PAYMENT_INSTALLMENT : "payments"
    TASK ||--o{ TASK_ACTIVITY : "activities"

    APPROVAL_REQUEST }o--|| LEAVE_REQUEST : "links"
    APPROVAL_REQUEST }o--|| PAYROLL : "links"
    APPROVAL_REQUEST }o--|| SALARY_ADVANCE : "links"

    MATERIAL ||--o{ MATERIAL_USAGE : "usage_log"
    MATERIAL ||--o{ MATERIAL_REQUEST : "requests"
```

### 6.2 Key Tables

| Table | Records (est.) | Purpose |
|-------|----------------|---------|
| `users` | 200 | Employee accounts with role, department, team, Telegram mapping |
| `teams` | 10+ | Organizational teams with department and leader |
| `leads` | 2,000+ | CRM leads with 7-stage pipeline, source, classification |
| `activities` | 15,000+ | Lead interaction history (call, meeting, stage_change) |
| `projects` | 200+ | Active projects with 6-stage delivery pipeline |
| `tasks` | 3,800+ | 19 default tasks per project, with status and assignments |
| `task_activities` | 10,000+ | Site reports, material updates, photo evidence |
| `contracts` | 200+ | Revenue contracts with 4-installment payment terms |
| `quotations` | 500+ | Design and construction quotations with revision tracking |
| `attendance_records` | 10,000+ | Daily check-in/out with source, OT hours, GPS |
| `payroll` | 4,000+ | Monthly salary calculations with Vietnamese tax compliance |
| `commissions` | 1,000+ | Sales commissions tied to project milestones |
| `approval_requests` | 3,000+ | Multi-step approval chains with delegation support |
| `materials` | 500+ | Material catalog with stock levels and min-stock alerts |
| `material_usages` | 2,000+ | Material consumption linked to projects |
| `notifications` | 20,000+ | In-app + Telegram push notifications |
| `audit_logs` | 30,000+ | Full audit trail with before/after snapshots |
| `kpi_snapshots` | 1,500+ | Monthly KPI computations and rankings |
| `zalo_messages` | 5,000+ | Ingested Zalo messages for signal analysis |
| `zalo_signals` | 500+ | Detected lead candidates, quote requests, risks |
| `price_items` | 100+ | Instant quote pricing catalog (basic/standard/premium) |

---

## 7. RBAC Architecture

### 7.1 Role Hierarchy

```mermaid
graph TD
    subgraph "Leadership"
        ADMIN["admin<br/>Giám đốc<br/>Full system access"]
        EXEC["executive<br/>Ban Quan Tri<br/>Read-only P&L, Projects, Reports"]
    end

    subgraph "Management"
        LEADER["leader<br/>Truong Phong<br/>Team leads + approvals"]
        PM_ROLE["pm<br/>Truong Du An<br/>Project execution + inventory"]
        ACCT["accountant<br/>Ke Toan / Nhan Su<br/>Finance, payroll, HR"]
    end

    subgraph "Operations"
        DE["data_entry<br/>Nhan Vien Sale<br/>Own leads only + Telegram"]
        DESIGNER["designer<br/>Nhan Vien Thiet Ke<br/>Design tasks + quotations"]
        PURCHASING["purchasing<br/>Nhan Vien Thu Mua<br/>Inventory + procurement"]
    end

    ADMIN --> LEADER
    ADMIN --> PM_ROLE
    ADMIN --> ACCT
    LEADER --> DE
    LEADER --> DESIGNER
    PM_ROLE --> PURCHASING
```

### 7.2 Permission Matrix

| Capability | admin | executive | leader | data_entry | accountant | pm | designer | purchasing |
|------------|:-----:|:---------:|:------:|:----------:|:----------:|:--:|:--------:|:----------:|
| View all leads | Y | - | team | own | - | - | - | - |
| Create/edit leads | Y | - | team | own | - | - | - | - |
| Assign leads | Y | - | Y | - | - | - | - | - |
| View projects | Y | Y | Y | Y | Y | Y | assigned | Y |
| Create projects | Y | Y | Y | - | - | Y | - | - |
| Create/edit tasks | Y | - | Y | - | - | Y | own | - |
| View accounting | Y | - | Y | Y | Y | - | - | - |
| View P&L | Y | Y | - | - | Y | - | - | - |
| Manage payroll | Y | - | - | - | Y | - | - | - |
| Approve requests | Y | - | Y | - | Y | Y | - | Y |
| Manage inventory | Y | - | - | - | Y | Y | - | Y |
| Manage users | Y | - | - | - | Y | - | - | - |
| View KPI | Y | Y | Y | Y | - | Y | Y | Y |
| Attendance (own) | Y | Y | Y | Y | Y | Y | Y | Y |
| Attendance (team) | Y | - | Y | - | Y | - | - | - |

---

## 8. Infrastructure

### 8.1 Deployment Topology

```mermaid
graph LR
    subgraph "Vercel (Edge CDN)"
        VERCEL["Next.js Frontend<br/>Auto-deploy from main"]
    end

    subgraph "Railway (Backend)"
        BE_RAIL["FastAPI Backend<br/>Auto-deploy from main"]
        TG_RAIL["Telegram Bot<br/>Separate service"]
        PG_RAIL["PostgreSQL 15<br/>Managed database"]
        REDIS["Upstash Redis<br/>Cache layer"]
    end

    subgraph "Railway (Zalo)"
        ZALO_SERVICE["Zalo Ingest Service<br/>Node.js (zca-js)"]
    end

    subgraph "External APIs"
        GROQ_API["Groq API<br/>LLM inference"]
        TGBOT["Telegram Bot API"]
        ZALO_API["Zalo OA API"]
        GDRIVE["Google Drive<br/>Backup storage"]
    end

    VERCEL -->|"HTTPS + JWT"| BE_RAIL
    TG_RAIL -->|"HTTP + JWT"| BE_RAIL
    ZALO_SERVICE -->|"X-Zalo-Secret"| BE_RAIL
    BE_RAIL --> PG_RAIL
    BE_RAIL --> REDIS
    BE_RAIL --> GROQ_API
    TG_RAIL --> TGBOT
    BE_RAIL --> TGBOT
    ZALO_SERVICE -.-> ZALO_API
    BE_RAIL -.-> GDRIVE
```

### 8.2 Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | Backend | PostgreSQL connection string |
| `SECRET_KEY` | Backend | JWT signing key |
| `GROQ_API_KEY` | Backend | LLM API key for AI features |
| `OLLAMA_BASE_URL` | Backend | Fallback LLM endpoint |
| `TELEGRAM_BOT_TOKEN` | Bot | Telegram bot authentication |
| `ZALO_INGEST_SECRET` | Backend + Zalo | Shared secret for ingest service |
| `REDIS_URL` | Backend | Redis connection (optional) |
| `BACKUP_GDRIVE_*` | Backend | Google Drive backup credentials |

### 8.3 Security Architecture

| Control | Implementation |
|---------|---------------|
| Authentication | JWT (HS256, 480-min expiry), stored in memory (not localStorage) |
| Authorization | 8-role RBAC enforced in both backend middleware and frontend UI |
| Team scoping | Leaders see only their team; data_entry sees only own leads |
| Audit trail | Every mutation logged with actor, before/after, timestamp |
| API security | Security headers (CSP, HSTS, X-Frame-Options) applied globally |
| Telegram auth | User ID mapped to CRM account; inline callbacks verified via JWT |
| Zalo security | Shared secret header; listen-only (no outbound Zalo messages) |
| Backup | Automated pg_dump with configurable retention + Google Drive upload |
| Period lock | Payroll approval locks the attendance period, preventing edits |

---

## 9. Automation & Background Jobs

| Job | Trigger | Action |
|-----|---------|--------|
| Follow-up Reminder | Scheduled (configurable days) | Notify sales about leads not contacted within SLA |
| Lead Recall | Scheduled (configurable days) | Reassign overdue leads to less-loaded sales reps |
| Payment Reminder | Scheduled | Notify about pending contract payment milestones |
| BOD Report | Daily/weekly/monthly (configurable hour) | Generate and push executive summary to Telegram group |
| Group Briefing | Manual or scheduled | Team performance summary to Telegram group chat |
| Payroll Generation | Manual (accountant) | Calculate monthly salary for all active employees |
| Payroll Payment | Manual (accountant) | Mark paid + send private payslips via Telegram DM |

---

## 10. Scalability Considerations

| Dimension | Current | Growth Path |
|-----------|---------|-------------|
| Users | 200 employees | Add read replicas, connection pooling (PgBouncer) |
| Leads | ~2,000 | Already indexed; add partitioning if >100K |
| API traffic | Moderate (web + bot) | Redis caching already in place; add rate limiting |
| File storage | Telegram photos (CDN) | Migrate to S3-compatible storage |
| Multi-tenant | Single tenant | Schema-per-tenant or row-level security (see Whitelabel Strategy) |

---

## Related Documentation

- [[04-Real-World-Usecases]] -- Daily workflows for every role
- [[05-Mermaid-Diagrams]] -- All system diagrams in one place
- [[06-Whitelabel-Strategy]] -- Multi-tenant and industry expansion plans
