# Spec — Hiển thị dự án theo khung đầu việc phòng ban + Ưu tiên nguồn lực + Việt hóa giao diện

> **Executor:** Bất kỳ phiên AI nào (dự kiến Opus 4.8). Spec tự chứa. Theo 3 feedback của chủ dự án 15/07/2026.
> **Đã kiểm chứng model:** `Project.target_end_date`, `Project.total_value`, `Task.department` (+ index `ix_tasks_department`) ĐÃ TỒN TẠI trong `backend/app/models/project.py` — phần A & B **không cần migration**.

---

## Phần A — Khung đầu việc theo PHÒNG BAN, hiển thị ngay khi có dự án mới

**Yêu cầu gốc:** hệ thống đã có khung 19 đầu việc chuẩn (tự sinh khi lead ký HĐ thiết kế). Khi có dự án mới, các phòng ban phải **nhìn phát biết dự án đang ở đâu** trong khung đó.

### A1. Thẻ dự án trên Kanban (`frontend/src/app/projects/page.tsx`)

Thêm **thanh tiến độ mini 5 khối** trên mỗi thẻ — mỗi khối = 1 giai đoạn (Thiết kế → Báo giá → Thu mua → Thi công → Nghiệm thu), màu theo trạng thái đầu việc của giai đoạn đó:
- 🟩 xanh = xong hết đầu việc giai đoạn · 🟨 vàng = đang làm · ⬜ xám = chưa bắt đầu
- Hover/tap từng khối: tooltip "Thu mua: 2/3 việc · Phòng Thu mua".
- Dữ liệu: API kanban đã trả tasks hoặc bổ sung `stage_progress` (aggregate COUNT theo stage+status trong `GET /projects/pipeline/kanban` — 1 query GROUP BY, không N+1).

### A2. Chi tiết dự án — chế độ xem "Theo phòng ban"

Modal chi tiết hiện group theo giai đoạn (đã có) → thêm toggle **"Theo phòng ban"**: group tasks bằng `Task.department`, mỗi phòng 1 khối gồm: tên phòng, thanh % việc xong, danh sách đầu việc + người phụ trách + hạn. Phòng nào **chưa tới lượt** (giai đoạn trước chưa xong) hiện mờ kèm nhãn "Chờ <phòng trước>". → PM/leader từng phòng mở dự án bất kỳ là thấy ngay phần việc của phòng mình.

### A3. Dashboard phòng ban

Trang chủ của designer/pm/purchasing thêm khối **"Dự án đang đến phòng bạn"**: dự án có ≥1 đầu việc thuộc phòng mình ở trạng thái chưa xong VÀ giai đoạn hiện tại của dự án khớp phòng — sắp theo thứ tự ưu tiên Phần B. Endpoint: `GET /projects/by-department?dept=` (aggregate, phân trang).

## Phần B — Thứ tự ưu tiên hiển thị: CẬN DEADLINE trước, HỢP ĐỒNG LỚN sau

**Quy tắc sort mặc định** (mọi danh sách/kanban dự án active, backend sort — không sort client):

```
1. urgency_bucket ASC   — theo target_end_date:
     0 = quá hạn (target_end_date < hôm nay, status ≠ completed)
     1 = còn ≤ 14 ngày
     2 = còn ≤ 30 ngày
     3 = còn xa / chưa đặt hạn
2. total_value DESC     — trong cùng bucket, hợp đồng lớn đứng trước
3. target_end_date ASC  — tie-break
```

- Badge trên thẻ: 🔴 "Quá hạn X ngày" / 🟠 "Còn X ngày" (≤14) / giá trị HĐ format `1,2 tỷ`.
- Ngưỡng 14/30 ngày đặt trong SystemSetting (`project_urgent_days`, `project_warning_days`) — BGĐ chỉnh được.
- Giữ các sort thủ công hiện có (dropdown) — quy tắc trên chỉ là **mặc định khi mở trang**.
- `target_end_date` trống → nhắc nhẹ trên thẻ "Chưa đặt hạn" (để PM điền — không có hạn thì không ưu tiên được).
- Index hỗ trợ: thêm `Index("ix_projects_end_value", "status", "target_end_date", "total_value")` (Alembic revision nhỏ — thay đổi schema DUY NHẤT của spec này).
- Đồng bộ nơi khác: `/duan` (bot) và dashboard cũng sort theo quy tắc này; báo cáo BOD thêm dòng "⏰ N dự án quá hạn / M dự án cận hạn".

## Phần C — Việt hóa giao diện (yêu cầu: hạn chế tối đa tiếng Anh)

### C1. Quy tắc (đã lưu memory dự án — áp cho MỌI code từ nay)

