# PURCHASING (Nhân viên Thu mua) — Cheat Sheet

> 🔑 Đăng nhập: `purchasing@jamahome.vn` / `purchase123`

## Bạn thấy gì trên Sidebar

```
✅ Dashboard    ❌ Pipeline    ✅ Dự án     ❌ Khách hàng
✅ Hợp đồng    ❌ Báo giá     ✅ Kho       ❌ Kế toán
❌ Nhân sự     ❌ Tài chính   ❌ P&L       ❌ Báo cáo    ✅ Cài đặt
```

## Việc cần làm hàng ngày

| Thời gian | Việc | Trang |
|-----------|------|-------|
| Sáng | Kiểm tra yêu cầu vật tư mới | `/inventory` |
| Sáng | Kiểm tra tồn kho thấp | `/inventory` → cảnh báo đỏ |
| Trưa | Duyệt/ปฏิเสธ yêu cầu | Telegram inline button |
| Chiều | Cập nhật trạng thái nhập kho | `/inventory` |
| Cuối tuần | Kiểm tra tồn kho toàn bộ | `/inventory` |

## Quyền chính

| Việc | How |
|------|-----|
| Quản lý kho vật tư | `/inventory` |
| Duyệt yêu cầu vật tư | Telegram Bot (nhấn nút) |
| Thêm vật tư mới | `/inventory` → "+ Thêm vật tư" |
| Cập nhật tồn kho | Click vật tư → sửa số lượng |
| Xem hợp đồng | `/contracts` (chỉ đọc) |

## Xử lý yêu cầu vật tư từ PM

### Cách 1: Trên Telegram (nhanh)
```
PM gửi yêu cầu → Bạn nhận tin nhắn:

📦 YÊU CẦU VẬT TƯ MỚI:
• Dự án: JMH-0601
• Vật tư: Keo dán gạch đá (5 bao)
• Người yêu cầu: Nguyễn Văn A

[ ✅ Phê duyệt ]   [ ❌ Từ chối ]

→ Nhấn nút Duyệt hoặc Từ chối ngay trên Telegram
```

### Cách 2: Trên Web
1. Vào `/inventory`
2. Kiểm tra tồn kho
3. Nếu đủ → Duyệt
4. Nếu thiếu → Liên hệ nhà cung cấp

## Cảnh báo tồn kho

| Màu | Ý nghĩa |
|-----|----------|
| 🔴 Đỏ | Tồn kho thấp — cần nhập thêm ngay |
| 🟡 Vàng | Sắp hết — lên kế hoạch nhập |
| 🟢 Xanh | Đủ — không cần hành động |

## Mẹo

- **Telegram Bot** là cách nhanh nhất để duyệt vật tư khi đang di chuyển
- Luôn cập nhật tồn kho sau khi nhập/xuất để số liệu chính xác
- Liên kết vật tư với **dự án** để theo dõi chi phí chính xác
