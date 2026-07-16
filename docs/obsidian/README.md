# JAMA HOME CRM — Obsidian Documentation

## Navigation

### Architecture
- [[System Architecture]] — Tech stack, module map, RBAC, data flow patterns
- [[ERD]] — Complete entity relationship diagram (34 tables)
- [[Deployment]] — Infrastructure, environment variables, scheduled jobs

### Modules
- [[Lead Management]] — 7-stage CRM pipeline, AI scoring, automation
- [[Approval Engine]] — Multi-step approval, delegation, escalation
- [[Attendance & Leave]] — Check-in/out, OT, leave requests
- [[KPI & Performance]] — 8 metrics, burnout detection, leaderboard
- [[Finance & Accounting]] — Transactions, P&L, commissions, costs
- [[Inventory Management]] — Materials, stock tracking, price items
- [[Projects]] — Project lifecycle, tasks, quotations, contracts
- [[Zalo Listener]] — Message ingestion, signal detection
- [[HR & Payroll]] — Employee profiles, salary grades, payroll generation
- [[Notifications & System]] — Notifications, settings, audit, feedback

### Cross-Module Flows
- [[Lead Pipeline Flow]] — End-to-end lead lifecycle
- [[Approval Flow]] — Universal approval with delegation/escalation
- [[Login Flow]] — Web + Telegram authentication
- [[Payroll Flow]] — Salary computation + approval + payslip
- [[Attendance Flow]] — Daily check-in/out + auto-close + OT
- [[Project Lifecycle Flow]] — Design through completion
- [[Zalo Listener Flow]] — Message ingestion + signal detection
- [[KPI Computation Flow]] — Monthly snapshot + burnout + leaderboard

## Quick Reference

| Concept | Count |
|---------|-------|
| Database tables | 34 |
| User roles | 8 |
| Departments | 5 |
| Lead pipeline stages | 7 |
| Approval types | 5 |
| KPI metrics | 8 |
| Scheduled jobs | 10+ |
| Signal types | 6 |
| Material categories | 10 |

## Tech Stack Summary

- **Frontend**: Next.js 14 (App Router) + React + TailwindCSS + shadcn/ui
- **Backend**: FastAPI + async SQLAlchemy 2.0 + Pydantic
- **Database**: PostgreSQL (prod) / SQLite (dev)
- **Auth**: JWT + bcrypt
- **Deploy**: Vercel (frontend) + Railway (backend + DB)
- **AI**: OpenAI GPT-4o-mini
- **Messaging**: Telegram Bot API + Zalo (via Node.js ingest)

## Tags

#index #readme #jama-home