1. **Nhãn UI mới bắt buộc tiếng Việt.** Thuật ngữ Anh chỉ giữ khi đã thành thói quen phổ thông và khó dịch gọn (KPI, OT, Email) — và **mọi thuật ngữ giữ lại phải có trong Bảng thuật ngữ** của `docs/HUONG_DAN_SU_DUNG_CRM.md` (§20 — đã tạo 15/07).
2. Code/API/tên biến giữ tiếng Anh (chuẩn kỹ thuật) — chỉ Việt hóa **chữ hiển thị cho người dùng** + thông báo bot.

### C2. Bảng đổi nhãn hiện có (quét 15/07 — executor rà thêm bằng grep)

| Hiện tại | Đổi thành | Vị trí chính |
|---|---|---|
| Dashboard | **Tổng quan** | Sidebar, tiêu đề trang chủ |
| Pipeline | **Luồng khách** (giữ "Pipeline" trong ngoặc lần đầu) | Sidebar, /leads |
| Check-in / Check-out | **Vào ca / Tan ca** (bot giữ lệnh `/checkin` `/checkout` — lệnh là mã) | /attendance, bot reply |
| Leaderboard | **Bảng xếp hạng** | /kpi (spec 04) |
| Demo Mode / Work Mode | **Chế độ Tập luyện / Chế độ Làm việc** | Login, Sidebar banner |
| Gross / Net | **Tổng thu nhập / Thực lĩnh** (đã đúng ở payslip — rà nốt bảng lương kế toán) | /payroll, phiếu lương |
| Copy text | **Sao chép** | /quote-tool |
| Final File | **File kết quả chốt** (đã Việt — giữ) | Task modal |
| SLA | giữ "SLA" + thêm vào Bảng thuật ngữ ("cam kết thời hạn chăm sóc") | Dashboard |

### C3. Cách làm không vỡ

- Tập trung chuỗi vào `frontend/src/lib/labels.ts` (const object) cho các nhãn dùng ≥2 nơi; chuỗi 1 nơi sửa tại chỗ. **KHÔNG** kéo framework i18n (chỉ 1 ngôn ngữ — YAGNI).
- Bot: rà reply trong `telegram-bot/bot/handlers/*` — một số reply đang không dấu ("Check-in thanh cong") do lo Unicode cũ → chuyển có dấu hết (aiogram xử lý UTF-8 tốt).
- QA gate: thêm vào bất biến của `docs/specs/06` §2: **"(6) Không nhãn UI tiếng Anh mới ngoài Bảng thuật ngữ"** — mỗi version QA per-role phải soi mục này.

## Phần D — Acceptance criteria

1. Given 3 dự án: A (còn 5 ngày, 500tr), B (còn 5 ngày, 2 tỷ), C (còn 60 ngày, 5 tỷ), When mở /projects, Then thứ tự **B → A → C**.
2. Given dự án quá hạn 3 ngày, Then đứng ĐẦU danh sách với badge 🔴 "Quá hạn 3 ngày"; báo cáo BOD sáng hôm sau có dòng cảnh báo.
3. Given dự án mới tạo từ lead ký HĐ, When designer mở chi tiết + toggle "Theo phòng ban", Then thấy đủ khung đầu việc mọi phòng, phòng Thiết kế active, các phòng sau mờ "Chờ Thiết kế".
4. Thẻ kanban hiện thanh 5 khối đúng trạng thái; API kanban không tăng số query (đo bằng echo log — 1 aggregate).
5. Trang /attendance hiện "Vào ca/Tan ca"; login hiện "Chế độ Tập luyện"; grep `"Dashboard"` trong tsx UI string = 0 kết quả (trừ labels.ts comment).
6. `docs/HUONG_DAN_SU_DUNG_CRM.md` §20 chứa mọi thuật ngữ Anh còn dùng; QA per-role pass bất biến số 6.

## Phần E — Hướng dẫn thực thi (cho Opus 4.8)

1. Đọc: `frontend/src/app/projects/page.tsx`, `backend/app/api/projects.py` (endpoint kanban + list), `backend/app/agents/task_coordinator.py` (blueprint 19 đầu việc — xem department gán thế nào), `docs/specs/06` (để cập nhật bất biến QA).
2. Thứ tự: B (sort backend + index + badge — giá trị ngay, ít rủi ro) → A1 → A2 → A3 → C (Việt hóa — làm cuối để quét một lượt cả nhãn mới).
3. Kiểm tra blueprint: nếu 19 đầu việc chưa gán đủ `department` khi tự sinh → sửa `task_coordinator.py` gán theo mapping stage→phòng (Thiết kế→DESIGN, Báo giá→DESIGN+SALES, Thu mua→PURCHASING, Thi công→PM, Nghiệm thu→PM+SALES) + script backfill task cũ.
4. Verify: pytest full + case D1-D6; chạy QA per-role theo spec 06 (đặc biệt role designer/pm/purchasing với khối "Dự án đang đến phòng bạn").
5. Xong: cập nhật Obsidian (Nhật ký + note module nếu đáng) theo memory `feedback_obsidian_notes`.
