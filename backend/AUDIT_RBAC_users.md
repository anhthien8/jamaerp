# Audit `app/api/users.py` — 12 chỗ `role not in` (chuẩn bị refactor sang `quyen_hieu_luc`)

Ngày: 2026-09-12. Nguồn sự thật quyền: `app/middleware/permissions.py`
(`quyen_hieu_luc(user, db)` → dict quyền hiệu lực; key liên quan: `canManageUsers`
— mặc định chỉ `admin` + `accountant` = True).

Lưu ý ma trận thực tế: vai trò hệ thống là `admin, leader, data_entry, accountant,
executive, supervisor` — KHÔNG có `sale_leader`/`sale` như mô tả task; `sale_leader`
nếu tồn tại là vai trò tùy chỉnh (nền data_entry). Ánh xạ: sale_leader≈leader,
sale≈data_entry, kế toán/tài chính admin≈accountant.

## A. REFACTOR ĐƯỢC sang `quyen_hieu_luc` → `canManageUsers` (7 chỗ)

Mẫu chung: `current_user.role not in ("admin", "accountant")`
→ `not (await quyen_hieu_luc(current_user, db)).get("canManageUsers")`.
Hành vi mặc định KHÔNG đổi (mặc định chỉ admin+accountant có canManageUsers);
điểm được thêm: sếp bật/tắt qua trang Phân quyền có hiệu lực thật.

| # | Dòng | Endpoint | Guard hiện tại | Ghi chú |
|---|------|----------|----------------|---------|
| 1 | 255 | `create_team` | tự lấy mình làm leader = tự chuyển đội | chống self-escalation; canManageUsers đúng ngữ nghĩa "quản lý nhân sự" |
| 2 | 320 | `update_team` | gán mình làm leader đội khác | như trên (kèm điều kiện `team_id != team.id` — giữ nguyên) |
| 3 | 365 | `set_team_members` | tự thêm mình vào đội khác | như trên |
| 4 | 788 | `update_user` | sửa người khác (self-edit vẫn cho) | GIỮ nhánh `current_user.id != user_id`; chỉ thay vế role |
| 5 | 833 | `update_user` | đổi `team_id` người khác/chính mình | self-escalation qua đội |
| 6 | 858 | `update_user` | đổi `department` | self-escalation qua bộ phận (điều phối KD) |
| 7 | 912 | `get_user_permissions` | xem quyền người khác (self vẫn cho) | GIỮ nhánh self; chỉ thay vế role |

Kỹ thuật: trong `update_user`, gọi `quyen_hieu_luc` MỘT lần đầu hàm, tái dùng cho
các check 788/825/833/858 — tránh 3-4 lượt đọc cache/DB.

## B. GIỮ NGUYÊN (5 chỗ)

| # | Dòng | Lý do |
|---|------|-------|
| 1 | 641 | `if role not in VALID_ROLES` — VALIDATION role-key hợp lệ, không phải permission check |
| 2 | 748 | `data.role not in VALID_ROLES and ... custom_role_keys` — validation input khi tạo user |
| 3 | 804 | validation role-key khi update |
| 4 | 807 | validation role-key custom khi update |
| 5 | 825 | gán `salary_grade_id`/`dependents_count` — business rule tài chính/HR admin. Ma trận chỉ có `canViewPayroll` (XEM lương), không có key "gán bậc lương"; map View→Write là mở rộng quyền ngầm. Giữ hardcode admin/accountant cho tới khi có key `canManagePayroll` riêng. |

## C. Ngoài phạm vi 12 chỗ nhưng liên quan (không đụng)

- L638, L742, L800, L802 dùng `role != "admin"` (đổi phân quyền, tạo user, đổi role/is_active)
  — admin-only cứng, đúng chủ đích chống leo thang, KHÔNG refactor.
- `is_team_lead()` (rbac.py) vẫn so role trực tiếp cho scope leader — ngoài phạm vi audit này.
