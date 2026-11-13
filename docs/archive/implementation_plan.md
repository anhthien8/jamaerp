# Kế hoạch triển khai: Pipeline Dự án, Ghi chú & Media, Phân quyền Kho vật tư và Tư vấn P&L

Tài liệu này chi tiết phương án triển khai phần mềm cho các yêu cầu mới:
1. **Pipeline quản lý dự án (5 giai đoạn) dạng Kanban** + Cho phép **Nhập ghi chú kèm Media/File** cho từng Task (đầu việc) của dự án. (ĐÃ HOÀN THÀNH ✅)
2. **Phân quyền Kho vật tư**: Chỉ cho phép `admin` và bộ phận `purchasing` (Thu mua) xem và chỉnh sửa. (ĐÃ HOÀN THÀNH ✅)
3. **Đề xuất kiến trúc module P&L** tinh gọn (KISS) & Kế hoạch triển khai chi tiết cho Giai đoạn tiếp theo.

---

## Trạng thái triển khai hiện tại

- **Backend API & Database Schema:** Hoàn thành triển khai SQLite models (`Project`, `Task`, `TaskActivity`), API endpoints phục vụ dự án, phân quyền kho vật tư và hooks tự động tạo dự án khi lead thành `signed_design`.
- **Frontend Integration:** Hoàn thành nâng cấp giao diện `ProjectsPage` với Kanban Board, Project Detail Modal nhóm theo giai đoạn và Task Detail Modal tích hợp note timeline + media + final file. Kiểm tra build thành công 100%.

---

## Kế hoạch triển khai tiếp theo: Module tính P&L (Profit & Loss) tinh gọn (KISS)

Theo thống nhất của ban quản trị, để hệ thống không bị quá phức tạp bởi các module HR/Lương/BHXH cồng kềnh, chúng ta sẽ xây dựng module P&L tinh gọn theo các hạng mục chi tiết dưới đây:

### 1. Database & Backend API (P&L)

Chúng ta sẽ tạo các endpoint để tính toán doanh thu và chi phí dựa trên dữ liệu giao dịch kế toán thực tế:

#### 1.1 API báo cáo P&L Dự án (`GET /accounting/projects/{project_id}/pl`)
- **Doanh thu (Revenue):** Tổng tiền của các giao dịch `income` có liên kết với `project_id` này (thuộc loại `design_contract`, `construction_contract`).
- **Chi phí (COGS):**
  - **Vật tư:** Tổng tiền giao dịch `expense` loại `material` liên kết với `project_id`.
  - **Nhân công/Thầu phụ:** Tổng tiền giao dịch `expense` loại `labor` liên kết với `project_id`.
  - **Commission:** Tổng tiền giao dịch `expense` loại `commission` liên kết với `project_id`.
- **Trả về json dạng:**
```json
{
  "project_id": "demo-proj-001",
  "project_name": "Nhà phố Q7 - Chị Mai",
  "revenue": 245000000,
  "costs": {
    "material": 85000000,
    "labor": 45000000,
    "commission": 15000000
  },
  "total_costs": 145000000,
  "gross_profit": 100000000,
  "margin_pct": 40.8
}
```

#### 1.2 API báo cáo P&L Doanh nghiệp (`GET /accounting/company/pl`)
- Hỗ trợ query params: `year`, `month`.
- **Tổng Lợi nhuận gộp:** Tổng lợi nhuận gộp của tất cả các dự án trong kỳ.
- **Chi phí vận hành cố định (OPEX):** Tổng các giao dịch `expense` thuộc danh mục chi phí vận hành chung (không gắn với `project_id` cụ thể, ví dụ: `salary` của khối văn phòng, `rent` văn phòng, điện nước).
- **Trả về json dạng:**
```json
{
  "period": "2026-06",
  "total_project_revenue": 1490000000,
  "total_project_costs": 530000000,
  "total_project_gross_profit": 960000000,
  "opex_costs": {
    "salaries": 180000000,
    "rent": 30000000,
    "utilities": 10000000
  },
  "total_opex": 220000000,
  "net_profit": 740000000
}
```

---

### 2. Frontend Integration (P&L)

#### 2.1 Tích hợp tab P&L trong trang Kế toán (`frontend/src/app/accounting/page.tsx`)
- Thêm một Tab mới mang tên **📊 Báo cáo P&L**.
- Chỉ cho phép `admin` và `accountant` xem tab này (`ROLE_PERMISSIONS` cho phép cấu hình).

#### 2.2 Thành phần giao diện P&L:
1. **P&L Doanh nghiệp tổng quan (Overhead):**
   - Bộ chọn Tháng/Năm.
   - Thẻ thống kê: Lợi nhuận gộp Dự án, Tổng Chi phí vận hành (OPEX), Lợi nhuận ròng.
   - Biểu đồ hình tròn phân tích chi tiết các loại chi phí cố định (Lương, Mặt bằng, Khác).
2. **Danh sách P&L từng công trình (Direct Profitability List):**
   - Bảng danh sách các dự án đang chạy với các cột: Mã dự án, Tên dự án, Doanh thu thực nhận, Chi phí vật tư, Chi phí nhân công/Thầu phụ, Commission đã chi, Lợi nhuận gộp dự án, % Tỷ suất lợi nhuận.
   - Điểm cảnh báo màu đỏ đối với dự án có lợi nhuận gộp thấp hơn 15% để giám đốc nhanh chóng can thiệp.

---

## Kế hoạch kiểm thử P&L
- **Kiểm thử tự động:** Tạo các unit test tính toán P&L trong `backend/tests/test_pl.py`.
- **Kiểm thử thủ công:** Tạo giao dịch mẫu cho dự án thử nghiệm và đối chiếu số liệu hiển thị trên bảng điều khiển.
