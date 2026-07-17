# ADMIN (Giám đốc) — Cheat Sheet

> 🔑 Đăng nhập: `admin@jamahome.vn` / `jamadmin123`

## Bạn thấy gì trên Sidebar

```
✅ Dashboard    ✅ Phê duyệt   ✅ Pipeline    ✅ Dự án     ✅ Khách hàng
✅ Hợp đồng    ✅ Báo giá     ✅ Kho         ✅ Kế toán
✅ Nhân sự     ✅ Tài chính   ✅ P&L         ✅ Báo cáo    ✅ Feedback    ✅ Cài đặt
```

## Việc cần làm hàng ngày

| Thời gian | Việc | Trang | Mô tả |
|-----------|------|-------|-------|
| **8:00** | Xem Dashboard | `/` | Tổng quan doanh thu, pipeline, dự án |
| **8:30** | Quản lý user | `/users` | Tạo/sửa/xóa tài khoản nhân viên mới |
| **9:00** | Cấu hình AI | `/settings` → 🧠 | Chọn model, fallback, test kết nối |
| **10:00** | Duyệt yêu cầu | `/approvals` | Vật tư, hợp đồng, báo giá chờ duyệt |
| **11:00** | Duyệt feedback | `/feedback` | Đọc phản hồi nhân viên → trả lời |
| **14:00** | Tạo link portal | `/customers` → click KH | Tạo link portal → gửi khách xem tiến độ |
| **15:00** | Cấu hình tự động | `/settings` → 🤖 | Set ngưỡng nhắc CSKH, thu hồi lead |
| **16:00** | Backup kiểm tra | `/settings` → 💾 | Verify backup Google Drive |

## Quyền đặc biệt (chỉ Admin mới có)

| Việc | How |
|------|-----|
| Thêm/sửa/xóa nhân viên | `/users` → "+ Thêm nhân viên" |
| Nghỉ việc + chuyển giao | `/hr` → chọn NV → "Nghỉ việc" → chọn người nhận |
| Cấu hình AI Model | `/settings` → 🧠 Cấu hình AI |
| Quản lý bậc lương | `/finance` → Tab "Bậc lương" |
| Quản lý chi phí cố định | `/finance` → Tab "Định phí" |
| Tạo link portal cho KH | `/customers` → click KH → "Tạo link portal" |
| Xem P&L toàn công ty | `/pl` |
| Duyệt vật tư vượt định mức | `/approvals` hoặc Telegram |

## Phím tắt

| Phím | Chức năng |
|------|-----------|
| `Ctrl + K` | Tìm kiếm toàn cục |
| `Esc` | Đóng popup |

## Mẹo

- Chuyển **Demo Mode** → **Work Mode** bằng cách bấm toggle ở Sidebar
- Dùng **Telegram Bot** để xem pipeline khi đi ngoài
- **Customer Portal**: Tạo link từ `/customers` → gửi khách qua Zalo để tự xem tiến độ
- **Feedback**: Nhân viên gửi feedback qua Telegram `/feedback` → xem tại `/feedback`
