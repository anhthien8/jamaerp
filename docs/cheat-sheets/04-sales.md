# SALES (Nhân viên Kinh doanh) — Cheat Sheet

> 🔑 Đăng nhập: `sales@jamahome.vn` / `sales123`

## Bạn thấy gì trên Sidebar

```
✅ Dashboard    ✅ Chấm công    ✅ Pipeline    ✅ Dự án     ✅ Khách hàng
✅ Hợp đồng    ✅ Báo giá     ❌ Kho       ❌ Kế toán
❌ Nhân sự     ❌ Tài chính   ❌ P&L       ✅ Báo cáo    ✅ Cài đặt
```

## Việc cần làm hàng ngày

| Thời gian | Việc | Trang | Mô tả |
|-----------|------|-------|-------|
| **8:00** | Chấm công | `/attendance` | Check-in đầu ca |
| **8:15** | Xem briefing | Telegram `/briefing` | Bot gửi danh sách leads cần follow-up |
| **8:30** | Nhập lead mới | `/leads` hoặc Telegram | Khách Zalo → paste → AI parse → tạo lead |
| **9:00-11:00** | Follow-up leads | `/leads` | Click lead → ghi chú cuộc gọi → chuyển stage |
| **11:00** | Báo giá nhanh | `/quote-tool` | Khách hỏi giá → chọn Xây mới/Cải tạo |
| **14:00** | Chuyển stage | `/leads` | Khách đồng ý → "Đang tư vấn" → "Khảo sát" |
| **16:00** | Cập nhật CRM | `/leads` | Ghi chú cuối ngày, cập nhật last_contacted |
| **Khi cần** | Gửi feedback | Telegram `/feedback` | Báo bug hoặc đề xuất tính năng |

## Quyền chính

| Việc | How |
|------|-----|
| Nhập lead mới | `/leads` → "+ Thêm Lead" |
| Chọn Nguồn + Kênh lead | Tạo lead → chọn Source (Zalo/FB) + Channel (Kênh A/B/Sale/Affiliate) |
| Chuyển giai đoạn lead | Click lead → chọn giai đoạn mới (6 bước) |
| Ghi hoạt động | Click lead → nhập ghi chú → "Gửi" |
| Tạo hợp đồng | `/contracts` → "+ Thêm hợp đồng" |
| Báo giá nhanh | `/quote-tool` → chọnmode Xây mới hoặc Cải tạo |
| Xem báo cáo cá nhân | `/reports` |

## 6 giai đoạn Pipeline

```
Tiếp nhận mới → Đang tư vấn → Khảo sát → Dự toán & tư vấn → Ký HĐ Thiết kế
                                                                        ↓
                                                                    Dự án tự tạo
```

## Báo giá tức thì (`/quote-tool`)

**Hai chế độ:**
- 🏗️ **Xây mới**: Nhập diện tích + loại nhà → 3 phương án (Cơ bản/Tiêu chuẩn/Cao cấp)
- 🔨 **Cải tạo**: Nhập diện tích/tầng + số tầng → Khung 100+ hạng mục, gợi ý vật liệu theo ngân sách

**Cách dùng:**
1. Chọn chế độ → Nhập số liệu → "Tạo báo giá"
2. Xem kết quả → Chọn phương án phù hợp
3. Bấm "Copy text gửi Zalo" → Paste vào tin nhắn Zalo cho khách

## Telegram Bot — Công cụ đắc lực

| Lệnh | Khi nào dùng |
|-------|--------------|
| `/lead` | Đang ngoài → nhận tin Zalo → paste vào bot |
| `/pipeline` | Kiểm tra nhanh pipeline trên điện thoại |
| `/briefing` | Mỗi sáng xem việc cần làm |
| `/suggest [ID]` | Cần gợi ý AI cho lead khó |

## Mẹo

- **Forward tin nhắn Zalo** trực tiếp vào Telegram Bot → bot tự phân tích
- Khi lead ký → hệ thống tự tạo dự án + 19 tasks, **bạn không cần nhập lại**
- Luôn cập nhật hoạt động → Leader theo dõi được tiến độ
- Lead quá hạn 7 ngày → hệ thống tự thu hồi giao sale khác
