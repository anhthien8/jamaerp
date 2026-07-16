# JAMA Zalo Listener — Ingest Service (spec 09)

Trợ lý **lắng nghe** nhóm Zalo → phân tích AI ở backend → đẩy tín hiệu về Telegram.

## ⚠️ Đọc trước khi dùng

- Dùng **tài khoản Zalo cá nhân chuyên dụng** (KHÔNG phải account thật của nhân viên, KHÔNG phải OA công ty).
- Automation Zalo qua thư viện không chính thống (`zca-js`) **vi phạm điều khoản Zalo** → tài khoản có nguy cơ **bị khóa sớm/muộn**. Service này thiết kế **listen-only** (không gửi tin) để giảm mạnh rủi ro.
- Triển khai theo phase: **P0** = 1 nhóm nội bộ, 2 tuần thử → **P1** nội bộ → **P2** nhóm khách (có account dự phòng). Xem `docs/specs/09`.

## Cài đặt

```bash
cd zalo-listener
npm install          # cần Node 18+
```

## Chạy

```bash
ZALO_INGEST_SECRET="<trùng-với-backend>" \
BACKEND_URL="https://jama-crm-prod-production.up.railway.app" \
npm start
```

Biến môi trường:
- `ZALO_INGEST_SECRET` (bắt buộc) — phải trùng `ZALO_INGEST_SECRET` đặt ở backend.
- `BACKEND_URL` — URL backend JAMA (mặc định `http://localhost:8000`).
- `POLL_MS` — chu kỳ poll yêu cầu đăng nhập (mặc định 5000).

## Luồng đăng nhập QR (qua web admin)

1. Admin vào **Cài đặt → 💬 Zalo → "Đăng nhập Zalo (QR)"** trên web JAMA.
2. Service này (đang chạy) poll thấy yêu cầu → gọi `loginQR` → nhận QR → đẩy ảnh QR về backend.
3. Web admin hiển thị QR → mở **Zalo trên điện thoại → Cá nhân → Quét mã QR**.
4. Đăng nhập xong → service bắt đầu lắng nghe nhóm → mỗi tin đẩy `POST /zalo/ingest/message`.

## Vận hành

- Chạy 24/7 trên **VPS Việt Nam** (IP VN, tránh cờ đăng nhập lạ). Dùng `pm2` hoặc systemd để tự khởi động lại.
- Phiên Zalo có thể rớt → service báo `error` về web, admin đăng nhập lại (quét QR mới).
- Có account **#2 dự phòng** khi account chính bị khóa (đặc biệt trước khi mở P2 nhóm khách).

## ⚠️ Ghi chú `[ADAPT]` trong code

`zca-js` thay đổi interface giữa các phiên bản. Các chỗ đánh dấu `[ADAPT]` trong `src/index.js`
(khởi tạo `Zalo`, `loginQR`, cấu trúc object message) cần đối chiếu với README của phiên bản
`zca-js` thực tế khi `npm install`. Đây là **scaffold khung** — logic backend + web đã hoàn chỉnh,
phần này là lớp keo nối tới thư viện Zalo.

## Bảo mật & riêng tư (Nghị định 13/2023)

- Chỉ xử lý tin **nhóm** (bỏ chat 1-1).
- Chỉ gửi **text + metadata** về backend; KHÔNG tải/lưu ảnh thô (chỉ link).
- Backend lưu **tín hiệu**, xóa tin thô sau 7 ngày.
- Dữ liệu chỉ dùng nâng hiệu suất/CSKH, KHÔNG dùng kỷ luật nhân viên.
