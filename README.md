# 🏠 JAMA HOME CRM

### ERP + CRM cho công ty thiết kế nội thất

![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)
![SQLite](https://img.shields.io/badge/SQLite-3-blue?logo=sqlite)
![Python](https://img.shields.io/badge/Python-3.11+-yellow?logo=python)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?logo=typescript)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3-38bdf8?logo=tailwindcss)
![License](https://img.shields.io/badge/License-MIT-lightgrey)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen)

---

## 📋 Giới thiệu

**JAMA HOME CRM** là hệ thống ERP/CRM toàn diện với AI Agent, được thiết kế đặc biệt cho **công ty thiết kế nội thất JAMA HOME**. Hệ thống tích hợp quản lý leads, dự án, kế toán, kho vật tư, nhân sự và hợp đồng — tất cả trong một giao diện dark theme chuyên nghiệp.

### 🎯 Điểm nổi bật

- **5 AI Agents** tự động xử lý leads, scoring, và hỗ trợ sales
- **Pipeline Kanban** 5 giai đoạn từ lead mới → ký hợp đồng thiết kế
- **Bảng điều khiển** real-time với KPI, biểu đồ doanh thu, hoa hồng
- **Mobile responsive** — hoạt động tốt trên mọi thiết bị
- **Dark theme** UI hiện đại với search toàn cục (Ctrl+K)

---

## 🛠️ Tech Stack

| Thành phần | Công nghệ |
|-----------|----------|
| **Frontend** | Next.js 16 (App Router) + TypeScript + Tailwind CSS |
| **Backend** | FastAPI (Python 3.11+) + SQLAlchemy 2.0 (async) |
| **Database** | SQLite (file-based, zero-config) |
| **AI Agents** | Lead Intake Agent, Sales Co-Pilot, Lead Scoring, Task Coordinator, Insight Agent |
| **Authentication** | JWT + Role-Based Access Control (RBAC) |
| **Telegram Bot** | aiogram 3.x (tích hợp CRM) |
| **Charts** | Recharts (Dashboard & Reports) |

---

## ✨ Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 🔄 **Pipeline Kanban 5 stages** | new → interested → survey_scheduled → potential → signed_design |
| 🏗️ **Quản lý dự án + Tasks** | Tạo dự án, giao việc, theo dõi tiến độ với Gantt view |
| 💰 **Kế toán** | Thu chi, lương, hoa hồng, biểu đồ tài chính |
| 📄 **Hợp đồng + Báo giá** | Tạo hợp đồng, báo giá với PDF export |
| 📦 **Kho vật tư** | Quản lý tồn kho, xuất nhập, vật tư cho dự án |
| 👥 **Quản lý nhân sự** | 5 vai trò RBAC, quản lý teams, phân quyền chi tiết |
| 🤖 **AI Agents** | Lead Intake Agent, Sales Co-Pilot, Lead Scoring tự động |
| 📱 **Mobile responsive** | Giao diện thích ứng mọi kích thước màn hình |
| 🔍 **Global search** | Tìm kiếm toàn cục với Ctrl+K / Cmd+K |
| 📎 **Google Drive links** | Đính kèm file từ Google Drive cho leads và dự án |
| 🎨 **Dark theme UI** | Giao diện tối hiện đại, chuyên nghiệp |
| 📊 **Dashboard & Reports** | Biểu đồ KPI, báo cáo doanh thu, hiệu suất nhân viên |

---

## 🚀 Quick Start

### Cách 1: Sử dụng start.cmd (Windows) — Khuyến nghị

Tải repo về, sau đó **double-click** file `start.cmd`:

```bash
# Clone
git clone https://github.com/anhthien8/jama-crm.git
cd jama-crm

# Double-click start.cmd
```

### Cách 2: Cài đặt thủ công

```bash
# Clone
git clone https://github.com/anhthien8/jama-crm.git
cd jama-crm

# ── Backend ──
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# ── Frontend (terminal mới) ──
cd frontend
npm install
npm run dev
```

### Truy cập

| Service | URL |
|---------|-----|
| 🖥️ **CRM Web** | [http://localhost:3001](http://localhost:3001) |
| 🔧 **API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| 📡 **API Docs (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) |

> **Lưu ý:** Database SQLite sẽ được tự động tạo và seed dữ liệu demo khi khởi động lần đầu.

---

## 👤 Tài khoản Demo

| Vai trò | Email | Mật khẩu | Quyền hạn |
|---------|-------|-----------|-----------|
| **Admin** | `admin@jamahome.vn` | `admin123` | Toàn quyền — quản lý users, cài đặt hệ thống |
| **Giám đốc** | `ceo@jamahome.vn` | `ceo123` | Xem tất cả — dashboard tổng hợp, báo cáo toàn công ty |
| **Leader Sales** | `leader@jamahome.vn` | `leader123` | Quản lý đội sales + commission override |
| **Nhân viên Sales** | `sales@jamahome.vn` | `sales123` | Leads cá nhân, tạo báo giá, theo dõi dự án |
| **Kế toán** | `accountant@jamahome.vn` | `account123` | Quản lý thu chi, lương, hoa hồng, hợp đồng |

---

## 📂 Cấu trúc dự án

```
jama-crm/
├── backend/                  # FastAPI + SQLite
│   ├── app/
│   │   ├── agents/           # AI agents (Lead Intake, Sales Co-Pilot, etc.)
│   │   ├── api/              # API routes (leads, projects, accounting...)
│   │   ├── models/           # SQLAlchemy models (User, Lead, Project...)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── middleware/        # Auth (JWT) + RBAC middleware
│   │   ├── main.py           # FastAPI app entrypoint
│   │   └── seed.py           # Auto-seed demo data (users, leads, projects)
│   ├── requirements.txt      # Python dependencies
│   └── jama_crm.db          # SQLite database (auto-created)
├── frontend/                 # Next.js 16 + TypeScript
│   ├── src/
│   │   ├── app/              # 12 page routes (leads, projects, accounting...)
│   │   ├── components/       # Reusable UI components
│   │   └── lib/              # API client, auth helpers, roles, demo data
│   ├── package.json
│   └── tailwind.config.ts
├── docs/                     # AI workflow documentation
│   ├── ai-workflow.md        # Chi tiết luồng AI agents
│   └── onboarding-guide.md   # Hướng dẫn onboarding nhân viên mới
├── telegram-bot/             # Telegram bot integration
├── docker-compose.yml        # Docker setup (PostgreSQL + Redis)
├── start.cmd                 # Windows launcher (double-click)
└── README.md                 # Tài liệu dự án
```

---

## 🤖 AI Workflow

JAMA HOME CRM tích hợp **5 AI Agents** hoạt động tự động:

| Agent | Chức năng |
|-------|----------|
| **Lead Intake Agent** | Tự động nhập leads từ Telegram, gắn tag, phân loại |
| **Sales Co-Pilot** | Gợi ý hành động tiếp theo cho nhân viên sales |
| **Lead Scoring Agent** | Chấm điểm leads 0–100 dự trên dữ liệu và hành vi |
| **Task Coordinator Agent** | Tự động tạo tasks từ dự án, phân công nhân viên |
| **Insight Agent** | Phân tích dữ liệu, tạo báo cáo insight hàng tuần |

> 📖 Xem chi tiết tại docs/ai-workflow.md

---

## 🔄 Pipeline Stages

```
🆕 new → 💡 interested → 📋 survey_scheduled → ⭐ potential → ✅ signed_design
```

| Stage | Mô tả |
|-------|-------|
| `new` | Lead mới chưa tiếp xúc |
| `interested` | Khách hàng quan tâm, đã trao đổi |
| `survey_scheduled` | Đã lên lịch khảo sát hiện trường |
| `potential` | Tiềm năng cao, chờ báo giá / hợp đồng |
| `signed_design` | Đã ký hợp đồng thiết kế — chuyển sang dự án |

---

## 💰 Quy tắc hoa hồng

| Loại | Tỷ lệ | Ghi chú |
|------|-------|---------|
| **Thiết kế** | **3%** | Tính trên giá trị hợp đồng thiết kế |
| **Thi công** | **2%** | Tính trên giá trị hợp đồng thi công |
| **Leader override** | **+0.5%** | Leader nhận thêm 0.5% trên doanh số đội |

> Hoa hồng được tự động tính toán bởi AI và hiển thị trong Dashboard & Reports.

---

## 🔐 Phân quyền vai trò (RBAC)

| Chức năng | Admin | Giám đốc | Leader Sales | Sales | Kế toán |
|-----------|:-----:|:-------:|:----------:|:-----:|:------:|
| Quản lý users | ✅ | ❌ | ❌ | ❌ | ❌ |
| Dashboard tổng quan | ✅ | ✅ | ✅ | ❌ | ❌ |
| Leads cá nhân | ❌ | ❌ | ✅ | ✅ | ❌ |
| Leads toàn bộ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Dự án | ✅ | ✅ | ✅ | ✅ | ❌ |
| Hợp đồng + Báo giá | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kế toán (Thu chi) | ✅ | ❌ | ❌ | ❌ | ✅ |
| Lương & Hoa hồng | ✅ | ❌ | ❌ | ❌ | ✅ |
| Kho vật tư | ✅ | ❌ | ❌ | ✅ | ❌ |
| Cài đặt hệ thống | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 🧪 API Endpoints

| Module | Endpoint | Mô tả |
|--------|----------|-------|
| Auth | `POST /api/v1/auth/login` | Đăng nhập, lấy JWT token |
| Leads | `GET/POST /api/v1/leads` | CRUD leads |
| Projects | `GET/POST /api/v1/projects` | CRUD dự án + tasks |
| Accounting | `GET/POST /api/v1/accounting/transactions` | Thu chi, lương |
| Contracts | `GET/POST /api/v1/contracts` | Hợp đồng + báo giá |
| Inventory | `GET/POST /api/v1/inventory` | Quản lý kho vật tư |
| Users | `GET/POST /api/v1/users` | Quản lý nhân sự |
| AI | `POST /api/v1/ai/scoring` | Lead scoring |
| Dashboard | `GET /api/v1/dashboard/stats` | Thống kê tổng quan |

> 📡 Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📜 License

MIT License — xem chi tiết tại [LICENSE](LICENSE).

---

**JAMA HOME CRM** © 2025 — Thiết kế & phát triển bởi [anhthien8](https://github.com/anhthien8)
