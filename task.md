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

## 9. Telegram Bot Commands - [ĐÃ HOÀN THÀNH ✅]
- `[x]` `/start` — Auth + welcome
- `[x]` `/lead` — Lead intake from Zalo (AI parse)
- `[x]` `/pipeline` — Pipeline overview
- `[x]` `/briefing` — Daily briefing
- `[x]` `/duan [Mã]` — Quick project lookup
- `[x]` `/baocao [Mã] [Nội dung]` — Site report + photos (FSM)
- `[x]` `/vatlieu [Mã] [Tên] - [SL]` — Material request + inline approve
- `[x]` `/suco [Mã] [Mô tả]` — Incident report + photo evidence
- `[x]` `/checkin [Mã]` / `/checkout [Mã]` — GPS check-in/out
- `[x]` `/cancel` — Clear FSM state

## 10. Unit Tests - [ĐÃ HOÀN THÀNH ✅]
- `[x]` Backend tests for P&L calculation (`backend/tests/test_pl.py` — 16 tests)
- `[x]` Backend tests for lead scoring (`backend/tests/test_lead_scoring.py` — 14 tests)
- `[x]` Backend tests for auth + RBAC (`backend/tests/test_auth_rbac.py` — 18 tests)
- `[x]` Backend tests for Telegram workflow API (`backend/tests/test_telegram_workflow.py` — 16 tests)
- Total: 64 tests, all passing

---

## 11. Tự động hóa CSKH + Báo cáo BOD - [ĐÃ HOÀN THÀNH ✅]
> Theo Brief: "Nhắc cập nhật CSKH mỗi 3-5 ngày, quá hạn thu hồi lead giao sale khác, nhắc hẹn thanh toán, báo cáo gửi tự động cho BOD hàng ngày/tuần/tháng"

- `[x]` **Models:** `Notification` (in-app notification + dedupe) và `SystemSetting` (key-value settings) — `backend/app/models/notification.py`
- `[x]` **Services** (`backend/app/services/`):
  - `automation.py` — nhắc follow-up (3 ngày), thu hồi lead quá hạn (7 ngày, giao sale ít việc nhất cùng team), nhắc thanh toán đợt pending
  - `bod_report.py` — báo cáo ngày/tuần/tháng (leads, doanh thu, top sales, AI insight) gửi admin/executive
  - `telegram_notify.py` — push Telegram từ backend (no-op nếu chưa cấu hình token)
- `[x]` **API mới:**
  - `GET /notifications`, `PUT /notifications/{id}/read`, `PUT /notifications/read-all`
  - `GET|PUT /automation/settings` (admin/executive)
  - `POST /automation/run/{followups|recall|payments|all}` — trigger thủ công
  - `POST /automation/run/bod-report/{period}`, `GET /automation/bod-report/{period}/preview`
- `[x]` **Worker scheduler:** automation chạy 07:00 VN hàng ngày; báo cáo BOD 08:00 (cấu hình được) — ngày luôn gửi, tuần vào thứ Hai, tháng vào mùng 1
- `[x]` **Frontend:**
  - `NotificationCenter` lấy thông báo thật từ backend (poll 60s, work mode), mark read đồng bộ server
  - Trang Settings: mục "Tự động hóa CSKH & Báo cáo" cho admin/executive (chỉnh ngưỡng ngày, bật/tắt, chạy ngay, gửi báo cáo test)
  - API client: notifications + automation methods
- `[x]` **Tests:** `backend/tests/test_automation.py` — ~28 tests (follow-up, recall, payment, settings API, BOD report, notifications API)
- `[x]` TypeScript type-check pass (tsc --noEmit, exit 0)

---

## 12. Cấu hình AI tập trung + Nhóm Telegram công ty - [ĐÃ HOÀN THÀNH ✅]
- `[x]` **LLM config service** (`backend/app/services/llm_config.py`):
  - Admin cấu hình model chính (free) + model fallback + API keys, lưu `system_settings`, cache 60s, áp dụng ngay không cần restart
  - `llm_complete()`: model chính lỗi → fallback model → raise (agent dùng rule-based)
  - Presets model free: Groq, Gemini, OpenRouter, Ollama
