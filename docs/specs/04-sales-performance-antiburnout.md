# Spec — Đánh giá hiệu suất & Chống burnout cho Team Sales

> **Executor:** Bất kỳ phiên AI nào (dự kiến Opus 4.8). Spec tự chứa — đọc mục "Hướng dẫn thực thi" cuối file trước khi code.
> **Ngày:** 15/07/2026. **Tiền đề:** HR Phase 1 đã xong (attendance/OT/leave/approval/audit — xem `docs/specs/01-03` và `Obsidian/1-Projects/jama-crm/HR Chấm công Nghỉ phép Lương.md`), 183 tests passing.
> **Bối cảnh tổ chức:** 5 team sales độc lập, mỗi team có leader; quy tắc SLA follow-up ≤3 ngày; lead quá 7 ngày bị thu hồi giao người khác (automation đã chạy); hoa hồng 3%/2% theo mốc 50/30/20.

---

## Phần A — Đánh giá hiệu suất (KPI)

### A1. Nguyên tắc thiết kế

1. **Đo cả effort lẫn outcome** — chỉ đo doanh số sẽ trừng phạt sale nhận lead xấu; chỉ đo effort sẽ khuyến khích spam activities. Trộn 3 nhóm có trọng số.
2. **Mọi metric lấy từ dữ liệu ĐÃ CÓ trong hệ thống** — không bắt sales nhập thêm bất cứ gì. Nguồn: `leads` (stage, lost_reason, assigned_to, last_contacted_at, deal_value), `activities`, `contracts`, `commissions`, `attendance_records` (mới).
3. **Trọng số cấu hình được** qua SystemSetting (pattern `payroll_engine.PAYROLL_SETTING_DEFAULTS`) — BGĐ chỉnh không cần deploy.
4. **Minh bạch:** nhân viên thấy KPI của CHÍNH MÌNH + leaderboard ẩn danh phần thấp (top 5 hiện tên, còn lại chỉ hiện vị trí của mình).

### A2. Bộ metric (kỳ = tháng)

| Nhóm | Metric | Nguồn | Định nghĩa |
|---|---|---|---|
| **Effort (30%)** | `activity_rate` | activities | Số hoạt động ghi nhận / ngày làm việc (từ attendance) |
| | `sla_compliance` | leads.last_contacted_at | % lead active được chạm ≤3 ngày (logic có sẵn trong `services/automation.py` — tái dùng `_last_touch`) |
| | `first_touch_hours` | activities đầu tiên − lead.created_at | Trung vị giờ phản hồi lead mới được gán |
| **Outcome (50%)** | `signed_count` / `signed_value` | leads stage=signed_design + contracts | Số HĐ ký + tổng giá trị |
| | `stage_conversion` | leads | % new→interested, % survey→signed (funnel cá nhân) |
| | `pipeline_value_weighted` | leads active | Σ deal_value × trọng số stage (new 10%, interested 25%, survey 50%, potential 75%) |
| **Quality (20%)** | `recall_rate` | AuditLog/automation recall | % lead bị hệ thống thu hồi (signal chăm sóc kém) — CÀNG THẤP CÀNG TỐT |
| | `lost_no_response_rate` | leads.lost_reason='không phản hồi' | % mất do bỏ bê (loại trừ mất do giá/đối thủ — không phải lỗi sale) |

`kpi_score = 100 × Σ(normalize(metric) × weight)` — normalize theo percentile trong toàn khối sales của kỳ (tránh mốc tuyệt đối lỗi thời).

### A3. Data model

