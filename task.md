# Checklist triển khai JAMA CRM

## 1. Database & Backend API (Dự án & Phân quyền) - [ĐÃ HOÀN THÀNH ✅]
- `[x]` Cập nhật `Project` và `Task` models trong `backend/app/models/project.py`
  - Thêm `stage` vào `Project`
  - Thêm `stage` và `final_file_url` vào `Task`
  - Tạo model `TaskActivity` cho ghi chú & media
- `[x]` Thêm check phân quyền trong `backend/app/api/inventory.py` cho `admin` và `purchasing`
- `[x]` Cập nhật API `change_stage` trong `backend/app/api/leads.py` để tự động tạo Dự án + 19 Tasks khi lead chuyển sang `signed_design`
- `[x]` Bổ sung các endpoint dự án mới trong `backend/app/api/projects.py`:
  - `GET /projects/pipeline/kanban`
  - `PUT /projects/{project_id}/stage`
  - `GET /projects/tasks/{task_id}/activities`
  - `POST /projects/tasks/{task_id}/activities`
  - `PUT /projects/tasks/{task_id}/final-file`
  - `PUT /projects/tasks/{task_id}/status`

## 2. Seed Data (Dự án & Phân quyền) - [ĐÃ HOÀN THÀNH ✅]
- `[x]` Cập nhật file seed `backend/app/seed.py` để cập nhật cấu trúc database mới (thêm `stage` cho project/task, thêm user role `purchasing`)

## 3. Frontend Integration (Dự án & Phân quyền) - [ĐÃ HOÀN THÀNH ✅]
- `[x]` Cập nhật `frontend/src/lib/roles.ts` định nghĩa role `purchasing` và phân quyền Kho vật tư
- `[x]` Bổ sung API client calls cho dự án/task trong `frontend/src/lib/api.ts`
- `[x]` Cải tiến giao diện `frontend/src/app/projects/page.tsx`:
  - Thêm View Toggle (List/Kanban)
  - Hiển thị Kanban Board 5 giai đoạn dự án
  - Group tasks theo giai đoạn trong Project Detail Modal
  - Thiết kế Task Detail Modal với upload Final File, đổi Status và dòng lịch sử ghi chú & media

## 4. Verification & Deployment (Dự án & Phân quyền) - [ĐÃ HOÀN THÀNH ✅]
- `[x]` Chạy thử local & kiểm tra lỗi build
- `[x]` Commit, push và deploy lên Railway
- `[x]` Kiểm tra hoạt động thực tế trên production

---

## 5. Module P&L (KISS) - [ĐÃ HOÀN THÀNH ✅]
- `[x]` **Backend P&L API:**
  - `[x]` API tính P&L từng dự án `GET /pl/projects/{project_id}`
  - `[x]` API P&L tổng quan `GET /pl/summary`
  - `[x]` API danh sách P&L dự án `GET /pl/projects`
- `[x]` **Frontend P&L UI:**
  - `[x]` Trang `/pl` với summary cards + per-project table + mobile view
  - `[x]` Phân quyền C-level only (admin/executive/accountant)
  - `[x]` Date filtering (month/quarter/year/custom)
  - `[x]` Sort by revenue/profit/margin

---

## 6. AI Agents (5/5) - [ĐÃ HOÀN THÀNH ✅]
- `[x]` Lead Intake Agent (`backend/app/agents/lead_intake.py`) — LLM + regex fallback
- `[x]` Sales Co-Pilot Agent (`backend/app/agents/sales_copilot.py`) — LLM + rule-based fallback
- `[x]` Lead Scoring Agent (`backend/app/agents/lead_scoring.py`) — LLM + rule-based scoring 0-100
- `[x]` Task Coordinator Agent (`backend/app/agents/task_coordinator.py`) — 19 tasks blueprint + LLM enrichment
- `[x]` Insight Agent (`backend/app/agents/insight_agent.py`) — weekly insights + LLM narrative

## 7. Background Worker - [ĐÃ HOÀN THÀNH ✅]
- `[x]` `backend/app/worker.py` — asyncio queue, periodic lead scoring, insight generation
- `[x]` Graceful shutdown (SIGTERM/SIGINT)
- `[x]` Health check endpoint support

## 8. Telegram Workflow API - [ĐÃ HOÀN THÀNH ✅]
- `[x]` `GET /telegram/project/{project_code}` — Quick project lookup
- `[x]` `POST /telegram/site-report` — Site report with photos (/baocao)
- `[x]` `POST /telegram/material-request` — Material request (/vatlieu)
- `[x]` `POST /telegram/incident` — Incident report (/suco)
- `[x]` `POST /telegram/checkin` — GPS check-in
- `[x]` `POST /telegram/checkout` — GPS check-out
- `[x]` `POST /telegram/approve/{id}` — Approve material (inline button)
- `[x]` `POST /telegram/reject/{id}` — Reject material (inline button)
- `[x]` `MaterialRequest` model for approval workflow
- `[x]` Router registered in `main.py`

## 9. Telegram Bot Commands - [CẦN HOÀN THÀNH ⏳]
- `[x]` `/start` — Auth + welcome
- `[x]` `/lead` — Lead intake from Zalo
- `[x]` `/pipeline` — Pipeline overview
- `[x]` `/briefing` — Daily briefing
- `[ ]` `/duan [Mã]` — Quick project lookup
- `[ ]` `/baocao [Mã] [Nội dung]` — Site report + photos
- `[ ]` `/vatlieu [Mã] [Tên] - [SL]` — Material request
- `[ ]` `/suco [Mã] [Mô tả]` — Incident report
- `[ ]` `/checkin` / `/checkout` — GPS check-in/out

## 10. Unit Tests - [CẦN HOÀN THÀNH ⏳]
- `[ ]` Backend tests for P&L calculation
- `[ ]` Backend tests for lead scoring
- `[ ]` Backend tests for auth + RBAC
- `[ ]` Backend tests for Telegram workflow API
