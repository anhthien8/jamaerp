# Roadmap khối HR — JAMA HOME (100+ nhân sự)

> Tổng hợp từ brainstorm 15/07/2026. Chi tiết kỹ thuật: spec 01 (backend chấm công/phép/lương), 02 (Approval Center), 03 (on/offboarding).
> **Nguyên tắc:** tái dùng tối đa hạ tầng đã chạy tốt — Telegram bot + inline approve, worker scheduler, pattern RBAC, code offboarding có sẵn trong `api/hr.py`.

---

## Giai đoạn 1 — MVP (2-4 tuần)

Thứ tự triển khai (theo phụ thuộc):

| # | Tính năng | Độ phức tạp | Phụ thuộc | Spec |
|---|---|---|---|---|
| 1 | Chấm công (AttendanceRecord + web/Telegram checkin + bảng công) | M | — | 01 §1.1 |
| 2 | AuditLog + gắn vào endpoint nhạy cảm | S | — | 01 §1.5 |
| 3 | Nghỉ phép + duyệt Telegram | M | Approval engine tối giản | 01 §1.2, 02 |
| 4 | Approval Center (engine + màn "Chờ tôi duyệt") | M | — | 02 |
| 5 | Bảng lương tự động + duyệt 2 cấp + phiếu lương Telegram riêng | L | 1, 2, 3 | 01 §1.3 |
| 6 | Vá offboarding (hoa hồng treo, thu hồi Telegram, lương cuối) + tạo tài khoản riêng cho 3 phòng đang dùng chung admin | S-M | 2 | 03 §3 |

### User story & acceptance criteria chính

**US-1 Chấm công:** Là nhân viên, tôi check-in/out bằng Telegram hoặc web để công của tôi được tính tự động.
- Given nhân viên đã link Telegram, When gõ `/checkin` lúc 8:02, Then tạo AttendanceRecord ngày hôm đó (giờ VN) và trả lời xác nhận.
- Given đã check-in, When `/checkout` lúc 18:30, Then work_hours=8, ot_hours=2 với ot_status=pending gửi leader duyệt.
- Given quên checkout, When qua 23:59, Then hệ thống tự đóng ca 8h + cờ cho leader, ghi note "auto-close".
- Given giám sát tại công trình, When `/checkin JMH-001` kèm GPS, Then ghi cả AttendanceRecord lẫn TaskActivity như hiện tại.

**US-2 Nghỉ phép:** Là nhân viên, tôi xin nghỉ và biết kết quả trong 24h.
- Given số dư phép 12 ngày, When tạo đơn 2 ngày và leader bấm ✅ trên Telegram, Then status=approved, số dư còn 10, bảng công 2 ngày đó ghi nghỉ có lương.
- Given đơn 5 ngày, When leader duyệt, Then đơn chuyển tiếp admin (2 cấp) — chưa trừ phép cho đến khi admin duyệt.
- Given leader không phản hồi 48h, Then đơn escalate lên admin và cả hai nhận nhắc.

**US-3 Lương:** Là kế toán, tôi bấm 1 nút sinh bảng lương cả công ty từ công + hoa hồng thật.
- Given kỳ 2026-07 đã chốt công, When `POST /payroll/generate`, Then mỗi user active có 1 dòng draft: base×(công/22) + OT + hoa hồng approved kỳ đó + phụ cấp − BHXH(10.5+1.5+1%) − tạm ứng.
- Given kế toán submit, When admin approve, Then kỳ bị khóa — mọi sửa công/hoa hồng kỳ đó bị backend từ chối (409).
- Given kỳ đã paid, When hệ thống gửi phiếu lương, Then mỗi người nhận **chat riêng** Telegram; không tin nhắn nào vào nhóm chung; ai chưa link Telegram nằm trong danh sách gửi tay cho kế toán.
- Given tôi là nhân viên, When mở `/payroll/me`, Then chỉ thấy phiếu lương của chính tôi, các kỳ đã paid.

**US-4 Audit:** Là admin, mọi thay đổi lương/quyền/nghỉ việc đều truy vết được: actor, before/after, thời gian.

### Chỉ số thành công MVP (đo sau 1 tháng go-live)
- ≥90% nhân viên check-in qua hệ thống (thay vì chấm tay).
- 100% đơn nghỉ phép đi qua hệ thống; thời gian duyệt trung vị <24h.
- Kỳ lương đầu tiên: sinh tự động, sai lệch phải sửa tay <5% số dòng.
- 0 sự cố lộ thông tin lương (kiểm tra log Telegram).

### Rủi ro triển khai
| Rủi ro | Giảm thiểu |
|---|---|
| 100 người đổi thói quen chấm công | Tuần 1-2 chạy song song với cách cũ; briefing nhóm 8:00 nhắc; leader làm gương |
| Dữ liệu lương nhạy cảm | Phiếu lương chỉ chat riêng; RBAC leader không xem lương; AuditLog từ ngày đầu; đổi JWT secret hardcoded (known issue) trước go-live |
| Tính đúng BHXH luật VN | Tỷ lệ đã cấu hình được trong SalaryGrade; kế toán đối chiếu tay kỳ đầu; trần đóng BHXH cần xác nhận với kế toán trưởng |
| SQLite ghi đồng thời giờ cao điểm | WAL đã bật; retry-on-locked; kế hoạch chuyển Postgres trên Railway |
| Chưa có Alembic | Script migration thủ công cho cột mới + đưa Alembic vào ngay giai đoạn này |

## Giai đoạn 2 — Quý tiếp theo

1. **Hồ sơ nhân sự đầy đủ + onboarding checklist tự sinh** (spec 03 §1-2) — nhắc hạn HĐLĐ, quiz Demo Mode.
2. **KPI cá nhân theo vai trò** — trang "KPI của tôi" (sales: SLA follow-up, conversion; designer: task đúng hạn; giám sát: báo cáo/ngày) — dữ liệu đã có sẵn trong leads/tasks/activities.
3. **Tạm ứng lương + chi phí công tác + OT** vào Approval Center (mở rộng engine giai đoạn 1).
4. **Báo cáo BHXH** — danh sách tăng/giảm lao động tháng cho kế toán.
5. **Thư viện SOP trong app** — đưa docs/cheat-sheets lên, tracking "đã đọc".

## Giai đoạn 3 — Sau đó

1. Review hiệu suất quý + coaching log (gắn cơ chế lên bậc trong 6 bậc lương).
2. HR analytics: headcount, turnover, chi phí lương/doanh thu, cảnh báo attrition (sale nhiều ngày không có activity).
3. Rà soát phân quyền định kỳ (báo cáo quý tự động).
4. Tuyển dụng: pipeline ứng viên (tái dùng UI Kanban lead) + referral thưởng qua Telegram.
5. Bảng tin nội bộ + danh bạ + sơ đồ tổ chức.
