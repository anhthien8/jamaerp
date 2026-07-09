# 📢 Hướng dẫn cài đặt Nhóm Telegram công ty JAMA HOME

> Sau khi cài đặt xong, bot JAMA CRM sẽ hoạt động như **trợ lý công việc** trong nhóm:
> gửi briefing mỗi sáng, tra cứu dự án, nhận báo cáo công trình, yêu cầu vật tư, báo sự cố, check-in/out GPS — cho toàn bộ nhân viên ở mọi role.

---

## Phần 1 — Chuẩn bị Bot (làm 1 lần, 5 phút)

### Bước 1: Kiểm tra bot đã có token
Bot của JAMA đã được tạo qua **@BotFather**. Nếu chưa có:

1. Mở Telegram, tìm **@BotFather** → gõ `/newbot`
2. Đặt tên: `JAMA HOME Trợ lý` — username: `jamahome_crm_bot` (phải kết thúc bằng `bot`)
3. BotFather trả về **token** dạng `123456789:AAH...xyz`

### Bước 2: Cấu hình token vào hệ thống
Thêm token vào file `.env` của **cả backend và telegram-bot**:

```env
TELEGRAM_BOT_TOKEN=123456789:AAH...xyz
```

- Backend dùng token để **push thông báo** (nhắc CSKH, báo cáo BOD, briefing nhóm)
- Bot dùng token để **nhận lệnh** từ nhân viên

> ⚠️ Deploy trên Railway: thêm biến `TELEGRAM_BOT_TOKEN` trong tab **Variables** của cả 2 service.

### Bước 3: Giữ Privacy Mode = ENABLED (mặc định)
Vào @BotFather → `/mybots` → chọn bot → **Bot Settings** → **Group Privacy** → giữ **Enabled**.

