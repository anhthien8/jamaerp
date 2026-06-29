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

## 5. Phase tiếp theo: Xây dựng Module P&L (KISS) - [KẾ HOẠCH TRIỂN KHAI ⏳]
- `[ ]` **Backend P&L API:**
  - `[ ]` Thêm API tính P&L cho từng dự án `GET /accounting/projects/{project_id}/pl`
  - `[ ]` Thêm API tính P&L tổng quan doanh nghiệp theo tháng/năm `GET /accounting/company/pl`
- `[ ]` **Frontend P&L UI:**
  - `[ ]` Cập nhật `ROLE_PERMISSIONS` cho phép `accountant` xem báo cáo tài chính P&L.
  - `[ ]` Tích hợp tab **Báo cáo P&L** trong `/accounting` trên giao diện.
  - `[ ]` Thiết kế bảng lợi nhuận trực tiếp trên từng dự án (có điểm cảnh báo dự án tỉ suất thấp).
  - `[ ]` Thiết kế thẻ thống kê OPEX và lợi nhuận ròng doanh nghiệp.
- `[ ]` **Kiểm thử & Đưa vào hoạt động:**
  - `[ ]` Viết unit test tự động tính toán số liệu P&L.
  - `[ ]` Kiểm tra tích hợp, chạy thử và deploy lên Railway.