- `[x]` **Refactor 5 AI agents** dùng `llm_complete`/`llm_available` trung tâm (lead_intake, sales_copilot, lead_scoring, insight_agent, task_coordinator)
- `[x]` **API `/ai-settings`** (admin only): GET (key được mask), PUT, POST /test (test kết nối model)
- `[x]` **Nhóm Telegram công ty:**
  - Setting `telegram_group_chat_id` + `group_briefing_enabled`
  - `send_group_briefing()` — briefing sáng vào nhóm (KHÔNG kèm số liệu tài chính)
  - Worker gửi briefing nhóm cùng giờ báo cáo BOD
  - Bot: lệnh `/id` (lấy Chat ID), tự chào khi được thêm vào nhóm
  - Fix bảo mật: auto-parse lead chỉ hoạt động trong chat riêng (không đọc nhóm)
- `[x]` **Frontend Settings:** mục "🧠 Cấu hình AI Model" (admin) + ô Chat ID nhóm + nút test/gửi briefing
- `[x]` **Docs:** `docs/HUONG_DAN_TELEGRAM_NHOM.md` — hướng dẫn 5 phần cài đặt nhóm công ty
- `[x]` Verify: python syntax pass toàn bộ, tsc --noEmit pass

---

## 13. Sao lưu tự động (Local + Google Drive) - [ĐÃ HOÀN THÀNH ✅]
- `[x]` **Backup service** (`backend/app/services/backup_service.py`):
  - Snapshot SQLite an toàn (sqlite3 backup API) → zip kèm metadata vào `backend/backups/`
  - Retention: tự xóa bản cũ hơn N ngày (mặc định 180, **tối đa 180**) — cả local và Drive
  - Google Drive OAuth 2.0: authorization code flow, lưu refresh_token, tự tạo thư mục JAMA-CRM-Backups, upload multipart, dọn file cũ trên Drive
  - PostgreSQL → skip kèm hướng dẫn pg_dump
- `[x]` **API `/backup`** (admin only): GET/PUT settings, POST /run (sao lưu ngay), OAuth flow (auth-url → callback với state token → disconnect)
- `[x]` **Worker:** backup hàng ngày lúc **5h sáng VN** (giờ chỉnh được, bật/tắt được)
- `[x]` **Frontend Settings** (admin): section 💾 — toggle + giờ + retention, kết nối/ngắt Google Drive, form OAuth Client, danh sách 10 bản backup gần nhất, nút Sao lưu ngay
- `[x]` `.gitignore` thêm `backend/backups/`
- `[x]` **Tests:** `backend/tests/test_backup.py` — ~17 tests (settings clamp, snapshot zip, retention cleanup, RBAC, OAuth state, run flow)
- `[x]` Docs: cập nhật mục Backup trong `huong-dan-it.html`
- `[x]` Verify: python syntax pass, tsc --noEmit pass

---

## 14. QC Bảo mật - [ĐÃ HOÀN THÀNH ✅]
- `[x]` **Vá Critical:** `/auth/telegram` yêu cầu bí mật chia sẻ `TELEGRAM_AUTH_SECRET` (header X-Telegram-Bot-Secret, hmac.compare_digest) — chặn mạo danh nhân viên qua telegram_user_id
- `[x]` **Vá High:** chặn JWT secret yếu/placeholder (<32 ký tự → từ chối khởi động); create_user bỏ default password, bắt buộc ≥8 ký tự + validate role/email; security headers middleware (nosniff, X-Frame-Options, HSTS...)
- `[x]` Rate-limit `/auth/telegram` khi chưa có secret; VALID_ROLES cho update_user
- `[x]` Báo cáo đầy đủ: `docs/SECURITY_QC.md` (1 Critical + 3 High đã vá, 2 Medium theo dõi, checklist production)
- ⚠️ Deploy cần đặt `TELEGRAM_AUTH_SECRET` giống nhau ở backend + telegram-bot

---

## 15. Báo giá sơ bộ tức thì (Instant Quote) - [ĐÃ HOÀN THÀNH ✅]
> Sale phản hồi "khoảng bao nhiêu tiền?" trong 30 giây thay vì 3-7 ngày — nâng tỷ lệ chốt + bảo vệ margin

