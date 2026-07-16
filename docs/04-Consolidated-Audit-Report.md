# Báo cáo Audit Hợp nhất — JAMA HOME CRM/ERP

> **Ngày:** 16/07/2026 · **Tổng hợp từ:** 4 tài liệu audit (`00-System-Architecture`, `01-Whitelabel-Strategy`, `02-Role-Permission-Matrix`, `03-Module-Dependency-Map`) + `qa/QA-2026-07-15.md` + bộ spec `specs/00-07`
> **Người tổng hợp:** Claude (tiếp quản từ phiên Opus 4.8 bị gián đoạn burst limit 16/07)

---

## 1. Kết luận điều hành (đọc 1 phút)

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| **Chất lượng code** | 🟢 Tốt | 329/329 tests pass, tsc clean, production build OK (QA 15/07) |
| **Bảo mật RBAC** | 🟢 Đã vá | 3 lỗ hổng (1 High, 2 Medium) phát hiện qua QA per-role → đã fix + 133 case RBAC tự động chạy mãi |
| **Kiến trúc** | 🟢 Sẵn sàng scale | 27 router độc lập, config-driven, Postgres + Alembic, cache layer — nền tốt cho 200 users (spec 05 còn phải chạy) |
| **Whitelabel** | 🟡 Khả thi, cần quyết | Phase 1 (branding + feature toggle) ước lượng thấp; quyết định trước 15/08 (doc 01) |
| **Deploy production** | 🟡 Đang hoàn thiện | Railway (backend+bot unified Dockerfile) + Vercel (frontend); health check cuối chưa xác nhận được do outage công cụ — xem mục 5 |
| **Nợ tồn đọng** | 🟠 Có kiểm soát | Danh sách mục 4 |

## 2. Điểm mạnh hệ thống (từ doc 00 + 03)

1. **Modular thật sự**: 27 router tách rời, dependency map rõ (doc 03) — Core (Auth/Users/Teams) là gốc duy nhất; các module HR (attendance/leaves/approvals/payroll) ghép qua approval engine dùng chung → tắt/bật per-tenant khả thi.
2. **Config-driven**: SystemSetting key-value cho automation, AI model, PIT/BHXH, ngưỡng ưu tiên dự án — đổi hành vi không cần deploy.
3. **Đa kênh nhất quán**: Web + Telegram bot dùng chung backend, quy tắc bảo mật thống nhất (tài chính chỉ chat riêng).
4. **QA gate vĩnh viễn**: quy trình per-role (spec 06) đã chạy pass đầu tiên và bắt được lỗ hổng thật ngay lần đầu — chứng minh giá trị.

## 3. Ma trận quyền (từ doc 02) — điểm cần lưu ý

- 8 role khớp giữa `roles.ts` (frontend) và guard backend sau đợt vá 15/07.
- ⚠️ Doc 02 ghi nhận `canViewAccounting: true` cho `data_entry` — **cần chủ dự án xác nhận** đây là chủ đích (sale xem sổ thu chi?) hay siết lại.
- Ngữ nghĩa đặc biệt cần giữ khi refactor: `/leads` trả danh sách RỖNG (không 403) cho role ngoài khối sales — đã có test khóa hành vi.

## 4. Nợ tồn đọng & việc kế tiếp (ưu tiên từ trên xuống)

1. **Xác nhận deploy end-to-end** (mục 5) + smoke login trên production.
2. **Spec 05 — scale 200 users**: chưa thực thi. Ưu tiên Track A (ảnh công trình → nhóm Telegram, quyết định chốt của chủ dự án) + Track B (6 điểm N+1 đã định vị).
3. **Whitelabel Phase 1** (doc 01): chờ chủ dự án quyết trước 15/08 — nếu làm: TenantConfig table + CSS variables + feature toggles (đã liệt kê đủ 13 module toggle key).
4. QA còn treo 4 mục "cần infra/browser": bot runtime, mobile 390px, demo-mode network, login per role trên browser thật.
5. Bất biến QA #6 (UI thuần Việt): doc 02 còn label không dấu trong bảng (docs nội bộ — chấp nhận), UI runtime đã sạch sau đợt Việt hóa.
6. Đồng bộ tài liệu: `Phan_Quyen_ERP_JAMA_HOME.txt` (06/04) đã lỗi thời so với doc 02 — dùng doc 02 làm source of truth mới.

## 5. Trạng thái deploy (thời điểm 16/07 ~05:30 VN)

- Commits deploy đã lên `main`: unified Dockerfile backend+bot, health server bot, seed prod DB lần đầu, skip migrate trong lifespan production (migrate chạy qua `start.sh db_upgrade` trước uvicorn).
- ⏳ **Health check cuối cùng CHƯA xác nhận** — cả phiên Opus (curl bị pause bởi burst limit) lẫn phiên này (outage classifier công cụ) đều chưa gọi được:
  - Backend: `https://jama-crm-prod-production.up.railway.app/health` — kỳ vọng `{"status":"ok"}`
  - Frontend: `https://frontend-1pnjctn4a-jamacrm.vercel.app` — kỳ vọng 200
- **Việc đầu tiên của phiên kế tiếp:** chạy 2 lệnh curl trên + login thử admin trên frontend prod → điền kết quả vào đây.

## 6. Ghi chú vận hành đa phiên (quan trọng)

Ba "công nhân" đang thay phiên trên cùng repo (Fable 5 / Opus 4.8 / chủ dự án). Quy ước để không dẫm chân:
- Trước khi sửa: `git status` + `git diff` file định sửa.
- Sau mỗi đợt: commit + cập nhật Obsidian `Nhật ký phát triển.md` (memory `feedback_obsidian_notes`).
- Nguồn sự thật tiến độ: task list phiên + mục "BÀN GIAO" trong Obsidian.
