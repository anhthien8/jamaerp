# System Architecture

> **Status**: Current state analysis as of July 2026
> **Last Updated**: 2026-07-16
> **Owner**: Product Team

---

## Overview

JAMA HOME CRM is a full-stack web application built for construction/interior design companies in Vietnam. It covers the entire business lifecycle from lead acquisition to project delivery, with integrated HR, payroll, inventory, and financial management.

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React + Next.js (TypeScript) | SPA with SSR, role-based routing |
| Backend | FastAPI (Python 3.11+) | Async REST API, webhook handling |
| Database | PostgreSQL (prod) / SQLite (dev) | Relational storage via SQLAlchemy async |
| ORM | SQLAlchemy 2.0 (async, mapped) | Models, migrations, queries |
| Auth | JWT (HS256) + RBAC | 8 roles, team-scoped access |
| Cache | Redis (optional) / in-memory | Dashboard, P&L, accounting summaries |
| AI/LLM | Groq (Llama 3.3) / Ollama fallback | Lead scoring, AI insights |
| Bot | Telegram Bot API | Field reports, check-in/out, approvals |
| Deployment | Railway (backend) + Vercel (frontend) | CI/CD, auto-deploy |

---

## Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        FE[Next.js Frontend<br/>Vercel]
        TG[Telegram Bot<br/>Webhook]
    end

    subgraph "API Gateway"
        BE[FastAPI Backend<br/>Railway]
        JWT[JWT Auth Middleware]
        RBAC[RBAC Guard]
    end

    subgraph "Application Layer"
        MOD_LEADS[Leads Module]
        MOD_PROJ[Projects Module]
        MOD_ACCT[Accounting Module]
        MOD_HR[HR Module]
        MOD_INV[Inventory Module]
        MOD_KPI[KPI Module]
        MOD_APPROVAL[Approval Engine]
        MOD_AI[AI Services]
        MOD_AUTO[Automation Engine]
    end

    subgraph "Data Layer"
        DB[(PostgreSQL)]
        REDIS[(Redis Cache)]
    end

    subgraph "External Integrations"
        GROQ[Groq LLM API]
        OLLAMA[Ollama Local LLM]
        TELEGRAM[Telegram Bot API]
    end

    FE --> BE
    TG --> BE
    BE --> JWT
    JWT --> RBAC
    RBAC --> MOD_LEADS
    RBAC --> MOD_PROJ
    RBAC --> MOD_ACCT
    RBAC --> MOD_HR
    RBAC --> MOD_INV
    RBAC --> MOD_KPI
    MOD_APPROVAL -.-> MOD_LEADS
    MOD_APPROVAL -.-> MOD_PROJ
    MOD_APPROVAL -.-> MOD_ACCT
    MOD_APPROVAL -.-> MOD_HR
    MOD_AI --> GROQ
    MOD_AI --> OLLAMA
    MOD_AUTO --> TELEGRAM
    MOD_LEADS --> DB
    MOD_PROJ --> DB
    MOD_ACCT --> DB
    MOD_HR --> DB
    MOD_INV --> DB
    MOD_KPI --> DB
    MOD_APPROVAL --> DB
    DB --> REDIS
```

---

## Module Map

```mermaid
graph LR
    subgraph "Sales Pipeline"
        A[Lead Management<br/>7 stages] --> B[Auto-Convert to<br/>Project + Contract]
    end

    subgraph "Project Delivery"
        B --> C[Task Management<br/>19 default tasks]
        C --> D[Site Reporting<br/>via Telegram]
        C --> E[Material Requests<br/>Approval workflow]
    end

    subgraph "Finance"
        B --> F[Contract &<br/>Payment Terms]
        F --> G[Transaction<br/>Tracking]
        G --> H[P&L Analysis]
    end

    subgraph "HR & Payroll"
        I[Attendance<br/>Web + Telegram] --> J[Payroll Engine]
        K[Leave Management] --> J
        J --> L[Payslip Delivery<br/>via Telegram]
    end

    subgraph "Inventory"
        M[Material Catalog] --> N[Stock Tracking]
        E --> N
        N --> O[Usage by Project]
    end

    subgraph "Governance"
        P[Approval Engine] --> Q[Audit Log]
        R[KPI Engine] --> S[Performance Reviews]
    end
