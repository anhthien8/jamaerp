# JAMA CRM — Session Handover (Full)

> Phiên làm việc từ 29/06/2026 - 30/06/2026
> Tiếp tục trên Claude Desktop

---

## 📌 Mục tiêu tổng thể

Hoàn thiện webapp JAMA HOME ERP/CRM cho công ty nội thất JAMA HOME có thể sử dụng được với 2 chế độ:
- **Demo Mode**: Show cho nhân sự cách sử dụng CRM
- **Work Mode**: Chế độ làm việc thực tế

---

## ✅ Đã hoàn thành

### Session 1: Core Features
- [x] Fix seed data undefined variables
- [x] Fix demo credentials mismatch
- [x] Demo/Work Mode toggle (login + sidebar)
- [x] 8 RBAC roles: admin, executive, accountant, leader, data_entry, designer, pm, purchasing
- [x] P&L Module (C-level only)
- [x] Pipeline Blueprint v2.0 (19 tasks/project)
- [x] Database indexing (12 composite indexes)
- [x] Pagination (10 endpoints)
- [x] In-memory caching

### Session 2: Security & UX
- [x] Backend RBAC: projects, customers, accounting, inventory
- [x] Frontend RBAC: sidebar filtering, page guards
- [x] Error states on all pages
- [x] Mobile responsive card views
- [x] Vietnamese diacritics fix
- [x] Focus-visible styles

### Session 3: Features & CRUD
- [x] Designer RBAC (can view projects, create/edit tasks)
- [x] PM CRUD (create/edit projects, create tasks with assignee)
- [x] Contract CRUD (Sales + PM roles)
- [x] Quotation CRUD (Designer + PM roles)
- [x] Task file upload (multi-file, images/PDF/DWG/SKP)
- [x] Material request from PM
- [x] Lost reason tracking (5 reasons + custom)
- [x] Daily follow-up dashboard
- [x] CSV export for accounting
- [x] Receivables aging
- [x] HR: Add employee + Nghỉ việc feature
- [x] Mode banner (Demo/Work indicator)
- [x] Search on Pipeline
- [x] Overdue indicators on Kanban cards
- [x] Quick activity button with toast feedback
- [x] Date range filter for accounting
- [x] Period selector (Month/Quarter/Year)

### Session 4: QC & Diagrams
- [x] 3 rounds of QC (backend + frontend + comprehensive)
- [x] 6 System diagrams generated
- [x] All crash bugs fixed
- [x] All type errors fixed
- [x] All demo mode issues fixed

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4 |
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.0 async |
| Database | SQLite (dev), PostgreSQL (Docker) |
| Auth | JWT (python-jose), bcrypt |
| AI | LiteLLM (Groq, Ollama fallback) |
| Telegram | aiogram 3.13 |
| Cache | In-memory with TTL |
| Deployment | Railway (production) |

---

## 📂 Project Structure

```
jama-crm/
├── backend/
│   ├── app/
│   │   ├── api/          # 11 API routers
│   │   ├── models/       # 15 SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── middleware/    # auth.py, rbac.py
│   │   ├── agents/       # AI agents (lead_intake, sales_copilot)
│   │   ├── cache.py      # In-memory cache
│   │   ├── config.py     # Settings
│   │   ├── database.py   # Async SQLAlchemy
│   │   ├── main.py       # FastAPI entry
│   │   └── seed.py       # Demo data seeder
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/          # 13 pages (App Router)
│       ├── components/   # Sidebar, SearchModal, etc.
│       └── lib/          # api.ts, auth.tsx, roles.ts, demo-data.ts
├── telegram-bot/
├── docs/
│   ├── Brief_ERP_JAMA_HOME.txt
│   ├── Phan_Quyen_ERP_JAMA_HOME.txt
│   ├── LightningLabs_ERP_Training.txt
│   ├── SESSION_HANDOVER.md  ← THIS FILE
│   └── ... (JD files, Excel)
├── docker-compose.yml
└── start.cmd
```

---

## 📊 RBAC Matrix