- ✅ Enabled: trong nhóm, bot **chỉ đọc lệnh /** (bảo mật — không đọc trò chuyện riêng của nhân viên)
- Bot vẫn nhận đủ: `/duan`, `/baocao`, `/id`... và vẫn **gửi** briefing bình thường

---

## Phần 2 — Tạo nhóm công ty & kết nối (5 phút)

### Bước 1: Tạo nhóm
1. Telegram → **New Group** → đặt tên: `JAMA HOME — Công việc`
2. Thêm toàn bộ nhân viên vào nhóm

### Bước 2: Thêm bot vào nhóm
1. Trong nhóm → **Add members** → tìm username bot (vd `@jamahome_crm_bot`) → thêm
2. Bot tự gửi lời chào + hướng dẫn ngay khi được thêm
3. (Khuyến nghị) Bấm vào tên nhóm → **Administrators** → thêm bot làm **admin** để bot không bị Telegram giới hạn khi gửi tin thường xuyên

### Bước 3: Lấy Chat ID của nhóm
Trong nhóm, gõ:

```
/id
```

Bot trả về Chat ID dạng **số âm**, ví dụ: `-1001234567890` → copy lại.

### Bước 4: Dán Chat ID vào CRM
1. Đăng nhập CRM bằng tài khoản **admin** → **Cài đặt** (⚙️)
2. Mục **🤖 Tự động hóa CSKH & Báo cáo** → ô **📢 Nhóm Telegram công ty**
3. Dán Chat ID (`-1001234567890`) → bật công tắc → **Lưu cài đặt**
4. Bấm **📢 Gửi briefing nhóm** để test — nhóm phải nhận được tin nhắn briefing

✅ Xong! Từ giờ mỗi sáng (theo giờ cấu hình, mặc định 08:00) bot tự gửi **briefing công việc** vào nhóm: lead mới, số dự án đang chạy, công việc đang mở, cảnh báo lead quá hạn.

> 🔒 Briefing nhóm **không chứa số liệu tài chính** (doanh thu, chi phí, P&L). Báo cáo tài chính chỉ gửi **riêng** cho admin/executive qua chat cá nhân với bot.

---

## Phần 3 — Liên kết từng nhân viên với bot (mỗi người 1 phút)

Để dùng lệnh bot (và nhận nhắc việc cá nhân), mỗi nhân viên cần liên kết Telegram ID:

1. Nhân viên chat riêng với bot → gõ `/id` → nhận **User ID** (số dương)
2. Gửi User ID cho admin
3. Admin vào CRM → **Nhân sự** → sửa hồ sơ nhân viên → điền **Telegram User ID**
4. Nhân viên gõ `/start` với bot → thấy "Chào mừng [Tên]" là thành công

---

## Phần 4 — Các lệnh nhân viên dùng hằng ngày

| Lệnh | Dùng cho | Chức năng |
|------|----------|-----------|
| `/duan JMH-001` | Mọi role | Tra cứu nhanh dự án (tiến độ, PM, tasks) |
| `/baocao JMH-001 Đã xong trần thạch cao` | Giám sát | Báo cáo công trình + gửi kèm ảnh |
| `/vatlieu JMH-001 Sơn Dulux - 10 thùng` | Giám sát/PM | Yêu cầu vật tư → sếp duyệt ngay trên Telegram |
| `/suco JMH-001 Thấm nước tầng 2` | Giám sát | Báo sự cố + ảnh hiện trường |
| `/checkin JMH-001` / `/checkout JMH-001` | Giám sát | Chấm công GPS tại công trình |
| `/pipeline` | Sales | Xem pipeline lead của mình |
| `/briefing` | Mọi role | Briefing cá nhân |
| `/lead` (chat riêng) | Sales/Admin | Paste tin nhắn Zalo → AI tự tách thông tin lead |
| `/id` | Mọi role | Lấy Chat ID / User ID |

> 💡 Lệnh nhập lead bằng AI (`/lead`, paste Zalo) chỉ hoạt động trong **chat riêng** với bot — tránh lộ SĐT khách trong nhóm chung.

---

## Phần 5 — Cấu hình AI Model (Admin)

AI của bot (parse lead, chấm điểm, gợi ý sales) dùng model cấu hình **tập trung** — áp dụng cho mọi role, đổi model không cần restart:

1. CRM → **Cài đặt** → mục **🧠 Cấu hình AI Model (toàn hệ thống)**
2. Chọn model free từ danh sách gợi ý:
   - **Groq — Llama 3.3 70B**: free tier, nhanh, khuyến nghị → lấy key tại [console.groq.com](https://console.groq.com)
   - **Google Gemini 2.0 Flash**: free tier → lấy key tại [aistudio.google.com](https://aistudio.google.com)
   - **OpenRouter free models** → [openrouter.ai](https://openrouter.ai)
   - **Ollama**: chạy local, không cần key (VPS tự host)
3. Dán API key → cấu hình **Model dự phòng** (khuyến nghị khác nhà cung cấp với model chính)
4. Bấm **🔌 Test kết nối** → thấy model trả lời là OK → **Lưu cấu hình AI**

**Cơ chế fallback 3 lớp:** Model chính lỗi/hết quota → tự chuyển model dự phòng → vẫn lỗi → hệ thống dùng rule-based (bot không bao giờ "chết").

---

## Xử lý sự cố thường gặp

| Vấn đề | Cách xử lý |
|--------|-----------|
| Bot không phản hồi `/id` trong nhóm | Kiểm tra bot đã được thêm vào nhóm; service telegram-bot đang chạy |
| Bấm "Gửi briefing nhóm" báo lỗi | Chat ID sai (phải là số âm) hoặc `TELEGRAM_BOT_TOKEN` chưa cấu hình ở backend |
| Bot không nhận diện nhân viên | Telegram User ID chưa được điền trong hồ sơ Nhân sự |
| Nhóm nâng cấp lên supergroup | Chat ID **đổi** (thêm tiền tố -100) — gõ `/id` lại và cập nhật trong CRM |
| AI không hoạt động | Cài đặt → Cấu hình AI Model → Test kết nối để xem lỗi cụ thể |