```

---

## Data Flow: Lead to Revenue

```mermaid
sequenceDiagram
    participant Zalo as Zalo/Website
    participant CRM as JAMA CRM
    participant PM as Project Manager
    participant TG as Telegram Bot
    participant ACC as Accountant

    Zalo->>CRM: New lead created (data_entry)
    CRM->>CRM: AI scoring + auto-assign to team
    loop Lead nurturing
        CRM->>CRM: Activity logged (call/meeting/survey)
        CRM->>CRM: Follow-up reminder (3-day SLA)
    end
    CRM->>CRM: Lead stage: new -> interested -> survey_scheduled -> potential
    CRM->>CRM: Lead stage: signed_design
    Note over CRM: Auto-creates: Customer + Project<br/>+ 19 Tasks + Contract
    CRM->>PM: Notification: New project assigned
    PM->>TG: /baocao (site report with photos)
    TG->>CRM: Site report logged as TaskActivity
    TG->>TG: /vatlieu (material request)
    TG->>CRM: MaterialRequest (pending approval)
    CRM->>ACC: Approval notification
    ACC->>CRM: Approve/reject via web or Telegram
    Note over CRM: Project progresses through 6 stages
    CRM->>CRM: Payment milestones tracked in Contract
    ACC->>CRM: Transaction recorded per payment
    CRM->>CRM: P&L calculated from contracts - costs
```

---

## Data Flow: Approval Engine

```mermaid
stateDiagram-v2
    [*] --> Pending: Create Request

    Pending --> Approved: Approve (final step)
    Pending --> Rejected: Reject
    Pending --> ChangesRequested: Request Changes
    Pending --> Cancelled: Cancel by requester

    ChangesRequested --> Pending: Resubmit

    Approved --> [*]
    Rejected --> [*]
    Cancelled --> [*]

    note right of Pending
        Multi-step chain support
        Delegation when absent
        SLA-based escalation
        Web + Telegram actions
    end note
