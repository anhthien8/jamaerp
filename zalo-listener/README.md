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

1. Admin vào **Cài đặt → Zalo — Trợ lý lắng nghe → «Đăng nhập Zalo (QR)»**.
2. Service poll thấy yêu cầu → `loginQR` → đẩy ảnh QR về web (QR hết hạn tự làm mới 3 lần).
3. Mở **Zalo trên điện thoại của tài khoản chuyên dụng → Quét mã QR**.
4. Đăng nhập xong: phiên (cookie + imei) gửi về backend, **mã hóa** lưu DB → Railway khởi động lại
   tự đăng nhập, khỏi quét QR. Service đồng bộ danh sách nhóm (tên, số thành viên) mỗi 6 giờ.
5. Nhóm mới vào ở trạng thái **TẮT theo dõi**: admin bật từng nhóm, chọn loại (nội bộ/khách) và
   phòng ban. Tin chỉ được lưu từ nhóm đang bật.

## Vận hành

- Chạy trên **Railway** (service riêng, region Singapore): `railway up --service jama-zalo-listener`.
  Env: `ZALO_INGEST_SECRET` (trùng backend), `BACKEND_URL`.
- **Đừng mở Zalo Web/PC bằng tài khoản chuyên dụng** — Zalo đẩy phiên nghe ra (mã 3000/3003),
  service xóa phiên và báo lỗi về web, admin phải quét QR lại.
- Admin bấm «Đăng xuất» trên web → service ngắt nghe trong ≤10 giây và bỏ phiên đã lưu.
- Có account **#2 dự phòng** khi account chính bị khóa (đặc biệt trước khi mở nhóm khách).
