# Quy trình — QA/QC theo TỪNG ROLE sau mỗi version changelog

> **Executor:** Bất kỳ phiên AI nào (dự kiến Opus 4.8) — đây là quy trình LẶP LẠI, áp dụng sau MỌI version từ nay về sau (yêu cầu của chủ dự án 15/07/2026).
> **Định nghĩa "version":** mỗi entry `## Phiên <ngày>` mới trong `Obsidian/1-Projects/jama-crm/Nhật ký phát triển.md` (đồng bộ với section mới trong `task.md`).

---

## §1. Nguyên tắc

1. **Mỗi role một pass QA riêng** — bug RBAC/UX chỉ lộ khi đóng vai đúng người dùng. 8 role web + 2 surface: Telegram bot, mobile viewport.
2. **3 lớp kiểm:** (L1) automated pytest+tsc, (L2) per-role scenario walkthrough (AI agent đóng vai hoặc người), (L3) regression RBAC negative (cái KHÔNG được thấy/làm).
3. **Có bằng chứng:** mỗi pass sinh 1 báo cáo `docs/qa/QA-<version>.md` — không có báo cáo = chưa QA.
4. Finding Critical (mất dữ liệu, lộ quyền, crash luồng chính) → **chặn release**; High → fix trong 48h; Medium/Low → backlog.

## §2. Ma trận QA per-role (checklist chuẩn — chạy mỗi version)

Tài khoản test: theo `docs/QUICK_REFERENCE.md`. Mỗi role kiểm: (a) luồng chính, (b) tính năng MỚI của version áp lên role đó, (c) negative RBAC.

| Role | Luồng chính phải pass | Negative RBAC phải fail đúng |
|---|---|---|
| **admin** | Dashboard exec · duyệt approvals · HR resign preview/confirm · audit-logs có bản ghi mới · payroll approve | — (full quyền, kiểm audit đủ) |
| **executive** | Dashboard exec · P&L · reports · projects read | KHÔNG sửa lead/contract; không thấy HR/Finance/Kho |
| **leader** | Pipeline team · phân công lead · bảng công team · duyệt phép/OT team · KPI team | KHÔNG thấy P&L, lương người khác, team khác; không duyệt đơn CHÍNH MÌNH |
| **data_entry (sales)** | Tạo lead → đổi stage → activity → quote-tool → checkin/out → xin nghỉ → xem phiếu lương mình | KHÔNG thấy lead người khác, Kho, HR, Kế toán, P&L |
| **designer** | Projects được giao · task status · upload file · quotation | KHÔNG thấy Pipeline, Hợp đồng, Kế toán |
| **pm** | Tạo dự án · tasks CRUD · yêu cầu vật tư · nghiệm thu upload | KHÔNG thấy Kế toán/HR/P&L |
| **accountant** | Giao dịch thu/chi · công nợ · generate→submit payroll · duyệt tạm ứng · HR add/offboard · xuất CSV | KHÔNG thấy Pipeline leads; không sửa được kỳ lương đã khóa (409) |
| **purchasing** | Kho vật tư CRUD · duyệt yêu cầu vật tư (web + inline Telegram) · cảnh báo tồn thấp | KHÔNG thấy Khách hàng/Báo cáo/Kế toán |
| **Telegram bot** | /start /lead /pipeline /briefing /duan /baocao /vatlieu /checkin(2 mode) /nghiphep /phieuluong(chat riêng only) /choduyet | /phieuluong trong NHÓM phải từ chối; auto-parse lead không chạy trong nhóm |
| **Mobile 390px** | Dashboard, Pipeline, /attendance, /approvals không vỡ layout, bảng → card | — |

**Bất biến hệ thống kiểm MỌI version:** (1) không số liệu tài chính/lương nào xuất hiện trong nhóm Telegram; (2) kỳ lương khóa từ chối mọi sửa công/hoa hồng; (3) user inactive không đăng nhập được; (4) demo mode không gọi API thật (Network tab); (5) thao tác nhạy cảm sinh AuditLog; (6) không nhãn UI tiếng Anh mới ngoài Bảng thuật ngữ (`HUONG_DAN_SU_DUNG_CRM.md` §20 — spec 07C).

## §3. Cách chạy bằng AI agents (khuyến nghị cho Opus 4.8)

Fan-out 10 agent song song (hoặc tuần tự nếu subagent không khả dụng — tự chạy từng role):

```
Prompt khuôn cho mỗi agent:
"Bạn là QA đóng vai role <X> của JAMA CRM. Server: <URL>, đăng nhập <email>/<pass>
(docs/QUICK_REFERENCE.md). Version đang kiểm: <changelog trích từ Nhật ký>.
Chạy checklist trong docs/specs/06-qa-per-role-process.md §2 dòng role <X>
qua API (httpx) hoặc browser. Với MỖI mục: PASS/FAIL + bằng chứng
(status code / screenshot / response). Đặc biệt soi tính năng mới: <liệt kê>.
Trả về JSON: {role, passed: [], failed: [{item, evidence, severity}], notes}."
```

Tổng hợp 10 JSON → 1 verify pass (adversarial: mỗi FAIL Critical/High phải tái hiện được lần 2 trước khi tính) → viết báo cáo.

## §4. Template báo cáo `docs/qa/QA-<version>.md`

```markdown
# QA Report — <version/ngày>
**Changelog kiểm:** <link entry Nhật ký>   **Người/agent chạy:** ...
**L1 Automated:** pytest <n> passed · tsc clean · (load test nếu đụng Track hiệu năng)
## Kết quả per-role
| Role | Pass | Fail | Ghi chú |
|---|---|---|---|
(10 dòng)
## Findings
| # | Severity | Role | Mô tả | Bằng chứng | Trạng thái |
## Bất biến hệ thống: 5/5 pass?
## Verdict: RELEASE / BLOCK (lý do)
```

Sau khi báo cáo xong: link vào entry changelog trong Obsidian Nhật ký (`QA: [[../qa/QA-<version>]] — verdict`).

## §5. Definition of Done cho MỌI version từ nay

1. Full pytest xanh + `tsc --noEmit` clean (L1).
2. Báo cáo QA per-role tồn tại trong `docs/qa/`, 10/10 surface được chạy, 5/5 bất biến pass.
3. 0 finding Critical mở; High có owner + deadline.
4. Obsidian đã cập nhật (memory `feedback_obsidian_notes`): entry Nhật ký + link QA report.
5. Nếu version đụng hiệu năng (spec 05): kèm kết quả load test kịch bản liên quan.

## §6. Bootstrap lần đầu (việc một lần khi thực thi spec này)

1. Tạo thư mục `docs/qa/` + file template trên.
2. Viết `backend/tests/test_rbac_matrix.py` — parametrize 8 role × bảng endpoint chính (allow/deny theo ma trận §2) để L3 negative chạy tự động vĩnh viễn (~60 case, nhanh).
3. Chạy pass QA đầu tiên cho version 15/07 (HR Phase 1) làm mẫu → `docs/qa/QA-2026-07-15.md`.
4. Ghi quy trình này thành note Obsidian `QA theo Role.md` link vào MOC [[JAMA CRM]].
