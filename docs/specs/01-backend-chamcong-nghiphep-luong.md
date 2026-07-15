# Spec kỹ thuật — Chấm công · Nghỉ phép · Bảng lương tự động · Audit log

> **Phạm vi:** Nhóm ưu tiên "Ngay" cho đội ngũ 100+ nhân sự JAMA HOME.
> **Nguyên tắc:** Xây trên nền code hiện có, đúng convention codebase (SQLAlchemy async, `mapped_column`, id `String(36)` uuid4, router theo module trong `backend/app/api/`, RBAC qua `middleware/rbac.py`).
> **Ngày:** 15/07/2026

---

## 0. Hiện trạng liên quan (đã kiểm chứng trong code)

| Thành phần | File | Ghi chú |
|---|---|---|
| User có `telegram_user_id`, `resign_date` | `backend/app/models/user.py` | Nền cho phiếu lương riêng tư + offboarding |
| `/checkin`, `/checkout` GPS | `backend/app/api/telegram_workflow.py:421` | ⚠️ Chỉ ghi `TaskActivity` text — **không thể tổng hợp công**. Cần bảng riêng |
| `Payroll` (draft/approved/paid), `Commission` (mốc 50/30/20) | `backend/app/models/payroll.py` | Đã có khung, thiếu: liên kết công thực tế, BHXH, luồng duyệt 2 cấp, khóa kỳ |
| `SalaryGrade` 6 bậc + tỷ lệ BHXH/BHYT/BHTN | `backend/app/models/salary_grade.py` | ⚠️ User chưa có FK tới bậc lương |
| Pattern duyệt Telegram inline | `MaterialRequest` trong `telegram_workflow.py` | Tái dùng cho nghỉ phép/tạm ứng |
| Scheduler nền | `backend/app/worker.py`, `services/automation.py` | Dùng cho chốt công cuối tháng, nhắc duyệt |
| Push Telegram | `backend/app/services/telegram_notify.py` | Dùng gửi phiếu lương chat riêng |

---

## 1. Data model mới

### 1.1 `attendance_records` — chấm công (models/attendance.py)

```python
class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: str                      # String(36), uuid4
    user_id: str                 # FK users.id, nullable=False
    work_date: Date              # ngày công (theo giờ VN, không phải UTC)
    check_in: DateTime | None
    check_out: DateTime | None
    check_in_lat: float | None   # GPS — bắt buộc với giám sát tại công trình
    check_in_lng: float | None
    project_id: str | None       # FK projects.id — check-in tại công trình nào
    source: str                  # "telegram" | "web"
    work_hours: float            # tự tính khi checkout, default 0
    ot_hours: float              # giờ vượt 8h/ngày hoặc cuối tuần, cần duyệt mới tính lương
    ot_status: str               # none | pending | approved | rejected
    note: str | None
    created_at / updated_at

    __table_args__ = (
        Index("ix_attendance_user_date", "user_id", "work_date", unique=True),
        # 1 người 1 bản ghi/ngày; check-in nhiều công trình → ghi TaskActivity như cũ,
        # AttendanceRecord chỉ giữ in đầu tiên & out cuối cùng
    )
```

**Quy tắc nghiệp vụ:**
- Check-in lần đầu trong ngày → tạo record; các lần sau chỉ cập nhật `check_out`.
- `work_hours = min(check_out - check_in, 8)`; phần vượt → `ot_hours` với `ot_status=pending`.
- Quên checkout → job đêm (worker) tự đóng ca lúc 23:59 với `note="auto-close"`, giờ công = 8h trần, đánh cờ cho leader xác nhận.
- Văn phòng: check-in web (không cần GPS) hoặc Telegram `/checkin` không kèm mã dự án. Hiện trường: bắt buộc `project_code` + GPS (giữ nguyên lệnh `/checkin JMH-001`).
- **Giữ nguyên** việc ghi `TaskActivity` hiện tại (bằng chứng công trình) — chỉ **thêm** ghi song song vào `attendance_records`.

### 1.2 `leave_requests` + `leave_balances` — nghỉ phép (models/leave.py)

```python
class LeaveBalance(Base):
    __tablename__ = "leave_balances"
    id, user_id (FK), year (int)
    annual_total: float    # 12 ngày/năm + thâm niên
    annual_used: float
    sick_used: float
    unpaid_used: float
    Index("ix_leave_balances_user_year", "user_id", "year", unique=True)

class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id, user_id (FK)
    leave_type: str        # annual | sick | unpaid
    start_date: Date
    end_date: Date
    days: float            # hỗ trợ 0.5 ngày
    reason: str(500)
    status: str            # pending | approved | rejected | cancelled
    approver_id: str | None
    reject_reason: str | None
    created_at / resolved_at
    Index("ix_leave_requests_user", "user_id"), Index("ix_leave_requests_status", "status")
```

