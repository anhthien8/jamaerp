# Spec — Onboarding & Offboarding nhân sự

> Giải quyết trực tiếp khuyến nghị 8.2 trong `docs/Phan_Quyen_ERP_JAMA_HOME.txt` ("thiết lập quy trình onboarding/offboarding để tự động cấp/thu hồi quyền") và các vấn đề 8.1 (dùng chung tài khoản admin ở phòng Thiết kế/Dự án/Kế toán).
> **Nền có sẵn:** `backend/app/api/hr.py` đã xử lý offboarding phần lõi (resign-preview → resign tự chuyển lead cho người ít lead nhất trong team + chuyển task cho PM + vô hiệu hóa tài khoản + undo trong 7 ngày). Spec này bổ khuyết phần còn thiếu.

---

## 1. Hồ sơ nhân sự mở rộng (model `EmployeeProfile`)

```python
class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    id, user_id (FK, unique)
    national_id: str | None          # CCCD
    date_of_birth: Date | None
    address: str | None
    bank_account: str | None; bank_name: str | None   # để chi lương
    contract_type: str               # probation | fixed_1y | fixed_2y | indefinite
    contract_signed_date: Date | None
    contract_end_date: Date | None   # worker nhắc trước 30 ngày (spec 01 §3)
    social_insurance_no: str | None  # số sổ BHXH
    start_date: Date                 # ngày vào làm — tính thâm niên & phép năm
    mentor_id: str | None            # FK users — người kèm cặp
    emergency_contact: str | None
    documents_json: Text | None      # link file HĐLĐ/bằng cấp đã upload
```

Trang HR hiện có (mục 11 HUONG_DAN_SU_DUNG_CRM.md) thêm tab "Hồ sơ" — chỉ admin/accountant sửa, nhân viên xem hồ sơ của mình.

## 2. Onboarding — checklist tự sinh theo vai trò

Khi tạo nhân viên mới (`POST /users` hiện có), backend tự sinh `OnboardingChecklist` với các bước theo role:

### Model

```python
class OnboardingStep(Base):
    __tablename__ = "onboarding_steps"
    id, user_id (FK)
    step_key: str        # account_created, telegram_linked, sop_read, demo_training,
                         # quiz_passed, mentor_assigned, day1_review, week1_review, month1_review
    title: str; owner_role: str   # ai chịu trách nhiệm: admin | accountant | leader | self
    due_days: int        # deadline = start_date + due_days
    status: str          # pending | done | skipped
    done_at, done_by
```

### Checklist chuẩn (mọi role) + phần riêng

| # | Bước | Người làm | Hạn | Tự động hóa |
|---|---|---|---|---|
| 1 | Tạo tài khoản đúng role + team (KHÔNG dùng chung admin) | Admin | ngày 0 | tự đánh done khi user tạo |
| 2 | Thu hồ sơ: HĐLĐ, CCCD, sổ BHXH, tài khoản ngân hàng | Accountant | ngày 3 | done khi EmployeeProfile đủ trường bắt buộc |
| 3 | Liên kết Telegram (`/id` → điền vào hồ sơ → `/start`) | Nhân viên + Admin | ngày 1 | done khi `telegram_user_id` có giá trị |
| 4 | Đọc cheat-sheet vai trò (`docs/cheat-sheets/` — đã có đủ 8 role) + bấm "Đã đọc" | Nhân viên | ngày 2 | tracking trên web |
| 5 | Training trên **Demo Mode** + quiz 10 câu theo role (≥8/10 đạt) | Nhân viên | ngày 5 | quiz trong app |
| 6 | Gán mentor/quản lý trực tiếp | Leader | ngày 1 | |
| 7 | Review 1 ngày / 1 tuần / 1 tháng (ghi vào coaching log) | Leader | D1/D7/D30 | worker nhắc leader |
| — | **Sales:** được phân team + nhận 3-5 lead đầu có mentor kèm | Leader | tuần 1 | |
| — | **Giám sát:** thực hành `/checkin`, `/baocao`, `/vatlieu`, `/suco` tại 1 công trình | Mentor | tuần 1 | |
| — | **Kế toán:** bàn giao quyền duyệt + đọc spec luồng lương | Admin | tuần 1 | |

Trang HR hiển thị progress bar onboarding từng nhân viên mới; worker gửi Telegram nhắc bước quá hạn cho owner.

## 3. Offboarding — bổ khuyết trên nền `api/hr.py`

### Đã có (giữ nguyên)
`resign-preview` (xem trước lead/task ảnh hưởng) → `resign` (chuyển lead → người ít lead nhất team / người chỉ định; task → PM dự án; deactivate; ghi Activity "Chuyển giao từ X do nghỉ việc") → `undo-resign` (7 ngày).

### Còn thiếu — thêm vào flow `resign`:

| # | Việc | Chi tiết |
|---|---|---|
| 1 | **Chốt hoa hồng treo** | Query `Commission` status `pending/approved` chưa `paid` của user → báo cáo cho accountant quyết: trả nốt kỳ lương cuối theo mốc đã đạt (50/30/20), phần mốc chưa đạt → chuyển người nhận bàn giao hoặc hủy theo chính sách. **Không tự xóa.** |
| 2 | **Thu hồi Telegram** | Xóa `telegram_user_id` + bot gửi tin chào tạm biệt; nếu trong nhóm công ty → nhắc admin remove khỏi nhóm (bot không tự kick được ở mọi cấu hình) |
| 3 | **Kỳ lương cuối** | Tạo payroll pro-rata đến `resign_date`, gộp phép năm chưa dùng (quy tiền theo luật) + hoa hồng chốt ở bước 1 |
| 4 | **Bàn giao tài liệu** | Checklist thủ công: file thiết kế/bản vẽ, ảnh công trình, tài liệu KH — leader xác nhận |
| 5 | **Phỏng vấn nghỉ việc** | Form ngắn (lý do, đề xuất) — lưu vào hồ sơ, HR analytics dùng sau |
| 6 | **Audit** | Toàn bộ bước ghi `AuditLog` (spec 01 §1.5) |

`resign` trả thêm `offboarding_checklist_id` — trạng thái từng bước theo dõi trên trang HR như onboarding.

### Lỗ hổng dữ liệu cần vá kèm theo

- **Quy tắc "không lộ SĐT khách giữa các sale":** khi chuyển lead hàng loạt lúc nghỉ việc, người nhận thấy toàn bộ lịch sử + SĐT — đúng chủ đích, nhưng cần AuditLog ghi rõ ai nhận bao nhiêu lead để truy vết.
- **User inactive còn JWT sống:** kiểm tra `middleware/auth.py` — mọi request phải check `is_active` (nếu chưa có thì thêm), tránh nhân viên đã nghỉ còn token hợp lệ.
- **Tài khoản dùng chung admin ở 3 phòng (vấn đề 8.1):** trước khi áp dụng quy trình này, tạo tài khoản riêng cho từng người phòng Thiết kế/Dự án/Kế toán — việc một lần, làm ngay.

## 4. RACI tổng hợp

| Bước | Admin | Accountant (kiêm HR) | Leader | Nhân viên |
|---|---|---|---|---|
| Tạo/khóa tài khoản, phân quyền | **R** | C | I | — |
| Hồ sơ, HĐLĐ, BHXH, lương cuối | I | **R** | — | C |
| Đào tạo, mentor, review D1/W1/M1 | I | I | **R** | C |
| Bàn giao lead/task/tài liệu | A | I | **R** | C |
| Telegram link/thu hồi | **R** | I | — | C |