```python
# backend/app/models/performance.py
class KpiSnapshot(Base):
    __tablename__ = "kpi_snapshots"
    id: str(36); user_id: FK users; period: str(10)  # "2026-07"
    metrics_json: Text        # dict toàn bộ metric thô
    score: float              # 0-100
    rank_in_team: int; rank_overall: int
    created_at
    Index("ix_kpi_user_period", "user_id", "period", unique=True)

class CoachingNote(Base):
    __tablename__ = "coaching_notes"
    id; user_id (nhân viên); coach_id (leader); note: Text
    kind: str(20)  # one_on_one | praise | concern | plan
    created_at
    # CHỈ leader trực tiếp + admin đọc; nhân viên đọc note về mình
    Index("ix_coaching_user", "user_id", "created_at")

class ReviewCycle(Base):
    __tablename__ = "review_cycles"
    id; user_id; period: str(7)  # "2026-Q3"
    self_json: Text | None      # tự đánh giá (3 câu hỏi cố định)
    leader_json: Text | None    # leader đánh giá + điểm
    goals_json: Text | None     # 3 mục tiêu kỳ sau (OKR-lite)
    status: str  # pending_self -> pending_leader -> done
    suggested_grade_change: str | None  # đề xuất lên/giữ bậc lương (nối SalaryGrade)
```

### A4. Service + jobs

- `backend/app/services/kpi_engine.py::compute_kpi(db, user, period)` — tính toàn bộ metric bằng aggregate SQL (KHÔNG loop per-lead); `snapshot_all(db, period)` cho toàn khối sales.
- Worker: job `kpi_snapshot` chạy 6:00 sáng **thứ Hai** (snapshot tuần rolling cho leaderboard) + mùng 1 (chốt kỳ tháng — dùng cho review). Pattern date-flag như `_last_attendance_close_date` trong `worker.py`.
- Quý: job tạo ReviewCycle pending_self cho mọi sales + notify.

### A5. API + UI + Bot

| Endpoint | Role |
|---|---|
| `GET /kpi/me?period=` | mọi role (sales thấy đủ metric) |
| `GET /kpi/team?period=` | leader (team mình), admin/executive (mọi team) |
| `GET /kpi/leaderboard?period=` | mọi sales — top 5 hiện tên, mình hiện vị trí |
| `POST /coaching-notes` / `GET /coaching-notes?user_id=` | leader/admin (scope team) |
| `GET/PUT /reviews/me` · `PUT /reviews/{id}/leader` | flow 2 bước |

- Web: trang `/kpi` (tab: Của tôi / Team (leader) / Leaderboard). Thêm sparkline 6 kỳ.
- Bot: `/kpi` — tóm tắt cá nhân; leader `/teamkpi`.
- Leaderboard TUẦN đăng nhóm Telegram (positive-only: top 3 + "most improved") — **không bao giờ** đăng ranking thấp lên nhóm.

## Phần B — Chống burnout

### B1. Tín hiệu (tự động từ dữ liệu có sẵn — không survey ép buộc)

| Signal | Nguồn | Ngưỡng default (SystemSetting) |
|---|---|---|
| OT kéo dài | attendance.ot_hours | >10h OT/tuần × 3 tuần liên tiếp |
| Làm Chủ nhật | attendance work_date CN | ≥3 CN/tháng |
| Không nghỉ phép | leave_requests | 0 ngày phép trong 90 ngày + số dư ≥6 |
| Hoạt động đêm | activities.created_at giờ VN | ≥30% activities sau 21h, 2 tuần liên tục |
| Disengagement | KpiSnapshot | activity_rate giảm ≥40% so trung bình 3 kỳ + SLA giảm |
| Quá tải lead | leads active/người | > `lead_cap` (default 25) |

`burnout_risk = số signal active` → 0-1 xanh, 2 vàng, ≥3 đỏ.

### B2. Hành động khi cảnh báo