**Luồng duyệt** (theo pattern `MaterialRequest`):
- Nhân viên tạo đơn (web hoặc Telegram `/nghiphep 20/07 21/07 việc gia đình`).
- ≤3 ngày → leader trực tiếp duyệt. >3 ngày hoặc người tạo là leader → admin duyệt.
- Duyệt qua Telegram inline button [✅ Duyệt] [❌ Từ chối] — đúng pattern vật tư.
- Approve → trừ `LeaveBalance`, ghi vào `attendance_records` các ngày nghỉ (`source="leave"`, `work_hours` = 8 nếu phép năm có lương, 0 nếu không lương).
- Lịch nghỉ team: `GET /leaves/calendar?team_id=&month=` cho leader.

### 1.3 Nâng cấp `Payroll` (sửa models/payroll.py — thêm cột, không phá schema cũ)

```python
# Thêm vào class Payroll:
work_days: float           # công thực tế từ attendance
standard_days: float       # công chuẩn của tháng (22)
ot_hours: float
ot_pay: float
allowance: float           # phụ cấp
advance_deduction: float   # trừ tạm ứng (xem spec 02)
bhxh_employee: float       # 10.5% + 1.5% + 1% trên base_salary theo bậc
bhxh_company: float        # 21.5% — chỉ để báo cáo chi phí, không trừ lương
salary_grade_id: str | None  # FK salary_grades.id — snapshot bậc tại kỳ lương
approved_by: str | None    # admin duyệt
paid_at: DateTime | None
# status mở rộng: draft → pending_approval → approved → paid  (locked = approved trở đi)
```

**Công thức:**
```
gross = base_salary × (work_days / standard_days) + ot_pay + commission_total + bonus + allowance
net   = gross − bhxh_employee − advance_deduction − deductions
```

### 1.4 User — thêm liên kết bậc lương (sửa models/user.py)

```python
salary_grade_id: str | None = mapped_column(String(36), ForeignKey("salary_grades.id"), nullable=True)
contract_end_date: Date | None   # hạn HĐLĐ — worker nhắc trước 30 ngày
```

### 1.5 `audit_logs` (models/audit.py)

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id, actor_id (FK users.id)
    action: str(50)     # payroll.approve, payroll.pay, user.role_change, user.resign,
                        # leave.approve, salary_grade.update, advance.approve ...
    entity_type: str(30); entity_id: str(36)
    before_json: Text | None; after_json: Text | None
    ip: str | None; created_at
    Index("ix_audit_entity", "entity_type", "entity_id"), Index("ix_audit_actor", "actor_id")