- `[x]` **Price book** (`backend/app/models/pricing.py`): 28 hạng mục × 3 phân khúc (Cơ bản/Tiêu chuẩn/Cao cấp), seed đơn giá tham khảo HCM — **Thu mua phải rà lại trước khi dùng thật**
- `[x]` **Engine** (`backend/app/services/instant_quote.py`): template hạng mục theo loại nhà (căn hộ/nhà phố/villa/văn phòng), công thức qty = base + hệ_số×m² + hệ_số×PN, villa ×1.25, khoảng giá ±15%, gợi ý phương án theo ngân sách khách, format text Zalo
- `[x]` **API:**
  - `POST /instant-quote/generate` (sale) — nhập số liệu hoặc paste text Zalo (AI parse + regex fallback)
  - `POST /instant-quote/public` (không auth, rate-limit 5 lần/giờ/IP) — mini-app khách tự báo giá → **tự tạo lead nóng** (source=website, priority=high, chống trùng SĐT), chỉ trả khoảng giá không lộ đơn giá chi tiết
  - CRUD `/instant-quote/price-items` — admin/purchasing sửa giá, mọi user xem
- `[x]` **Frontend:**
  - `/quote-tool` (sale/leader, có trong sidebar): 2 chế độ nhập, 3 card phương án, bảng chi tiết, nút Copy text Zalo, bảng đơn giá sửa inline cho Thu mua
  - `/bao-gia` (public, không login): landing lead magnet cho khách tự nhập → nhận khoảng giá + CTA khảo sát miễn phí
- `[x]` **Tests:** `backend/tests/test_instant_quote.py` — ~24 tests (engine math, tiers tăng dần, template theo loại nhà, public tạo lead + chống trùng, RBAC price book)
- `[x]` Verify: sanity check giá (căn hộ 75m² ≈ 184/338/702tr — hợp lý thị trường), tsc pass

---

## 17b. Báo giá Cải tạo — Dual mode engine - [ĐÃ HOÀN THÀNH ✅]
> Theo file `JAMA_ baogiaphantho.xlsx` — báo giá cải tạo nhà phố 3 tầng

### Engine (backend)
- `[x]` **Renovation template** (`services/instant_quote.py`): ~100+ hạng mục, 7 nhóm (Tháo dỡ / Kết cấu / Hoàn thiện / Cửa / Cầu thang / M&E / Khác)
- `[x]` **Floor-aware generation**: lọc items theo số tầng (1-4), items T2/T3/mái chỉ xuất hiện khi đủ tầng
- `[x]` **Material options** cho budget fitting: Sàn (gạch→gỗ), Cửa (HDF→gỗ tự nhiên), WC (Inax→TOTO→AS), Sơn (Dulux→Jotun)
- `[x]` Sanity: 80m² × 1T = 327tr, × 2T = 501tr, × 3T = 723tr — hợp lý

### API
- `[x]` `QuoteRequest` + `PublicQuoteRequest` thêm `mode: "new" | "renovation"`, `floors: 1-4`
- `[x]` `POST /instant-quote/generate` route renovation → `generate_renovation_quote()`
- `[x]` `POST /instant-quote/public` hỗ trợ renovation mode + tạo lead

### Zalo text
- `[x]` `format_renovation_quote_for_zalo()` — text thân thiện với gợi ý vật liệu theo budget

### Verify
- `[x]` 136 backend tests passing
- `[x]` TypeScript --noEmit clean

## 16. Triển khai Báo giá (deploy + đơn giá + nhúng web) - [ĐÃ CHUẨN BỊ ✅]
- `[x]` **Template Excel đơn giá** cho Thu mua: `docs/JAMA_Bang_Don_Gia_Noi_That.xlsx` — 28 hạng mục × 3 phân khúc, cột giá tham khảo (khóa) + giá thật (điền), cột chênh lệch % có công thức, sheet hướng dẫn. 0 lỗi công thức.
- `[x]` **Nhúng trang Dự Toán** (`deploy/embed/`):
  - `jama-bao-gia-widget.html` — widget native độc lập gọi API public, chỉ sửa 1 dòng API_BASE, dán vào Custom HTML. JS verified.
  - `README-nhung-trang-du-toan.md` — hướng dẫn iframe (nhanh) vs widget native (đẹp), cấu hình CORS, checklist test.