```

---

## API Router Inventory (27 routers)

| Router | Prefix | Purpose | Key RBAC |
|--------|--------|---------|----------|
| [[api-auth]] | `/api/v1/auth` | Login, Telegram auth | All users |
| [[api-leads]] | `/api/v1/leads` | CRUD, pipeline, kanban, CSV export | data_entry: own; leader: team; admin: all |
| [[api-projects]] | `/api/v1/projects` | CRUD, tasks, stage progression | PM/designer/sales: assigned; leader: all |
| [[api-dashboard]] | `/api/v1/dashboard` | Executive & personal dashboards | Role-specific view |
| [[api-accounting]] | `/api/v1/accounting` | Transactions, commissions, payroll listing | accountant/admin |
| [[api-pl]] | `/api/v1/pl` | P&L summary + per-project detail | admin/executive/accountant |
| [[api-hr]] | `/api/v1/hr` | Resignation, handover, undo-resign | admin/leader |
| [[api-kpi]] | `/api/v1/kpi` | KPI compute, leaderboard, coaching, reviews | Role-scoped |
| [[api-attendance]] | `/api/v1/attendance` | Check-in/out, team table, OT approval | All (personal); leader/admin (team) |
| [[api-approvals]] | `/api/v1/approvals` | Central approval hub, delegation | Approvers + delegated |
| [[api-leaves]] | `/api/v1/leaves` | Leave requests, balance, calendar | All (own); leader (team) |
| [[api-payroll]] | `/api/v1/payroll` | Generate, edit, submit, approve, pay | accountant (edit); admin (approve) |
| [[api-inventory]] | `/api/v1/inventory` | Materials, stock, usage tracking | admin/purchasing/accountant |
| [[api-telegram]] | `/api/v1/telegram` | Bot commands: reports, materials, incidents | Telegram-authenticated |
| [[api-automation]] | `/api/v1/automation` | Reminders, BOD reports, group briefing | admin/executive |
| [[api-notifications]] | `/api/v1/notifications` | In-app notification CRUD | All users |
| [[api-audit]] | `/api/v1/audit-logs` | Audit trail query | admin only |
| [[api-backup]] | `/api/v1/backup` | Database backup/restore | admin |
| [[api-users]] | `/api/v1/users` | User CRUD, team management | admin |
| [[api-customers]] | `/api/v1/customers` | Customer records | Various |
| [[api-contracts]] | `/api/v1/contracts` | Contract CRUD, payment terms | PM/leader/admin |
| [[api-quotations]] | `/api/v1/quotations` | Quotation management | PM/leader/designer/admin |
| [[api-instant-quote]] | `/api/v1/instant-quote` | AI-powered instant quoting | PM/leader/designer/admin |
| [[api-feedback]] | `/api/v1/feedback` | User feedback submission | All users |
| [[api-salary-grades]] | `/api/v1/salary-grades` | Salary grade management | admin/accountant |
| [[api-fixed-costs]] | `/api/v1/fixed-costs` | Fixed cost tracking | admin/accountant |
| [[api-variable-costs]] | `/api/v1/variable-costs` | Variable cost tracking | admin/accountant |
| [[api-commission-structures]] | `/api/v1/commission-structures` | Commission rules | admin/accountant |

---

## Database Model Map

```mermaid
erDiagram
    User ||--o{ Lead : "assigned"
    User ||--o{ Team : "leads"
    Team ||--o{ User : "members"
    User ||--o{ Task : "assigned"
    User ||--o{ AttendanceRecord : "daily"
    User ||--o{ Payroll : "monthly"
    User ||--o{ KpiSnapshot : "monthly"
    User ||--o{ LeaveBalance : "yearly"
    User ||--o{ LeaveRequest : "requests"
    User ||--o{ CoachingNote : "receives"
    User ||--o{ ReviewCycle : "reviews"

    Lead ||--o{ Activity : "history"
    Lead ||--o| Project : "converts"
    Lead ||--o{ Quotation : "quotes"

    Project ||--o{ Task : "tasks"
    Project ||--o{ TaskActivity : "updates"
    Project ||--o{ Contract : "contracts"
    Project ||--o{ MaterialUsage : "materials"
    Project ||--o{ MaterialRequest : "requests"
    Project ||--o{ Transaction : "expenses"

    Contract ||--o{ PaymentInstallment : "payments"
    Task ||--o{ TaskActivity : "activities"

    User ||--o{ Notification : "receives"
    User ||--o{ AuditLog : "actions"
    User ||--o{ ApprovalRequest : "approves"
    ApprovalRequest }o--|| LeaveRequest : "links"
    ApprovalRequest }o--|| Payroll : "links"
    ApprovalRequest }o--|| SalaryAdvance : "links"

    Material ||--o{ MaterialUsage : "usage_log"
    Material ||--o{ MaterialRequest : "requests"
```

---

## Security Architecture

### Authentication Flow
1. User logs in via email/password or Telegram bot
2. Backend validates credentials, returns JWT (480-minute expiry)
3. Frontend stores JWT in memory (not localStorage)
4. Every API request carries `Authorization: Bearer <jwt>`
5. Middleware validates JWT, resolves User, enforces RBAC

### RBAC Enforcement
- **Backend**: Middleware `get_current_user` + role checks in each router
- **Frontend**: `roles.ts` defines `ROLE_PERMISSIONS` per role; UI elements conditionally rendered
- **Team scoping**: Leaders see only their team's data; data_entry sees only own leads
- **Audit trail**: Every sensitive action logged with before/after snapshots

### Security Headers (applied globally)
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
X-XSS-Protection: 1; mode=block
CSP: default-src 'self'
HSTS: max-age=31536000 (HTTPS only)
```

---

## Deployment Topology

```mermaid
graph LR
    subgraph "Production"
        VERCEL[Vercel<br/>Next.js Frontend]
        RAILWAY[Railway<br/>FastAPI Backend]
        PG[Railway PostgreSQL]
        REDIS_PROD[Upstash Redis]
        TG_BOT[Telegram Bot<br/>Webhook -> Backend]
    end

    subgraph "External"
        GROQ_API[Groq API<br/>LLM Scoring]
        ZALO[Zalo OA<br/>Lead Intake]
    end

    VERCEL -->|HTTPS| RAILWAY
    TG_BOT -->|Webhook| RAILWAY
    RAILWAY --> PG
    RAILWAY --> REDIS_PROD
    RAILWAY --> GROQ_API
    ZALO -->|Webhook| RAILWAY
```