```

Ghi log bằng helper `services/audit.py::log_action(db, actor, action, entity, before, after)` — gọi trong các endpoint nhạy cảm (lương, quyền, nghỉ việc, bậc lương). Chỉ admin đọc: `GET /audit-logs?entity_type=&actor=&from=&to=`.

---

## 2. API endpoints

Router mới: `api/attendance.py`, `api/leaves.py`, `api/audit.py`; mở rộng `api/hr.py` (payroll đã nằm rải trong accounting — gom về `api/payroll.py`).

| Method & Path | Mô tả | Role |
|---|---|---|
| `POST /attendance/checkin` | body: `{source, project_code?, lat?, lng?}` — web dùng JWT, Telegram dùng `user_tg_id` (giữ endpoint cũ, thêm ghi AttendanceRecord) | mọi role |
| `POST /attendance/checkout` | đóng ca, tính work_hours/ot_hours | mọi role |
| `GET /attendance/me?month=` | bảng công cá nhân | mọi role |
| `GET /attendance/team?team_id=&month=` | bảng công team | leader (team mình), admin, accountant |
| `PATCH /attendance/{id}` | sửa công (quên chấm) — bắt buộc `note`, ghi audit | leader, accountant, admin |
| `POST /attendance/{id}/ot-approve` \| `ot-reject` | duyệt OT | leader, admin |
| `POST /leaves` | tạo đơn nghỉ | mọi role |
| `GET /leaves/me` · `GET /leaves/pending` · `GET /leaves/calendar` | xem đơn / chờ duyệt / lịch team | theo scope role |
| `POST /leaves/{id}/approve` \| `reject` \| `cancel` | duyệt/hủy | leader (≤3 ngày, team mình), admin |
| `GET /leaves/balance/me` | số dư phép | mọi role |
| `POST /payroll/generate?period=2026-07` | sinh bảng lương draft cho toàn bộ user active: gộp attendance + commission (status=approved, period khớp) + tạm ứng | accountant, admin |
| `POST /payroll/{period}/submit` | draft → pending_approval, notify admin | accountant |
| `POST /payroll/{period}/approve` \| `reject` | admin duyệt cả kỳ → khóa; reject kèm lý do → về draft | admin |
| `POST /payroll/{period}/pay` | đánh dấu đã chi + **gửi phiếu lương từng người qua Telegram chat riêng** (telegram_notify; ai chưa link Telegram → đánh dấu gửi email/thủ công) | accountant (sau khi approved) |
| `GET /payroll/me?period=` | nhân viên xem phiếu lương của mình (chỉ kỳ đã paid) | mọi role |
| `GET /audit-logs` | tra cứu audit | admin |

**RBAC:** dùng `middleware/rbac.py` role checker hiện có; scope team của leader lọc theo `User.team_id` như pattern trong `api/hr.py::_least_loaded_teammate`.

---

## 3. Tích hợp worker / scheduler (`worker.py` + `services/automation.py`)

| Job | Lịch | Việc |
|---|---|---|
| `auto_close_attendance` | 23:59 hằng ngày | Đóng ca quên checkout, cờ cho leader |
| `monthly_timesheet_lock` | ngày 1 hằng tháng | Chốt bảng công tháng trước, notify accountant "sẵn sàng generate lương" |
| `leave_reminder` | 8:00 | Nhắc người duyệt các đơn pending >24h (escalate lên admin sau 48h) |
| `contract_expiry_reminder` | 8:00 thứ Hai | HĐLĐ hết hạn trong 30 ngày → notify accountant + admin |
| `payslip_dispatch` | trigger khi `/pay` | Gửi phiếu lương chat riêng — **tuyệt đối không gửi vào nhóm chung** (nguyên tắc đã có trong HUONG_DAN_TELEGRAM_NHOM.md) |

---

## 4. Telegram bot — lệnh mới (telegram-bot/)

| Lệnh | Vai trò | Backend |
|---|---|---|
| `/checkin [mã dự án]` | mọi role (mã dự án bắt buộc với giám sát) | POST /attendance/checkin |
| `/checkout` | mọi role | POST /attendance/checkout |
| `/nghiphep <từ> <đến> <lý do>` | mọi role | POST /leaves |
| `/congcuatoi` | mọi role | GET /attendance/me |
| `/phieuluong` | mọi role (chat riêng only) | GET /payroll/me |
| Inline [✅/❌] cho đơn phép & OT | leader/admin | approve/reject endpoints |

---

## 5. Migration & seed

- Chưa có Alembic (known issue trong QUICK_REFERENCE.md) → bảng mới tự tạo qua `Base.metadata.create_all`; các **cột thêm vào bảng cũ** (`users`, `payrolls`) cần script migration thủ công `backend/scripts/migrate_hr_phase1.py` (ALTER TABLE ADD COLUMN — SQLite hỗ trợ) chạy 1 lần trước deploy. Khuyến nghị nhân dịp này đưa Alembic vào.
- `seed.py`: thêm LeaveBalance năm hiện tại cho user mẫu, 5 AttendanceRecord mẫu, 1 kỳ payroll draft.

## 6. Thứ tự triển khai đề xuất

1. AttendanceRecord + checkin/checkout (web+Telegram) + bảng công cá nhân — *độc lập, thấy giá trị ngay*
2. LeaveRequest/Balance + duyệt Telegram — *tái dùng pattern MaterialRequest*
3. AuditLog helper + gắn vào endpoint nhạy cảm — *nhỏ, làm sớm để lương có log từ đầu*
4. Payroll generate + duyệt 2 cấp + phiếu lương Telegram — *phụ thuộc 1-3*

## 7. Rủi ro kỹ thuật

- **Múi giờ:** codebase dùng UTC; `work_date` phải quy về Asia/Ho_Chi_Minh trước khi cắt ngày, nếu không ca tối sẽ rơi sai ngày.
- **SQLite concurrent write:** 100 người check-in 8:00 sáng cùng lúc — WAL mode đã bật (thấy file `jama.db-wal`) nhưng cần retry-on-locked ở tầng service; cân nhắc Postgres khi deploy Railway.
- **Khóa kỳ lương:** mọi PATCH attendance/commission của kỳ đã `approved` phải bị từ chối (kiểm tra trong endpoint, không chỉ ở UI).
- **Riêng tư lương:** endpoint `/payroll/me` chỉ trả dữ liệu của chính JWT user; leader KHÔNG xem được lương thành viên (chỉ accountant/admin).
