# JAMA CRM — Quick Reference Card

> Tóm tắt nhanh cho Claude Desktop

---

## 🚀 Start Commands

```bash
# Backend
cd H:/Hermes/jama-crm/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (Production)
cd H:/Hermes/jama-crm/frontend
npm run build && npx next start -p 3004

# Frontend (Dev)
cd H:/Hermes/jama-crm/frontend
npm run dev
```

## 🔑 Quick Login

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@jamahome.vn | admin123 |
| CEO | ceo@jamahome.vn | ceo123 |
| KT | accountant@jamahome.vn | account123 |
| Leader | leader@jamahome.vn | leader123 |
| Sales | sales@jamahome.vn | sales123 |
| Designer | designer@jamahome.vn | designer123 |
| PM | pm@jamahome.vn | pm123 |
| Thu mua | purchasing@jamahome.vn | purchase123 |

## 📂 Key Files

| File | Purpose |
|------|---------|
| `frontend/src/lib/roles.ts` | RBAC permissions |
| `frontend/src/lib/api.ts` | API client + demo data resolver |
| `frontend/src/lib/auth.tsx` | Auth context + demo users |
| `frontend/src/lib/demo-data.ts` | Mock data for demo mode |
| `backend/app/main.py` | FastAPI entry point |
| `backend/app/seed.py` | Database seeder |
| `backend/app/api/*.py` | API endpoints |

## 🔧 Common Fixes

### Dashboard crash
Check `frontend/src/app/page.tsx` — ensure `data?.overdue_leads ?? 0` pattern

### P&L crash
Check `frontend/src/app/pl/page.tsx` — ensure `(summary.margin ?? 0).toFixed(1)` pattern

### Demo mode issues
Check `frontend/src/lib/api.ts` — ensure demo resolver exists for the endpoint

### RBAC issues
Check `frontend/src/lib/roles.ts` — ensure permission exists for the role
Check `backend/app/api/*.py` — ensure backend role check exists

## 📊 Pages (13 total)

| Page | Route | RBAC |
|------|-------|------|
| Dashboard | `/` | All |
| Pipeline | `/leads` | Sales only |
| Projects | `/projects` | All (scoped) |
| Customers | `/customers` | Most roles |
| Contracts | `/contracts` | Most roles |
| Quotations | `/quotations` | Sales, Designer, PM |
| Inventory | `/inventory` | Admin, Purchasing, Accountant |
| Accounting | `/accounting` | Admin, Accountant, Leader |
| HR | `/hr` | Admin, Accountant |
| P&L | `/pl` | C-level only |
| Reports | `/reports` | Most roles |
| Settings | `/settings` | All |
| Login | `/login` | Public |

## 🐛 Current Known Issues

1. Dashboard always fetches executive data
2. No Alembic migrations
3. JWT secret hardcoded
4. No test files
5. SearchModal uses hardcoded data

## 📋 Next: Module Finance

See `docs/FINANCE_MODULE_PLAN.md` for full plan.