1. **Riêng tư tuyệt đối:** cảnh báo đỏ/vàng chỉ gửi **chat riêng leader trực tiếp + admin** (pattern payslip — không nhóm, không cho sale khác thấy). Nhân viên tự thấy trạng thái của mình ở `/kpi` kèm gợi ý tích cực ("bạn còn 8 ngày phép — đặt lịch nghỉ nhé"), không thấy chữ "burnout risk" gây lo âu.
2. **Giảm tải tự động (opt-in per team):** khi 1 sale chạm `lead_cap`, auto-assign lead mới (logic `_least_loaded_teammate` có sẵn trong `api/hr.py`) bỏ qua người đó cho tới khi giảm dưới trần.
3. **Quiet hours bot:** `services/telegram_notify.py` thêm guard — thông báo không khẩn (không phải sự cố/duyệt lương) gửi trong 21:00–07:30 VN thì **xếp hàng đến sáng** (bảng nhỏ `deferred_notifications` hoặc dùng Notification có sẵn + worker flush 7:30).
4. **Nhắc nghỉ phép chủ động:** worker tháng — ai còn >8 ngày phép sau tháng 9 → nhắc riêng + nhắc leader xếp lịch.
5. **Coaching gợi ý:** cảnh báo gửi leader kèm 2-3 hành động mẫu (giảm lead, 1-1, hoán đổi nguồn lead xấu) — ghi lại bằng CoachingNote để theo dõi có làm hay không.

### B3. Chính sách (ghi vào docs + thư viện SOP sau này)

- Dữ liệu burnout **không dùng để phạt/xếp loại** — chỉ để hỗ trợ. Ghi rõ trong note chính sách + hiển thị footer trang KPI.
- Leader bị đo ngược: % cảnh báo đỏ của team tồn tại >30 ngày không có CoachingNote → hiện trên dashboard admin.

## Phần C — Acceptance criteria chính (Given/When/Then)

1. Given kỳ 2026-08 có dữ liệu leads+activities+attendance, When job `kpi_snapshot` chạy, Then mỗi sales active có 1 KpiSnapshot với score 0-100 và metrics_json đủ 8 metric; chạy lại job không tạo bản ghi trùng (unique user+period, update-in-place).
2. Given sale A có 3 tuần OT 12h/tuần, When job burnout chạy, Then leader của A nhận đúng 1 tin chat riêng (dedupe ref `burnout-{user}-{week}`), nhóm Telegram KHÔNG nhận gì, sale B không query được signal của A (403).
3. Given team bật lead_cap=25 và A đang giữ 25 lead active, When lead mới được auto-assign, Then A bị bỏ qua, lead vào người ít nhất còn lại; AuditLog ghi lý do.
4. Given 22:00 VN có notification loại `approval`, When gửi, Then bị hoãn tới 7:30 sáng; loại `incident` gửi ngay.
5. Review quý: nhân viên submit self → leader nhận notify → leader chấm + đề xuất bậc → admin thấy danh sách đề xuất trong 1 màn hình.
6. RBAC: sales không xem KPI người khác (chỉ leaderboard ẩn danh); CoachingNote của team X không lộ cho leader team Y. Toàn bộ đọc/ghi nhạy cảm có AuditLog.

## Phần D — Hướng dẫn thực thi (cho Opus 4.8)

1. Đọc trước: `backend/app/services/automation.py` (helper `_notify` + `_last_touch`), `backend/app/worker.py` (pattern job), `backend/app/services/attendance_service.py`, `backend/app/api/hr.py::_least_loaded_teammate`, `frontend/src/app/attendance/page.tsx` (pattern trang tab).
2. Thứ tự: models+migration (Alembic revision mới trên head `dbceffd80f23`) → kpi_engine + tests công thức (fixture giả lập 3 sales chênh lệch rõ) → API+RBAC → worker jobs → UI `/kpi` → bot → burnout signals → quiet hours.
3. Aggregate SQL bắt buộc — reviewer sẽ reject loop-per-lead (xem bài học N+1 trong spec 05 §3).
4. Verify: pytest toàn suite xanh (baseline 183) + case chuẩn tay: sale 20 activities/20 ngày công, SLA 90%, 2 HĐ ký 500tr → tính score tay đối chiếu; chạy 2 lần job không duplicate; quiet-hours test giả lập giờ bằng inject `now`.
5. Sau khi xong: cập nhật Obsidian theo memory `feedback_obsidian_notes` + entry Nhật ký + QA per-role theo `docs/specs/06`.
