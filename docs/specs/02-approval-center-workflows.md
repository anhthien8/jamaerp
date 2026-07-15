# Spec — Trung tâm phê duyệt (Approval Center)

> **Mục tiêu:** Gom mọi luồng duyệt về 1 engine + 1 màn hình "Chờ tôi duyệt" + Telegram inline button, tái dùng pattern `MaterialRequest` đã chạy tốt (`backend/app/api/telegram_workflow.py`).
> **Nguyên tắc bảo mật hiện hành (giữ nguyên):** số liệu tài chính/lương chỉ gửi Telegram **chat riêng**, không bao giờ vào nhóm chung.

---

## 1. Engine chung — model `ApprovalRequest`

Thay vì mỗi loại một bảng (như MaterialRequest hiện tại), dùng 1 bảng generic:

```python
class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: str(36)
    type: str(30)          # leave | advance | payroll_period | expense | overtime | material
    ref_id: str(36)        # id bản ghi gốc (LeaveRequest, Payroll period, AttendanceRecord...)
    title: str(255)        # hiển thị: "Nghỉ phép 2 ngày — Nguyễn Văn A"
    amount: float | None   # nếu có giá trị tiền
    requester_id: FK users
    current_approver_id: FK users        # người đang cần duyệt (hỗ trợ nhiều cấp)
    step: int = 1; total_steps: int = 1  # duyệt 2 cấp: step 1 accountant → step 2 admin
    status: str            # pending | approved | rejected | changes_requested | expired | cancelled
    reason: str | None     # lý do từ chối / yêu cầu sửa
    delegate_id: str | None  # người được ủy quyền khi approver vắng
    due_at: DateTime       # SLA — quá hạn thì nhắc + escalate
    created_at / resolved_at
```

- `MaterialRequest` giữ nguyên chạy song song, migrate về engine này ở phase sau.
- Mỗi type đăng ký một **policy** (code, không config DB cho gọn): ai duyệt, mấy cấp, SLA, escalate tới ai.

## 2. Ma trận 5 luồng

| Loại | Người tạo | Cấp 1 | Cấp 2 | SLA/cấp | Quá hạn |
|---|---|---|---|---|---|
| **Nghỉ phép ≤3 ngày** | mọi role | Leader team | — | 24h | nhắc 24h → escalate admin 48h |
| **Nghỉ phép >3 ngày** / người tạo là leader | mọi role | Leader | Admin | 24h | như trên |
| **Tạm ứng lương** (≤30% lương bậc) | mọi role | Accountant | Admin nếu >5tr | 48h | nhắc → escalate admin |
| **Bảng lương kỳ** | Accountant (generate → submit) | Admin | — | 72h | nhắc admin mỗi ngày |
| **Chi phí công tác** | mọi role | Leader | Accountant (ghi sổ) | 48h | nhắc |
| **OT** | tự sinh khi checkout vượt 8h | Leader | — | 48h | quá hạn → tự reject, NV có thể khiếu nại |

## 3. Workflow tree chuẩn (áp dụng mọi loại)

```
[Tạo đơn] → pending(step 1)
   ├─ Approver bấm ✅ → step < total_steps ? chuyển step+1, notify approver kế → pending(step 2)
   │                     : approved → side-effect theo type (trừ phép / tạo Transaction tạm ứng
   │                       / khóa kỳ lương / ghi sổ chi phí / cộng ot_pay)
   ├─ Approver bấm ❌ (+ lý do bắt buộc) → rejected → notify requester
   ├─ Approver chọn "Yêu cầu sửa" → changes_requested → requester sửa → về pending(step giữ nguyên)
   ├─ Requester hủy khi còn pending → cancelled
   ├─ Quá due_at → notify nhắc; quá 2×SLA → escalate lên admin (current_approver_id = admin)
   └─ Approver bật "vắng mặt" (delegate) → mọi đơn tới delegate_id, ghi rõ "duyệt thay"
```

**Bất biến cần test (QA):**
1. Không side-effect nào chạy trước khi đủ `total_steps` approve.
2. Reject/cancel sau khi approved là không thể (409).
3. Mọi chuyển trạng thái ghi `AuditLog` (spec 01 §1.5).
4. Approver không thể tự duyệt đơn của chính mình (đơn leader → bắt buộc admin).
5. Kỳ lương đã approved → mọi sửa attendance/commission kỳ đó bị chặn ở backend.

## 4. Kênh thông báo

| Sự kiện | Web (notification hiện có) | Telegram |
|---|---|---|
| Đơn mới cần duyệt | badge "Chờ tôi duyệt" | chat riêng approver, inline [✅][❌][✏️ Sửa] |
| Được duyệt/từ chối | notify requester | chat riêng requester |
| Escalate | notify admin | chat riêng admin |
| Bảng lương chờ duyệt | notify admin | chat riêng admin: "Kỳ 2026-07: 104 NV, tổng chi X" — **không gửi nhóm** |

Inline button callback → POST `/approvals/{id}/approve|reject` với `approver_tg_id` (đúng pattern `ApproveRejectRequest` hiện có).

## 5. API

| Endpoint | Role |
|---|---|
| `GET /approvals/pending-for-me` | mọi role (lọc theo current_approver hoặc delegate) |
| `GET /approvals/my-requests` | mọi role |
| `POST /approvals/{id}/approve` \| `reject` \| `request-changes` | approver hợp lệ của step hiện tại |
| `POST /approvals/{id}/cancel` | requester, khi pending |
| `POST /users/me/delegate {delegate_id, until}` | leader/accountant/admin |

## 6. Màn hình web "Chờ tôi duyệt" (`/approvals`)

- Tab: **Chờ tôi** (mặc định) · Đơn của tôi · Đã xử lý.
- Card: loại + title + amount + người tạo + thời gian chờ (đỏ nếu quá SLA) + nút Duyệt/Từ chối/Sửa.
- Bulk approve cho nghỉ phép/OT (chọn nhiều — leader 5 team sales sẽ cần).
- Sidebar hiện badge số đơn chờ (thêm vào `frontend/src/lib/roles.ts` cho role có quyền duyệt).

## 7. Rủi ro chính

- **Nghẽn ở admin:** mọi escalate + lương + phép dài đều dồn về 1 admin — cần delegate hoạt động ngay từ MVP, và cân nhắc thêm role `executive` được duyệt thay.
- **Double-tap Telegram:** 2 người/2 lần bấm ✅ cùng lúc → endpoint phải idempotent (kiểm tra status=pending trong transaction).
- **Đơn mồ côi:** approver nghỉ việc → job đêm quét đơn có approver inactive, chuyển admin.
