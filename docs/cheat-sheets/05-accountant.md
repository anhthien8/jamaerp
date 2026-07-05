# ACCOUNTANT (Kế toán) — Cheat Sheet

> 🔑 Đăng nhập: `accountant@jamahome.vn` / `account123`

## Bạn thấy gì trên Sidebar

```
✅ Dashboard    ❌ Pipeline    ✅ Dự án     ✅ Khách hàng
✅ Hợp đồng    ✅ Báo giá     ✅ Kho       ✅ Kế toán
✅ Nhân sự     ✅ Tài chính   ✅ P&L       ✅ Báo cáo    ✅ Cài đặt
```

## Việc cần làm hàng ngày

| Thời gian | Việc | Trang |
|-----------|------|-------|
| Sáng | Kiểm tra giao dịch mới | `/accounting` |
| Sáng | Duyệt yêu cầu vật tư | `/inventory` hoặc Telegram |
| Trưa | Ghi nhận phiếu thu/chi | `/accounting` → "+ Giao dịch mới" |
| Cuối tháng | Xuất báo cáo CSV | `/accounting` → "Xuất CSV" |
| Cuối tháng | Kiểm tra P&L | `/pl` |

## Quyền chính

| Việc | How |
|------|-----|
| Ghi nhận giao dịch thu/chi | `/accounting` |
| Quản lý lương & hoa hồng | `/finance` |
| Quản lý nhân sự | `/hr` → "+ Thêm Nhân viên" |
| Xem P&L | `/pl` |
| Duyệt vật tư | `/inventory` → chọn YC → Duyệt |

## Tabs trên trang Kế toán

| Tab | Nội dung |
|-----|----------|
| **Tổng quan** | Tổng thu, tổng chi, lãi/lỗ tháng |
| **Giao dịch** | Danh sách thu/chi, lọc theo loại/dự án |
| **Hoa hồng** | Commission nhân viên Sales |
| **Bảng lương** | Lương + BHXH theo bậc |

## Mẹo

- Xuất CSV regularly để backup dữ liệu kế toán
- Kiểm tra **Công nợ phải thu** trên Tab Tổng quan
- Duyệt vật tư nhanh qua **Telegram Bot** (nhận inline button)