- ⏳ **Cần user:** (1) push code + deploy Railway, (2) Thu mua điền giá thật vào Excel rồi nhập app, (3) chọn cách nhúng + điền domain

---

## 17. Feedback ERP 0907 — Fix bugs + Lead fields - [ĐÃ HOÀN THÀNH ✅]
> Theo file Feedback ERP 0907 (Google Slides): 6 yêu cầu từ business

### Bugs (Slide 5)
- `[x]` **Fix task ordering:** Demo mode resolver (`api.ts:128`) giờ sort tasks theo `order` field. Thêm demo handler cho PUT task status.
- `[x]` **Fix missing tasks:** Auto-create 19 tasks khi lead chuyển `signed_design` giờ có error handling per-task — nếu 1 task fail thì project + các task khác vẫn tạo thành công, log warning.

### Lead fields mới (Slide 2 + Slide 4)
- `[x]` **`channel`** (Kênh phân bổ): `kenh_a`, `kenh_b`, `kenh_chinh`, `kenh_sale`, `kenh_affiliate`, `khac` — phân biệt với `source` (platform)
- `[x]` **`contact_status`**: `reachable`, `unreachable`, `wrong_number`, `no_need`, `pending`
- `[x]` **`survey_date`**: DateTime — ngày khảo sát thực tế
- `[x]` **`survey_photos`**: Text (JSON array URLs) — ảnh xác minh khảo sát
- `[x]` Updated model, schema (LeadCreate/LeadUpdate/LeadResponse), API helper, frontend Lead type

### Pipeline stages (Slide 4)
- `[x]` Cập nhật `STAGE_LABELS` cho khớp flow business:
  - new → "Tiếp nhận mới"
  - interested → "Đang tư vấn"
  - survey_scheduled → "Khảo sát"
  - potential → "Dự toán & tư vấn"
  - signed_design → "Ký HĐ Thiết kế"

### Verify
- `[x]` 136 backend tests passing
- `[x]` TypeScript --noEmit clean

---

## 18. QC/QA Audit — Feedback ERP 0907 - [ĐÃ HOÀN THÀNH ✅]

### Critical fixes
- `[x]` `create_lead` endpoint giờ pass đầy đủ new fields (channel, contact_status, survey_date, survey_photos, property_class, price_per_sqm, region, segment, plan_type, tags, deal_value)
- `[x]` Project code generation loop giờ có max 100 iterations guard (tránh infinite loop)
- `[x]` Customer detail endpoint thêm RBAC check (admin/executive/leader/accountant/data_entry/pm)

### High fixes
- `[x]` `Project` interface frontend thêm `customer_id`
- `[x]` `survey_photos` type sửa thành `string[]`
- `[x]` Customer demo route `GET /customers/{id}` — enriches with linked projects
- `[x]` Inline import `or_` trong customers.py moved to top

### Seed data
- `[x]` Lead seed đầu tiên (`Bong`) có thêm `channel="kenh_sale"` + `contact_status="reachable"`

### Verify
- `[x]` 136 backend tests passing
- `[x]` TypeScript --noEmit clean

---

## 19. Báo giá Cải tạo — Full stack - [ĐÃ HOÀN THÀNH ✅]
> Theo file `JAMA_ baogiaphantho.xlsx` — dual mode engine + frontend

### Backend engine
- `[x]` Renovation template: ~100+ hạng mục, 7 nhóm (Tháo dỡ/Kết cấu/Hoàn thiện/Cửa/CT/M&E/Khác)
- `[x]` Floor-aware generation: lọc items theo số tầng (1-4), sanity check giá
- `[x]` Material options cho budget fitting: Sàn/Cửa/WC/Sơn
- `[x]` API: mode "new"|"renovation" + floors param trên cả 2 endpoint

### Frontend `/quote-tool`
- `[x]` Mode toggle: 🏗️ Xây mới / 🔨 Cải tạo
- `[x]` Cải tạo: input diện tích/tầng, selector số tầng, kết quả theo nhóm + gợi ý vật liệu
- `[x]` Xây mới: giữ nguyên 3 tier cards + detail table
- `[x]` Copy Zalo text cả 2 mode

### Verify
- `[x]` 136 backend tests passing
- `[x]` TypeScript --noEmit clean
