# System Architecture — JAMA HOME CRM

## Overview

JAMA HOME CRM is a full-stack enterprise application for a Vietnamese interior design company with ~200 employees across 8 roles. The system manages the complete business lifecycle: lead capture, design quotation, construction project management, HR/payroll, inventory, and financial reporting.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), React, TailwindCSS, shadcn/ui |
| Backend | FastAPI (Python 3.11+), async SQLAlchemy 2.0 |
| Database | PostgreSQL (production), SQLite (development) |
| Auth | JWT (access tokens), bcrypt password hashing |
| Messaging | Telegram Bot API (notifications, approvals, daily briefings) |
| Zalo Integration | Node.js ingest service (zca-js) + REST bridge |
| Deployment | Railway (backend + PostgreSQL), Vercel (frontend) |
| AI | OpenAI GPT-4o-mini (lead scoring, instant quotes) |

## High-Level Architecture Diagram

```mermaid
graph TB
    subgraph Clients["Khách hàng & Nhân viên"]
        Browser["Web Browser<br/>Next.js SPA"]
        TelegramApp["Telegram App"]
        ZaloApp["Zalo App"]
    end

    subgraph Frontend["Frontend — Vercel"]
        NextJS["Next.js 14<br/>App Router + SSR"]
        ReactPages["React Pages<br/>leads, projects, HR, finance..."]
    end

    subgraph Backend["Backend — Railway"]
        FastAPI["FastAPI<br/>REST API"]
        AuthMW["JWT Middleware"]
        Scheduler["APScheduler<br/>Daily Jobs"]
        ApprovalEngine["Approval Engine"]
        KPIEngine["KPI Engine"]
        PayrollEngine["Payroll Engine"]
        Automation["Automation Service<br/>Follow-up, Recall, BOD"]
    end

    subgraph External["Dịch vụ bên ngoài"]
        TelegramBot["Telegram Bot"]
        ZaloIngest["Zalo Ingest Service<br/>Node.js (zca-js)"]
        OpenAI["OpenAI API<br/>GPT-4o-mini"]
    end

    subgraph Data["Data Layer"]
        PostgreSQL["PostgreSQL<br/>AsyncSession"]
        FileStorage["File Storage<br/>Survey photos, documents"]
    end

    Browser -->|"HTTPS"| NextJS
    NextJS -->|"REST API"| FastAPI
    TelegramApp -->|"Bot Commands"| TelegramBot
    TelegramBot -->|"Webhook / Polling"| FastAPI
    ZaloApp -->|"Group Messages"| ZaloIngest
    ZaloIngest -->|"REST Push"| FastAPI

    FastAPI --> AuthMW
    FastAPI --> ApprovalEngine
    FastAPI --> KPIEngine
    FastAPI --> PayrollEngine
    Scheduler --> Automation
    Scheduler --> ApprovalEngine

    FastAPI -->|"SQL"| PostgreSQL
    Automation -->|"Notify"| TelegramBot
    ApprovalEngine -->|"Notify"| TelegramBot
    FastAPI -->|"AI Scoring"| OpenAI

    ReactPages -->|"API Calls"| FastAPI
```

## Module Map

```mermaid
graph LR
    subgraph Core["Core CRM"]
        LeadMgmt["Quản lý Lead<br/>7-stage pipeline"]
        Customer["Khách hàng"]
        Quotation["Báo giá"]
        Contract["Hợp đồng"]
        Project["Dự án & Task"]
    end

    subgraph HR["HR & Operations"]
        Attendance["Chấm công"]
        Leave["Nghỉ phép"]
        Payroll["Bảng lương"]
        KPI["KPI & Performance"]
        HRProfile["Hồ sơ nhân viên"]
    end

    subgraph Finance["Finance"]
        Accounting["Sổ cái kế toán"]
        PL["P&L Report"]
        CostMgmt["Chi phí<br/>Định phí / Biến phí"]
        Commission["Hoa hồng"]
    end

    subgraph Support["Support"]
        Inventory["Quản lý vật tư"]
        Zalo["Zalo Listener"]
        Approval["Phê duyệt"]
        Notification["Thông báo"]
        Audit["Audit Log"]
        Feedback["Phản hồi"]
    end

    LeadMgmt -->|"signed_design"| Project
    LeadMgmt -->|"convert"| Customer
    Quotation -->|"link"| Contract
    Contract -->|"link"| Project
    Project -->|"material usage"| Inventory
    Approval -->|"multi-type"| Leave
    Approval -->|"multi-type"| Payroll
    Attendance -->|"work days"| Payroll
    KPI -->|"metrics"| HRProfile
    Project -->|"transactions"| Accounting
    Commission -->|"period"| Payroll
    Zalo -->|"signals"| LeadMgmt
```

## Role-Based Access Control (RBAC)

```mermaid
graph TB
    Admin["Admin<br/>Toàn quyền hệ thống"]
    Executive["Executive (BOD)<br/>Báo cáo, Dashboard"]
    Leader["Leader<br/>Team management, Approval"]
    DataEntry["Data Entry<br/>Nhập liệu CRM"]
    Accountant["Accountant<br/>Finance, Payroll"]
    Purchasing["Purchasing<br/>Inventory, Pricing"]
    Designer["Designer<br/>Design tasks"]
    PM["Project Manager<br/>Project execution"]

    Admin -->|"manage all"| System["Hệ thống"]
    Executive -->|"view"| Reports["Báo cáo tổng"]
    Leader -->|"approve"| TeamData["Dữ liệu team"]
    DataEntry -->|"CRUD"| CRMData["Lead, Activity"]
    Accountant -->|"manage"| FinanceData["Tài chính, Lương"]
    Purchasing -->|"manage"| InventoryData["Vật tư, Đơn giá"]
    Designer -->|"manage"| DesignData["Task thiết kế"]
    PM -->|"manage"| ProjectData["Dự án, Task"]
```

## Departments

| Code | Department | Vietnamese |
|------|-----------|------------|
| EXEC | Executive | Ban Giám đốc |
| SALES | Sales | Phòng Kinh doanh |
| DESIGN | Design | Phòng Thiết kế |
| PM | Project Management | Phòng Quản lý Dự án |
| ACCT | Accounting | Phòng Kế toán |

## Data Flow Patterns

### Synchronous (Request-Response)
- Web API calls: CRUD operations, search, dashboard queries
- Auth: login, token refresh

### Asynchronous (Event-Driven)
- Approval side-effects: when approval completes, triggers leave/payroll updates
- Notifications: in-app + Telegram push on events
- AI scoring: non-blocking lead scoring on create/update

### Scheduled (Cron Jobs)
- **07:00 VN**: BOD daily report, follow-up reminders, group briefing
- **Midnight VN**: Auto-close open attendance shifts, Zalo message cleanup (>7 days), approval escalation check
- **Monthly**: KPI snapshot generation, payroll period lock

## Key Design Decisions

1. **Approval Engine as shared service**: Single `ApprovalRequest` table handles leave, advance, payroll, expense, and overtime approvals with pluggable side-effects via `register_side_effect()`.
2. **1 record/user/day attendance**: Check-in creates, subsequent check-ins update check-out only. Prevents duplicate records.
3. **KPI uses aggregate SQL**: No per-lead loops for 200+ employees (performance critical).
4. **Zalo Signal vs Message**: Raw messages are temporary (7-day retention), signals are permanent assets.
5. **Delegate approval**: Users can set `delegate_to` + `delegate_until` for approval proxy when absent.
6. **Audit trail**: All sensitive operations (salary, role changes, approvals) logged to `audit_logs`.

## Tags

#architecture #system-design #jama-home