| Feature | Admin | Leader | Sales | Designer | PM | Accountant | Purchasing |
|---------|-------|--------|-------|----------|-----|------------|------------|
| Dashboard | FULL | FULL | FULL | FULL | FULL | FULL | FULL |
| Leads | FULL | SCOPE | SCOPE | — | — | — | — |
| Projects | CRUD | CRU | R | R(own) | CRUD | R | R |
| Tasks | CRUD | CRU | R | RU(own) | CRUD | R | R |
| Contracts | CRUD | CRU | CRUD | R | CRUD | CRUD | R |
| Quotations | CRUD | CRUD | CRUD | CRUD | CRUD | R | — |
| Inventory | CRUD | R | — | — | R | R | CRUD |
| Accounting | CRUD | R | — | — | — | CRUD | — |
| Customers | CRUD | CRUD | CRUD | R | R | CRUD | — |
| P&L | FULL | — | — | — | — | FULL | — |
| HR | FULL | READ | — | — | — | FULL | — |

---

## 🔑 Demo Accounts

| Email | Password | Role |
|-------|----------|------|
| admin@jamahome.vn | admin123 | Giám đốc |
| ceo@jamahome.vn | ceo123 | Ban Quản Trị |
| accountant@jamahome.vn | account123 | Kế toán |
| leader@jamahome.vn | leader123 | Trưởng phòng |
| sales@jamahome.vn | sales123 | Nhân viên Sale |
| designer@jamahome.vn | designer123 | Nhân viên Thiết kế |
| pm@jamahome.vn | pm123 | Trưởng Dự án |
| purchasing@jamahome.vn | purchase123 | Thu mua |

---

## 🐛 Known Issues (cần fix)

| # | Issue | Severity |
|---|-------|----------|
| 1 | Dashboard always fetches executive data (chưa phân role) | Low |
| 2 | No Alembic migrations (dùng create_all) | Medium |
| 3 | JWT secret hardcoded trong config | Medium |
| 4 | No test files | Medium |
| 5 | SearchModal dùng hardcoded demo data | Low |

---

## 📋 Next Steps (Phase tiếp theo)

### Module Finance (Ưu tiên cao)
1. **Nhân sự** — HĐ lao động, Bậc lương, Onboard/Offboard
2. **Lương thưởng** — Gross → BHXH → BHYT → BHTN → PIT → NET
3. **Bảng lương** — Payslip, phân bổ NV theo bậc
4. **Hoa hồng** — Tự động theo dự án, milestone, tỷ lệ phòng ban
5. **Chi phí Định phí** — Tiền nhà, điện nước (cập nhật hàng tháng)
6. **Chi phí Biến phí** — Theo dự án, theo tháng

### Pipeline Enhancements
7. Construction team/role
8. Purchase Order workflow
9. Supplier management
10. Daily site reports

### Advanced Features
11. Client portal
12. Gantt chart
13. Change order management
14. Bank reconciliation

---

## 📊 System Diagrams

### Architecture
```
Frontend (Next.js) ↔ Backend (FastAPI) ↔ DB (SQLite/PostgreSQL)
     ↕                                        ↕
  Demo Mode                              Telegram Bot
  (localStorage)                         AI Agents
```

### Lead Pipeline (7 stages)
```
new → interested → survey_scheduled → potential → signed_design
                                            ↓
                                      AUTO-CONVERT
                                      → Customer + Project + 19 Tasks
```

### Project Pipeline (6 stages, 19 tasks)
```
Design(5) → Quotation(4) → Procurement(3) → Construction(4) → Acceptance(3) → Completed
```

---

## 🚀 How to Run

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev  # Development
npm run build && npx next start -p 3004  # Production

# Docker
docker-compose up
```

**Production URL**: https://jamacrm-production.up.railway.app

---

## 📝 Notes for Claude Desktop

- Khi chạy trên Claude Desktop, có thể cần set environment variable `APP_ENV=development`
- Frontend chạy trên port 3004 (production build)
- Backend chạy trên port 8000
- Database SQLite tự tạo khi startup (auto-seed demo data)
- Nếu cần reset data: xóa file `backend/jama.db` và restart backend

---

*Last updated: 30/06/2026*
